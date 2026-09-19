"""Tests for M1 — Phrase IR schema and hashing."""
from __future__ import annotations

import pytest

from intentlang.translation_engine.semantic_phrase.phrase_ir import (
    PhraseIR,
    PhraseStatus,
    SpeechAct,
    Modality,
    Provenance,
    generate_phrase_id,
)


def test_phrase_ir_stable_hash():
    """Two phrases with same semantic meaning produce same hash."""
    ir1 = PhraseIR(
        speech_act="WARNING",
        action="close",
        object="WORKSPACE",
        polarity="assertive",
        modality="WILL",
        destructive=True,
        consequences=["discard_unsaved_changes"],
    )
    ir2 = PhraseIR(
        speech_act="WARNING",
        action="close",
        object="WORKSPACE",
        polarity="assertive",
        modality="WILL",
        destructive=True,
        consequences=["discard_unsaved_changes"],
    )
    assert ir1.semantic_hash() == ir2.semantic_hash()


def test_phrase_ir_different_semantics_different_hash():
    """Phrases with different semantics produce different hashes."""
    ir1 = PhraseIR(speech_act="WARNING", destructive=True)
    ir2 = PhraseIR(speech_act="WARNING", destructive=False)
    assert ir1.semantic_hash() != ir2.semantic_hash()


def test_phrase_ir_missing_optional_fields():
    """IR with missing optional fields still hashes correctly."""
    ir = PhraseIR(speech_act="STATEMENT")
    h = ir.semantic_hash()
    assert len(h) == 16  # SHA-256 truncated to 16 chars


def test_phrase_ir_explicit_unknown():
    """IR with explicit UNKNOWN fields hashes correctly."""
    ir = PhraseIR(
        speech_act=SpeechAct.UNKNOWN.value,
        modality=Modality.UNKNOWN.value,
    )
    h = ir.semantic_hash()
    assert len(h) == 16


def test_phrase_ir_slots_preserved():
    """Slots are included in semantic hash."""
    ir1 = PhraseIR(slots=["count", "name"])
    ir2 = PhraseIR(slots=["name", "count"])  # different order
    assert ir1.semantic_hash() == ir2.semantic_hash()  # sorted


def test_phrase_ir_protected_tokens_preserved():
    """Protected tokens are included in semantic hash."""
    ir1 = PhraseIR(protected_tokens=["Ctrl+K"])
    ir2 = PhraseIR(protected_tokens=["Ctrl+J"])
    assert ir1.semantic_hash() != ir2.semantic_hash()


def test_phrase_ir_technical_terms_preserved():
    """Technical terms are included in semantic hash."""
    ir1 = PhraseIR(technical_terms=["API", "JSON"])
    ir2 = PhraseIR(technical_terms=["API", "XML"])
    assert ir1.semantic_hash() != ir2.semantic_hash()


def test_phrase_ir_serialization_roundtrip():
    """IR serializes to dict and back correctly."""
    ir = PhraseIR(
        speech_act="WARNING",
        action="close",
        object="WORKSPACE",
        polarity="assertive",
        modality="WILL",
        destructive=True,
        consequences=["discard_unsaved_changes"],
        protected_tokens=["Ctrl+K"],
        technical_terms=["API"],
        provenance=Provenance(
            source_hash="abc123",
            source_locale="en",
            target_locale="es",
        ),
    )
    d = ir.to_dict()
    ir2 = PhraseIR.from_dict(d)
    assert ir2.speech_act == "WARNING"
    assert ir2.destructive is True
    assert ir2.protected_tokens == ["Ctrl+K"]
    assert ir2.provenance.source_hash == "abc123"


def test_phrase_ir_is_verified():
    """is_verified returns True for verified statuses."""
    ir = PhraseIR(status=PhraseStatus.VERIFIED.value)
    assert ir.is_verified() is True

    ir2 = PhraseIR(status=PhraseStatus.VERIFIED_WITH_LIMITATIONS.value)
    assert ir2.is_verified() is True

    ir3 = PhraseIR(status=PhraseStatus.NEEDS_REVIEW.value)
    assert ir3.is_verified() is False


def test_phrase_ir_needs_review():
    """needs_review returns True for review statuses."""
    ir = PhraseIR(status=PhraseStatus.NEEDS_REVIEW.value)
    assert ir.needs_review() is True

    ir2 = PhraseIR(status=PhraseStatus.AMBIGUOUS.value)
    assert ir2.needs_review() is True

    ir3 = PhraseIR(status=PhraseStatus.VERIFIED.value)
    assert ir3.needs_review() is False


def test_generate_phrase_id_deterministic():
    """Same input produces same ID."""
    id1 = generate_phrase_id("Hello world", "en")
    id2 = generate_phrase_id("Hello world", "en")
    assert id1 == id2


def test_generate_phrase_id_different_inputs():
    """Different inputs produce different IDs."""
    id1 = generate_phrase_id("Hello world", "en")
    id2 = generate_phrase_id("Hello world", "es")
    assert id1 != id2
