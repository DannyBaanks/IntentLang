"""M0: reproducibility and failure classification for semantic benchmarks."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from ci.run_semantic_benchmark import classify_case, run_benchmark


def test_benchmark_classifies_missing_dependency_without_calling_it_unknown():
    result = classify_case("ja", "text", RuntimeError("missing fugashi"))

    assert result["status"] == "DEPENDENCY_BLOCKED"


def test_benchmark_report_is_deterministic_except_for_timestamp(tmp_path):
    first = run_benchmark(str(tmp_path / "one"))
    second = run_benchmark(str(tmp_path / "two"))

    assert first["cases"] == second["cases"]
