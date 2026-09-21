"""M1: language-independent Meaning IR contract."""
from __future__ import annotations

import pytest

from intentlang.meaning_ir import (
    Meaning,
    MeaningEntity,
    MeaningProvenance,
    MeaningRole,
    validate_meaning,
)


def meaning_fixture(
    *, language: str = "en", surface: str = "Alice was tired",
    polarity: str = "positive", tense: str = "past", aspect: str = "simple",
) -> Meaning:
    return Meaning(
        predicate="fatigue",
        roles=(MeaningRole("experiencer", entity="alice"),),
        polarity=polarity,
        tense=tense,
        aspect=aspect,
        modality="asserted",
        entities=(MeaningEntity("alice", "person.alice"),),
        provenance=MeaningProvenance(
            surface=surface,
            language=language,
            semantic_backend="fixture",
            confidence="gold",
            mode="strict",
            source_hash="fixture",
        ),
    )


def test_meaning_key_excludes_language_and_surface():
    english = meaning_fixture(language="en", surface="Alice was tired")
    spanish = meaning_fixture(language="es", surface="Alicia estaba cansada")

    assert english.key() == spanish.key()


def test_meaning_round_trips_without_losing_negation_or_aspect():
    value = meaning_fixture(polarity="negative", tense="past", aspect="perfect")

    restored = Meaning.from_dict(value.to_dict())

    assert restored == value
    assert restored.polarity == "negative"
    assert restored.aspect == "perfect"


def test_meaning_rejects_missing_predicate_and_invalid_status():
    with pytest.raises(ValueError, match="predicate"):
        validate_meaning({"schema": "meaning/1", "status": "RESOLVED"})

    invalid = meaning_fixture().to_dict()
    invalid["status"] = "MAYBE"
    with pytest.raises(ValueError, match="status"):
        validate_meaning(invalid)


def test_meaning_key_separates_agent_object_swap():
    first = meaning_fixture()
    swapped = Meaning(
        predicate=first.predicate,
        roles=(MeaningRole("experiencer", entity="watch"),),
        polarity=first.polarity,
        tense=first.tense,
        aspect=first.aspect,
        modality=first.modality,
        entities=(
            MeaningEntity("watch", "object.watch"),
            MeaningEntity("alice", "person.alice"),
        ),
        provenance=first.provenance,
    )

    assert first.key() != swapped.key()
