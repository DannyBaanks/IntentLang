"""R0: the detector must expose failures rather than bless the current engine."""
from __future__ import annotations

import importlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_r0_runner_exists():
    assert importlib.util.find_spec("ci.run_adversarial_benchmark") is not None, (
        "R0 needs an importable adversarial benchmark runner"
    )


@pytest.fixture
def runner():
    assert importlib.util.find_spec("ci.run_adversarial_benchmark") is not None, (
        "R0 needs an importable adversarial benchmark runner"
    )
    return importlib.import_module("ci.run_adversarial_benchmark")


def pair(case_id="pair", *, relation="equivalent", candidate=None):
    return {
        "case_id": case_id,
        "kind": "meaning_pair",
        "phenomenon": "roles",
        "language": "en",
        "source": "Alice saw the rabbit",
        "candidate": candidate or "Alice saw the rabbit",
        "expected": {"relation": relation},
    }


def intent(case_id="intent", *, can_act=True):
    expected = {"can_act": can_act}
    if can_act:
        expected["primitive"] = "COPY"
    return {
        "case_id": case_id,
        "kind": "intent_surface",
        "phenomenon": "direct_order",
        "language": "es",
        "source": "copia el archivo" if can_act else "qwertzuiop el archivo",
        "expected": expected,
    }


def corpus(tmp_path, rows):
    path = tmp_path / "cases.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return str(path)


def test_runner_detects_a_false_accept_without_freezing_a_parser_bug(runner, tmp_path, monkeypatch):
    # Simulate a blind evaluator; fixing production should never break this detector test.
    monkeypatch.setattr(runner, "compare_candidates", lambda *_: {
        "semantic_passes": 1, "failures": [],
    })
    report = runner.run_adversarial_benchmark(corpus(tmp_path, [pair(
        relation="different", candidate="Alice did not see the rabbit",
    )]))
    assert report["counts"]["false_accept"] == 1
    assert report["cases"][0]["passed"] is False
    assert report["exit_code"] == 1


def test_real_positive_and_negative_controls(runner, tmp_path):
    report = runner.run_adversarial_benchmark(corpus(tmp_path, [
        pair("positive"),
        pair("negative", relation="different", candidate="Alice did not see the rabbit"),
    ]))
    assert report["counts"]["total"] == 2
    assert report["counts"]["passed"] == 2
    assert report["exit_code"] == 0


def test_equivalent_unknown_is_abstention_not_equivalence(runner, tmp_path):
    report = runner.run_adversarial_benchmark(corpus(tmp_path, [
        pair(candidate="Completely unsupported sentence"),
    ]))
    assert report["counts"]["abstain"] == 1
    assert report["cases"][0]["passed"] is False
    assert report["exit_code"] == 1


def test_negative_unknown_is_a_safe_rejection_not_proven_difference(runner, tmp_path):
    report = runner.run_adversarial_benchmark(corpus(tmp_path, [
        pair(relation="different", candidate="Completely unsupported sentence"),
    ]))
    assert report["counts"]["abstain"] == 1
    assert report["counts"]["passed"] == 0
    assert report["cases"][0]["passed"] is True
    assert report["exit_code"] == 0


def test_unsupported_source_does_not_validate_a_negative_pair(runner, tmp_path):
    row = pair(relation="different")
    row["source"] = "Unsupported source sentence"
    report = runner.run_adversarial_benchmark(corpus(tmp_path, [row]))
    assert report["counts"]["abstain"] == 1
    assert report["cases"][0]["passed"] is False
    assert report["exit_code"] == 1


@pytest.mark.parametrize("rows", [
    [], [pair(), pair()], [{"case_id": "broken"}],
    [{**pair(), "kind": "unknown"}],
    [{**pair(), "expected": {"relation": "maybe"}}],
    [{**intent(), "expected": {"can_act": "false"}}],
    [{**intent(), "expected": {"can_act": True}}],
    [{**pair(), "language": "not-a-supported-language"}],
    [{**pair(), "source": " "}],
    [{**pair(), "target_language": 42}],
    [{**pair(), "target_language": ["es"]}],
    [{**pair(), "language": ["en"]}],
    [{**pair(), "expected": {"relation": "equivalent", "extra_guarantee": True}}],
])
def test_invalid_fixtures_fail_before_any_evaluation(runner, tmp_path, rows, monkeypatch):
    def unexpected_evaluation(*_):
        pytest.fail("Invalid corpus must not partially evaluate")
    monkeypatch.setattr(runner, "parse_meaning", unexpected_evaluation)
    report = runner.run_adversarial_benchmark(corpus(tmp_path, rows))
    assert report["invalid_fixtures"]
    assert report["cases"] == []
    assert report["exit_code"] == 2


def test_malformed_json_and_missing_corpus_produce_diagnostics(runner, tmp_path):
    path = tmp_path / "invalid.jsonl"
    path.write_text('{"case_id":\n', encoding="utf-8")
    for source in (str(path), str(tmp_path / "absent.jsonl")):
        report = runner.run_adversarial_benchmark(source)
        assert report["invalid_fixtures"]
        assert report["exit_code"] == 2


def test_missing_wordnet_is_infrastructure_and_remaining_cases_run(runner, tmp_path, monkeypatch):
    from intentlang.lexicon import LexiconUnavailable

    def missing_resource(*_):
        raise LexiconUnavailable("missing test WordNet")
    monkeypatch.setattr(runner, "resolve", missing_resource)
    report = runner.run_adversarial_benchmark(corpus(tmp_path, [intent(), pair()]))
    assert report["counts"]["total"] == 2
    assert report["counts"]["passed"] == 1
    assert report["counts"]["infrastructure_error"] == 1
    assert report["infrastructure_errors"][0]["error_type"] == "LexiconUnavailable"
    assert report["exit_code"] == 2


def test_intents_check_lowering_without_executing_capabilities(runner, tmp_path):
    report = runner.run_adversarial_benchmark(corpus(tmp_path, [intent(), intent("unknown", can_act=False)]))
    assert report["exit_code"] == 0
    positive, negative = report["cases"]
    assert positive["actual"]["can_lower"] is True
    assert negative["actual"]["can_lower"] is False
    assert negative["actual"]["status"] == "UNKNOWN"


def test_lowering_bypass_is_a_false_accept_even_if_can_act_is_false(runner, tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "lower_intent_to_program", lambda _: object())
    report = runner.run_adversarial_benchmark(corpus(tmp_path, [intent(can_act=False)]))
    assert report["counts"]["false_accept"] == 1
    assert report["cases"][0]["actual"]["can_lower"] is True


def test_report_has_reproducibility_metadata_and_separate_denominators(runner, tmp_path):
    path = corpus(tmp_path, [pair("one"), pair("two")])
    report = runner.run_adversarial_benchmark(path)
    assert report["schema"] == "adversarial-benchmark/1"
    assert len(report["metadata"]["corpus_sha256"]) == 64
    assert report["metadata"]["git_commit"]
    assert report["metadata"]["python_version"]
    assert report["metadata"]["duration_seconds"] >= 0
    assert report["statistics"]["records"] == 2
    assert report["statistics"]["text_variants"] == 4
    assert report["statistics"]["unique_texts"] == 1
    assert report["statistics"]["unique_resolved_source_meanings"] == 1
    assert report["statistics"]["phenomena"] == {"roles": 2}
    assert report["statistics"]["source_predicates"] == {"see": 2}
    assert report["statistics"]["expectations"] == {"meaning_pair:equivalent": 2}


def test_cross_language_candidate_uses_its_target_language(runner, tmp_path):
    row = {**pair(candidate="Alicia vio al conejo"), "target_language": "es"}
    report = runner.run_adversarial_benchmark(corpus(tmp_path, [row]))
    assert report["exit_code"] == 0
    assert report["cases"][0]["actual"]["candidate_status"] == "RESOLVED"


@pytest.mark.parametrize("rows,expected_exit", [
    ([pair()], 0),
    ([pair(relation="different")], 1),  # Deliberately inconsistent gold checks the CLI's gate.
    ([], 2),
])
def test_cli_exit_status_matches_current_report(runner, tmp_path, rows, expected_exit):
    path = corpus(tmp_path, rows)
    output = tmp_path / "report"
    result = subprocess.run([
        sys.executable, str(ROOT / "ci/run_adversarial_benchmark.py"),
        "--corpus", path, "--output-dir", str(output),
    ], cwd=ROOT, check=False, capture_output=True, text=True)
    assert result.returncode == expected_exit, result.stderr
    report = json.loads((output / "adversarial_report.json").read_text())
    assert report["exit_code"] == expected_exit
    assert report["metadata"]["command"]
    assert (output / "adversarial_report.md").exists()


def test_cli_empty_wordnet_directory_is_exit_two(tmp_path, runner):
    path = corpus(tmp_path, [intent()])
    env = dict(os.environ, WN_DATA_DIR=str(tmp_path / "empty-wordnet"))
    output = tmp_path / "report"
    result = subprocess.run([
        sys.executable, str(ROOT / "ci/run_adversarial_benchmark.py"),
        "--corpus", path, "--output-dir", str(output),
    ], env=env, cwd=ROOT, check=False, capture_output=True, text=True)
    assert result.returncode == 2, result.stderr
    report = json.loads((output / "adversarial_report.json").read_text())
    assert report["counts"]["infrastructure_error"] == 1
    assert report["counts"]["false_accept"] == 0


def test_checked_in_corpus_has_controls_and_recorded_audit_cases(runner):
    rows = [json.loads(line) for line in (
        ROOT / "corpus/semantic/adversarial_regressions.jsonl"
    ).read_text().splitlines() if line.strip()]
    assert len({row["case_id"] for row in rows}) == len(rows)
    assert sum(row["kind"] == "meaning_pair" and row["expected"]["relation"] == "different" for row in rows) >= 7
    assert sum(row["kind"] == "meaning_pair" and row["expected"]["relation"] == "equivalent" for row in rows) >= 4
    assert sum(row["kind"] == "intent_surface" for row in rows) >= 6
    assert any(row.get("target_language") == "es" for row in rows)
