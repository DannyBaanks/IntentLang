"""M4: external candidates are scored by semantic identity, not string match."""
from __future__ import annotations

from intentlang.meaning_ir import Meaning
from intentlang.semantic_comparator import compare_candidates


def _expected() -> Meaning:
    return Meaning.from_dict({
        "schema": "meaning/1", "status": "RESOLVED", "predicate": "see",
        "roles": [
            {"name": "agent", "entity": "alice", "concept": None, "features": {}},
            {"name": "object", "entity": "rabbit", "concept": None, "features": {}},
        ],
        "polarity": "positive", "tense": "past", "aspect": "simple", "modality": "asserted",
        "entities": [
            {"id": "alice", "concept": "person.alice", "features": {}},
            {"id": "rabbit", "concept": "animal.rabbit", "features": {}},
        ],
        "provenance": {"surface": "fixture", "language": "und", "semantic_backend": "gold", "confidence": "gold", "mode": "strict", "source_hash": "x"},
    })


def test_comparator_accepts_semantically_equivalent_candidate():
    report = compare_candidates(_expected(), {"en": "Alice saw the rabbit", "es": "Alicia vio al conejo"})
    assert report["languages"] == 2
    assert report["semantic_passes"] == 2
    assert report["semantic_failures"] == 0


def test_comparator_classifies_polarity_drift_and_unknown_output():
    report = compare_candidates(_expected(), {"en": "Alice did not see the rabbit", "ja": "意味不明"})
    assert report["semantic_passes"] == 0
    assert report["semantic_failures"] == 2
    assert {failure["reason"] for failure in report["failures"]} == {"meaning_mismatch", "unresolved"}
