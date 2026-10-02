"""R0 evidence: measure semantic false accepts without executing any capability."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

SCHEMA = "adversarial-benchmark/1"
MEANING_LANGUAGES = {"en", "es", "ja", "zh"}
OUTCOMES = ("passed", "false_accept", "false_reject", "abstain", "infrastructure_error")


# Import engine dependencies on use, so missing packages still produce a report.
def parse_meaning(text: str, language: str):
    from intentlang.meaning_parser import parse_meaning as parse
    return parse(text, language)


def compare_candidates(expected, candidates):
    from intentlang.semantic_comparator import compare_candidates as compare
    return compare(expected, candidates)


def resolve(text: str, language: str):
    from intentlang.resolve import resolve as resolve_text
    return resolve_text(text, language)


def lower_intent_to_program(intent):
    from intentlang.lowering import lower_intent_to_program as lower
    return lower(intent)


def _validate_row(row: Any, line: int, seen: set[str]) -> list[str]:
    if not isinstance(row, dict):
        return [f"line {line}: fixture must be an object"]
    errors = [
        f"line {line}: {name} must be a nonempty string"
        for name in ("case_id", "kind", "phenomenon", "language", "source")
        if not isinstance(row.get(name), str) or not row[name].strip()
    ]
    case_id = row.get("case_id")
    if isinstance(case_id, str):
        if case_id in seen:
            errors.append(f"line {line}: duplicate case_id {case_id!r}")
        seen.add(case_id)
    expected = row.get("expected")
    if not isinstance(expected, dict):
        return [*errors, f"line {line}: expected must be an object"]
    kind = row.get("kind")
    if kind == "meaning_pair":
        if not isinstance(row.get("candidate"), str) or not row["candidate"].strip():
            errors.append(f"line {line}: candidate must be a nonempty string")
        if expected.get("relation") not in ("equivalent", "different"):
            errors.append(f"line {line}: relation must be equivalent or different")
        if set(expected) != {"relation"}:
            errors.append(f"line {line}: meaning expectation only supports relation")
        languages = MEANING_LANGUAGES
        target = row.get("target_language", row.get("language"))
        if not isinstance(target, str) or target not in languages:
            errors.append(f"line {line}: unsupported target_language")
    elif kind == "intent_surface":
        if not isinstance(expected.get("can_act"), bool):
            errors.append(f"line {line}: can_act must be a boolean")
        if expected.get("can_act") is True and (
            not isinstance(expected.get("primitive"), str) or not expected["primitive"].strip()
        ):
            errors.append(f"line {line}: positive intent requires a primitive")
        expected_fields = {"can_act", "primitive"} if expected.get("can_act") is True else {"can_act"}
        if set(expected) != expected_fields:
            errors.append(f"line {line}: unsupported intent expectation fields")
        languages = {path.stem for path in (ROOT / "src/engine_lang/languages").glob("*.yaml")}
    else:
        return [*errors, f"line {line}: unsupported kind"]
    if not isinstance(row.get("language"), str) or row["language"] not in languages:
        errors.append(f"line {line}: unsupported language for {kind}")
    return errors


def _load_corpus(path: Path) -> tuple[list[dict], list[str], str | None]:
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
    except (OSError, UnicodeError) as error:
        return [], [f"Cannot read UTF-8 corpus: {type(error).__name__}: {error}"], None
    rows = []
    errors = []
    seen: set[str] = set()
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError as error:
            errors.append(f"line {line_number}: invalid JSON: {error}")
            continue
        errors.extend(_validate_row(row, line_number, seen))
        rows.append(row)
    if not rows:
        errors.append("Corpus contains no fixtures")
    return rows, errors, hashlib.sha256(raw).hexdigest()


def _evaluate_meaning(row: dict) -> tuple[str, bool, dict]:
    language = row["language"]
    target_language = row.get("target_language", language)
    source = parse_meaning(row["source"], language)
    candidate = parse_meaning(row["candidate"], target_language)
    actual = {
        "source_status": source.status,
        "candidate_status": candidate.status,
        "source_meaning": source.to_dict(),
        "candidate_meaning": candidate.to_dict(),
        "source_meaning_key": source.key(),
        "candidate_meaning_key": candidate.key(),
    }
    if source.status != "RESOLVED":
        actual["decision"] = "unresolved_source"
        return "abstain", False, actual
    if candidate.status != "RESOLVED":
        actual["decision"] = "unresolved_candidate"
        # A known negative safely rejected is not proof of its meaning.
        return "abstain", row["expected"]["relation"] == "different", actual
    comparison = compare_candidates(source, {target_language: row["candidate"]})
    accepted = comparison["semantic_passes"] > 0
    actual.update(comparison=comparison, decision="accepted" if accepted else "rejected")
    should_accept = row["expected"]["relation"] == "equivalent"
    if accepted == should_accept:
        return "passed", True, actual
    return ("false_accept" if accepted else "false_reject"), False, actual


def _evaluate_intent(row: dict) -> tuple[str, bool, dict]:
    intent = resolve(row["source"], row["language"])
    can_act = intent.can_act()
    try:
        lower_intent_to_program(intent)
    except ValueError as error:
        can_lower = False
        lower_error = str(error)
    else:
        can_lower = True
        lower_error = None
    actual = {
        "status": intent.status.value, "primitive": intent.primitive,
        "can_act": can_act, "can_lower": can_lower,
        "lower_error": lower_error, "intent": intent.to_dict(),
    }
    if row["expected"]["can_act"]:
        passed = can_act and can_lower and intent.primitive == row["expected"]["primitive"]
        if passed:
            return "passed", True, actual
        return ("abstain" if not can_act and not can_lower else "false_reject"), False, actual
    if can_act or can_lower:
        return "false_accept", False, actual
    return "abstain", True, actual


def _git(args: list[str]) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def _metadata(path: Path, digest: str | None) -> dict:
    packages = {}
    for name in ("wn", "simplemma", "jieba", "fugashi", "unidic-lite", "PyYAML"):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = None
    dirty = _git(["status", "--porcelain"])
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "git_commit": _git(["rev-parse", "HEAD"]),
        "git_dirty": None if dirty is None else bool(dirty),
        "corpus_path": str(path.resolve()), "corpus_sha256": digest,
        "python_version": platform.python_version(), "platform": platform.platform(),
        "cpu_count": os.cpu_count(), "package_versions": packages,
        "wordnet_data_directory": os.environ.get("WN_DATA_DIR", "default Wn directory"),
    }


def run_adversarial_benchmark(corpus_path: str) -> dict:
    """Validate the whole corpus first; run independent cases even after engine errors."""
    started = time.perf_counter()
    cpu_started = time.process_time()
    path = Path(corpus_path)
    rows, invalid, digest = _load_corpus(path)
    report: dict[str, Any] = {
        "schema": SCHEMA, "metadata": _metadata(path, digest),
        "cases": [], "counts": dict.fromkeys(("total", *OUTCOMES), 0),
        "invalid_fixtures": invalid, "infrastructure_errors": [],
    }
    if not invalid:
        for row in rows:
            result = dict(row)
            try:
                evaluator = _evaluate_meaning if row["kind"] == "meaning_pair" else _evaluate_intent
                outcome, passed, actual = evaluator(row)
            except Exception as error:  # evidence must survive one broken dependency/case
                outcome, passed, actual = "infrastructure_error", False, {}
                diagnostic = {
                    "case_id": row["case_id"], "error_type": type(error).__name__,
                    "error": str(error),
                }
                report["infrastructure_errors"].append(diagnostic)
                result["error"] = diagnostic
            result.update(outcome=outcome, passed=passed, actual=actual)
            report["cases"].append(result)
            report["counts"][outcome] += 1
        report["counts"]["total"] = len(rows)
    source_keys = {
        json.dumps(case["actual"]["source_meaning_key"], ensure_ascii=False)
        for case in report["cases"]
        if case["actual"].get("source_status") == "RESOLVED"
    }
    texts = []
    if not invalid:
        for row in rows:
            texts.append((row["language"], row["source"]))
            if row["kind"] == "meaning_pair":
                texts.append((row.get("target_language", row["language"]), row["candidate"]))
    report["statistics"] = {
        "records": len(rows), "evaluated_records": len(report["cases"]),
        "text_variants": len(texts), "unique_texts": len(set(texts)),
        "unique_resolved_source_meanings": len(source_keys),
        "source_predicates": dict(Counter(
            case["actual"]["source_meaning"]["predicate"]
            for case in report["cases"] if case["actual"].get("source_status") == "RESOLVED"
        )),
        "kinds": dict(Counter(row["kind"] for row in rows)) if not invalid else {},
        "phenomena": dict(Counter(row["phenomenon"] for row in rows)) if not invalid else {},
        "expectations": dict(Counter(
            f"{row['kind']}:{row['expected'].get('relation', 'can_act' if row['expected'].get('can_act') else 'cannot_act')}"
            for row in rows
        )) if not invalid else {},
        "languages": sorted({language for language, _ in texts}),
        "expectations_met": sum(case["passed"] for case in report["cases"]),
    }
    report["exit_code"] = (
        2 if invalid or report["infrastructure_errors"]
        else 1 if any(not case["passed"] for case in report["cases"])
        else 0
    )
    report["metadata"]["duration_seconds"] = time.perf_counter() - started
    report["metadata"]["cpu_seconds"] = time.process_time() - cpu_started
    return report


def format_report(report: dict) -> str:
    """Human-readable evidence, not a claim of general translation accuracy."""
    def cell(value: Any) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")

    lines = [
        "# IntentLang — benchmark adversarial R0", "",
        f"Commit: `{report['metadata']['git_commit']}`; dirty: {report['metadata']['git_dirty']}.",
        f"Corpus SHA-256: `{report['metadata']['corpus_sha256']}`.",
        f"Exit code: **{report['exit_code']}**. Ejecución: {report['metadata']['generated_at']}.", "",
        "Muestra dirigida de regresión; no estima precisión general ni mide generación de traducciones.", "",
        "| Resultado | Casos |", "|---|---:|",
    ]
    lines.extend(f"| {outcome} | {count} |" for outcome, count in report["counts"].items())
    lines.extend([
        "", "`passed` cuenta decisiones comprobadas. `abstain` queda separado aunque cumpla",
        "una expectativa de rechazo seguro; UNKNOWN no demuestra una diferencia semántica.", "",
        "| ID | Fenómeno | Origen | Candidato | Resultado | Expectativa cumplida |",
        "|---|---|---|---|---|---|",
    ])
    for case in report["cases"]:
        values = [case["case_id"], case["phenomenon"], case["source"],
                  case.get("candidate", "—"), case["outcome"], case["passed"]]
        lines.append("| " + " | ".join(cell(value) for value in values) + " |")
    for name in ("invalid_fixtures", "infrastructure_errors"):
        if report[name]:
            lines.extend(["", f"## {name}", ""])
            lines.extend(f"- {cell(error)}" for error in report[name])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", default=str(ROOT / "corpus/semantic/adversarial_regressions.jsonl"))
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    report = run_adversarial_benchmark(args.corpus)
    report["metadata"]["command"] = [sys.executable, *sys.argv]
    output = Path(args.output_dir)
    try:
        output.mkdir(parents=True, exist_ok=True)
        (output / "adversarial_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
        )
        (output / "adversarial_report.md").write_text(format_report(report), encoding="utf-8")
    except OSError as error:
        print(f"Cannot persist benchmark evidence: {error}", file=sys.stderr)
        return 2
    print(json.dumps({"counts": report["counts"], "exit_code": report["exit_code"],
                      "output": str(output)}, ensure_ascii=False))
    return report["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
