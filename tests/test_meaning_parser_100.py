"""M2 volume gate: 100 annotated simple-event sentences."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from ci.run_semantic_benchmark import run_m2_gate


def test_m2_reaches_100_cases_without_semantic_failures():
    report = run_m2_gate("corpus/semantic/meaning_m1.jsonl")

    assert report["records"] == 100
    assert report["semantic_failures"] == 0, report["failures"]
