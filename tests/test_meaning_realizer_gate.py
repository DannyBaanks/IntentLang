"""M3 gate: realization and back-translation preserve the corpus meaning."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from ci.run_semantic_benchmark import run_m3_gate


def test_m3_realization_gate_covers_the_full_corpus():
    report = run_m3_gate("corpus/semantic/meaning_m1.jsonl")
    assert report["records"] == 100
    assert report["checks"] == 400
    assert report["semantic_failures"] == 0, report["failures"]
