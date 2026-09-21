"""Reproducible M0 benchmark for semantic translation work.

The runner deliberately separates infrastructure failures from semantic
outcomes.  It is small enough to run in CI and is the first gate before adding
Meaning IR behavior.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from intentlang.meaning_ir import Meaning, validate_meaning
from intentlang.meaning_parser import parse_meaning
from intentlang.meaning_realizer import realize_meaning
from intentlang.resolve import resolve
from intentlang.translation_engine.materializer import _materialize_text

CORPUS_VERSION = "m0-alice-controls-1"
CORPUS_SOURCE = {
    "title": "Alice's Adventures in Wonderland",
    "url": "https://www.gutenberg.org/ebooks/11",
    "license": "public-domain-us",
}

CASES: tuple[dict[str, Any], ...] = (
    {"case_id": "copy-en", "lang": "en", "text": "copy the file", "expected": "COPY"},
    {"case_id": "copy-es", "lang": "es", "text": "copia el archivo", "expected": "COPY"},
    {"case_id": "copy-zh", "lang": "zh", "text": "复制 文件", "expected": "COPY"},
    {
        "case_id": "alice-prose-en",
        "lang": "en",
        "text": "Alice was beginning to get very tired",
        "expected": None,
    },
)

SEPARATION_PAIRS = (
    ("polarity_positive", "polarity_negative"),
    ("tense_past", "tense_present"),
    ("aspect_progressive", "aspect_perfect"),
    ("agent_alice", "agent_rabbit"),
)


def classify_case(
    language: str,
    text: str,
    error: BaseException | None = None,
    *,
    status: str | None = None,
    primitive: str | None = None,
    expected: str | None = None,
) -> dict[str, Any]:
    """Return a stable benchmark row without hiding failures."""
    row: dict[str, Any] = {"lang": language, "text": text}
    if error is not None:
        message = str(error).lower()
        if any(token in message for token in ("dependency", "fugashi", "wordnet", "lexicon")):
            row["status"] = "DEPENDENCY_BLOCKED"
        else:
            row["status"] = "INFRASTRUCTURE_FAILURE"
        row["error_type"] = type(error).__name__
        row["error"] = str(error)
        return row

    row["status"] = status or "UNKNOWN"
    row["primitive"] = primitive
    if expected is not None:
        row["expected"] = expected
        if row["status"] == "RESOLVED" and primitive == expected:
            row["status"] = "PASS"
        elif row["status"] == "RESOLVED":
            row["status"] = "SEMANTIC_FAILURE"
    return row


def _source_hash() -> str:
    payload = json.dumps(CASES, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def run_m1_gate(corpus_path: str) -> dict[str, Any]:
    """Validate the fixture-level M1 invariants for a semantic corpus."""
    records = [
        json.loads(line)
        for line in Path(corpus_path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    by_id = {record.get("case_id"): record for record in records}
    schema_failures: list[dict[str, Any]] = []
    identity_failures: list[dict[str, Any]] = []
    convergence_failures: list[dict[str, Any]] = []
    meanings: dict[str, Meaning] = {}
    for record in records:
        case_id = record.get("case_id", "<missing>")
        try:
            expected = record.get("expected_meaning")
            if expected is None:
                expected = by_id[record["expected_meaning_ref"]]["expected_meaning"]
            validate_meaning(expected)
            meaning = Meaning.from_dict(expected)
            meanings[case_id] = meaning
            if meaning.key() != Meaning.from_dict(meaning.to_dict()).key():
                identity_failures.append({"case_id": case_id, "reason": "roundtrip key changed"})
        except (KeyError, TypeError, ValueError) as exc:
            schema_failures.append({"case_id": case_id, "error": str(exc)})
        variants = record.get("variants", {})
        if set(variants) != {"en", "es", "ja", "zh"}:
            convergence_failures.append({"case_id": case_id, "languages": sorted(variants)})

    separation_failures: list[dict[str, Any]] = []
    for left, right in SEPARATION_PAIRS:
        if left in meanings and right in meanings and meanings[left].key() == meanings[right].key():
            separation_failures.append({"left": left, "right": right})
    return {
        "records": len(records),
        "schema_failures": len(schema_failures),
        "identity_failures": len(identity_failures),
        "separation_failures": len(separation_failures),
        "convergence_failures": len(convergence_failures),
        "failures": schema_failures + identity_failures + separation_failures + convergence_failures,
    }


def run_m2_gate(corpus_path: str, case_ids: set[str] | None = None) -> dict[str, Any]:
    """Run the real parser against selected gold-aligned corpus records."""
    records = [
        json.loads(line)
        for line in Path(corpus_path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if case_ids is not None:
        records = [record for record in records if record.get("case_id") in case_ids]
    by_id = {record.get("case_id"): record for record in records}
    failures: list[dict[str, Any]] = []
    resolved = 0
    for record in records:
        expected_data = record.get("expected_meaning")
        if expected_data is None:
            expected_data = by_id[record["expected_meaning_ref"]]["expected_meaning"]
        expected = Meaning.from_dict(expected_data)
        variant_failures = []
        for language, text in record.get("variants", {}).items():
            actual = parse_meaning(text, language)
            if actual.key() != expected.key() or actual.status != expected.status:
                variant_failures.append({
                    "language": language,
                    "actual_status": actual.status,
                    "actual_key": actual.key(),
                    "expected_key": expected.key(),
                })
        if variant_failures:
            failures.append({"case_id": record["case_id"], "variants": variant_failures})
        else:
            resolved += 1
    return {"records": len(records), "resolved": resolved,
            "semantic_failures": len(failures), "failures": failures}


def run_m3_gate(corpus_path: str, case_ids: set[str] | None = None) -> dict[str, Any]:
    """Realize each gold meaning and verify back-translation in four languages."""
    all_records = [
        json.loads(line)
        for line in Path(corpus_path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    selected = [record for record in all_records if case_ids is None or record.get("case_id") in case_ids]
    by_id = {record.get("case_id"): record for record in all_records}
    failures: list[dict[str, Any]] = []
    checks = 0
    for record in selected:
        expected_data = record.get("expected_meaning")
        if expected_data is None:
            expected_data = by_id[record["expected_meaning_ref"]]["expected_meaning"]
        expected = Meaning.from_dict(expected_data)
        for language in ("en", "es", "ja", "zh"):
            checks += 1
            output = realize_meaning(expected, language)
            actual = parse_meaning(output, language) if output else None
            matches = (
                output is None
                if expected.status == "UNKNOWN"
                else actual is not None and actual.status == expected.status and actual.key() == expected.key()
            )
            if not matches:
                failures.append({
                    "case_id": record["case_id"], "language": language,
                    "output": output, "expected_status": expected.status,
                    "actual_status": actual.status if actual else None,
                })
    return {"records": len(selected), "checks": checks,
            "semantic_failures": len(failures), "failures": failures}


def run_benchmark(output_dir: str) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []

    for case in CASES:
        try:
            intent = resolve(case["text"], case["lang"])
            row = classify_case(
                case["lang"],
                case["text"],
                status=intent.status.value,
                primitive=intent.primitive,
                expected=case["expected"],
            )
        except Exception as exc:  # benchmark must report, not abort, one language
            row = classify_case(case["lang"], case["text"], exc)
        rows.append({"case_id": case["case_id"], **row})

    materializer = [
        {
            "case_id": "alice-prose-en",
            "target": target,
            "output": _materialize_text(CASES[-1]["text"], target, "benchmark"),
        }
        for target in ("es", "ja", "zh")
    ]
    report: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "corpus_version": CORPUS_VERSION,
        "corpus_source": CORPUS_SOURCE,
        "source_hash": _source_hash(),
        "cases": rows,
        "materializer": materializer,
    }
    (output / "benchmark_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    readable = [
        "# Semantic benchmark report",
        "",
        f"Corpus: {CORPUS_VERSION}",
        f"Source hash: `{report['source_hash']}`",
        "",
        "| Case | Language | Status | Primitive |",
        "|---|---|---|---|",
    ]
    readable.extend(
        f"| {row['case_id']} | {row['lang']} | {row['status']} | {row.get('primitive') or '—'} |"
        for row in rows
    )
    readable.extend(["", "## Materializer", ""])
    readable.extend(f"- `{row['target']}`: `{row['output']}`" for row in materializer)
    (output / "BENCHMARK_REPORT.md").write_text("\n".join(readable) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the IntentLang M0 semantic benchmark")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    report = run_benchmark(args.output_dir)
    print(json.dumps({"cases": len(report["cases"]), "output": args.output_dir}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
