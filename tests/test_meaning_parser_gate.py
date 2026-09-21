"""M2 gate for the currently implemented simple-event parser rules."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from ci.run_semantic_benchmark import run_m2_gate


def test_m2_gate_parses_the_five_book_seed_cases():
    report = run_m2_gate(
        "corpus/semantic/meaning_m1.jsonl",
        case_ids={"alice_tired", "rabbit_watch", "drink_me", "nothing_remarkable", "court_before"},
    )

    assert report["records"] == 5
    assert report["semantic_failures"] == 0
    assert report["resolved"] == 5


def test_m2_gate_reports_misaligned_cases_instead_of_hiding_them(tmp_path):
    source = {
        "case_id": "misaligned",
        "variants": {"en": "Alice blorps the rabbit", "es": "Alicia blorpea al conejo", "ja": "アリスはウサギをブロープした", "zh": "爱丽丝对兔子进行了布洛普"},
        "expected_meaning": {
            "schema": "meaning/1", "status": "RESOLVED", "predicate": "see", "roles": [],
            "polarity": "positive", "tense": "past", "aspect": "simple", "modality": "asserted",
            "entities": [],
            "provenance": {"surface": "fixture", "language": "und", "semantic_backend": "gold", "confidence": "gold", "mode": "strict", "source_hash": "misaligned"},
        },
    }
    corpus = tmp_path / "misaligned.jsonl"
    corpus.write_text(json.dumps(source, ensure_ascii=False) + "\n", encoding="utf-8")
    report = run_m2_gate(str(corpus))

    assert report["records"] == 1
    assert report["semantic_failures"] == 1
