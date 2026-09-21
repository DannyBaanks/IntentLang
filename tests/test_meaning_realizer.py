"""M3: realization must preserve Meaning IR under back-translation."""
from __future__ import annotations

import json
from pathlib import Path

from intentlang.meaning_ir import Meaning
from intentlang.meaning_parser import parse_meaning
from intentlang.meaning_realizer import realize_meaning

BASE_CASES = {"alice_tired", "rabbit_watch", "drink_me", "nothing_remarkable", "court_before"}


def _meanings():
    rows = [json.loads(line) for line in Path("corpus/semantic/meaning_m1.jsonl").read_text(encoding="utf-8").splitlines()]
    return {row["case_id"]: Meaning.from_dict(row["expected_meaning"]) for row in rows if row["case_id"] in BASE_CASES}


def test_realizer_backtranslates_the_base_cases_into_four_languages():
    for meaning in _meanings().values():
        for language in ("en", "es", "ja", "zh"):
            output = realize_meaning(meaning, language)
            assert output, (meaning.predicate, language)
            restored = parse_meaning(output, language)
            assert restored.status == meaning.status
            assert restored.key() == meaning.key(), (meaning.predicate, language, output)


def test_realizer_returns_none_for_unknown_meaning():
    unknown = Meaning.from_dict({
        "schema": "meaning/1", "status": "UNKNOWN", "predicate": None, "roles": [],
        "polarity": "unknown", "tense": None, "aspect": None, "modality": None,
        "entities": [],
        "provenance": {"surface": "x", "language": "en", "semantic_backend": "test", "confidence": "gold", "mode": "strict", "source_hash": "x"},
    })

    assert realize_meaning(unknown, "es") is None
