"""M2 extended phenomena: each case must converge in four languages."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from ci.run_semantic_benchmark import run_m2_gate  # noqa: I001


EXTENDED_CASES = {
    "polarity_positive", "polarity_negative", "tense_past", "tense_present",
    "aspect_progressive", "aspect_perfect", "agent_alice", "agent_rabbit",
    "object_watch", "modality_must", "modality_may", "location_in",
    "source_pocket", "quantifier_none", "imperative_open",
}


def test_extended_m2_cases_converge_in_all_four_languages():
    report = run_m2_gate("corpus/semantic/meaning_m1.jsonl", case_ids=EXTENDED_CASES)

    assert report["records"] == len(EXTENDED_CASES)
    assert report["semantic_failures"] == 0, report["failures"]
