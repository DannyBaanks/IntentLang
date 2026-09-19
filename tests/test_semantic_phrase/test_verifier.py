"""Tests for M4 — Semantic Roundtrip Verifier."""
from __future__ import annotations

import pytest

from intentlang.translation_engine.semantic_phrase.verifier import (
    verify_roundtrip,
    format_verify_result,
)
from intentlang.translation_engine.semantic_phrase.phrase_ir import PhraseStatus


def test_identical_phrases_verified():
    """Identical source and target should pass verification."""
    result = verify_roundtrip(
        source="Close this workspace",
        target="Close this workspace",
    )
    assert result.passed is True
    assert result.verdict == PhraseStatus.VERIFIED.value
    assert result.pass_rate == 1.0


def test_semantically_equivalent_phrases():
    """Phrases with same semantic invariants should pass."""
    # Both are imperative commands with same modality
    result = verify_roundtrip(
        source="Close this workspace",
        target="Close this workspace now",
    )
    # Both should have same destructive, modality, etc.
    assert result.passed is True


def test_negation_mismatch_rejected():
    """Negation mismatch should fail verification."""
    result = verify_roundtrip(
        source="Do not delete this file",
        target="Delete this file",
    )
    assert result.passed is False
    assert result.verdict in (
        PhraseStatus.REJECTED.value,
        PhraseStatus.NEEDS_REVIEW.value,
    )
    # Find the negation check
    neg_check = next(c for c in result.checks if c.field == "negation")
    assert neg_check.passed is False


def test_modality_change_rejected():
    """Modality change should fail verification."""
    result = verify_roundtrip(
        source="You must save your changes",
        target="You may save your changes",
    )
    assert result.passed is False
    mod_check = next(c for c in result.checks if c.field == "modality")
    assert mod_check.passed is False


def test_destructive_change_rejected():
    """Destructive flag change should fail verification."""
    result = verify_roundtrip(
        source="This will permanently delete your account",
        target="This will archive your account",
    )
    assert result.passed is False
    dest_check = next(c for c in result.checks if c.field == "destructive")
    assert dest_check.passed is False


def test_slot_mismatch_rejected():
    """Slot/placeholder mismatch should fail verification."""
    result = verify_roundtrip(
        source="You have {count} unsaved changes",
        target="You have unsaved changes",
    )
    assert result.passed is False
    slot_check = next(c for c in result.checks if c.field == "slots")
    assert slot_check.passed is False


def test_protected_tokens_preserved():
    """Protected tokens should be compared."""
    result = verify_roundtrip(
        source="Press Ctrl+K to open",
        target="Press Ctrl+K to open",
    )
    token_check = next(c for c in result.checks if c.field == "protected_tokens")
    assert token_check.passed is True


def test_protected_tokens_mismatch():
    """Protected tokens mismatch should fail."""
    result = verify_roundtrip(
        source="Press Ctrl+K to open",
        target="Press Ctrl+J to open",
    )
    token_check = next(c for c in result.checks if c.field == "protected_tokens")
    assert token_check.passed is False


def test_backtranslation_as_auxiliary():
    """Backtranslation is auxiliary evidence, not authority."""
    # Use same language for backtranslation to ensure modality matches
    result = verify_roundtrip(
        source="Close this workspace",
        target="Close this workspace now",
        backtranslation="Close this workspace",
    )
    # Should still pass even with backtranslation
    assert result.passed is True
    assert result.verifier_mode == "lexical_plus_model"


def test_format_result():
    """Result formatting works correctly."""
    result = verify_roundtrip(
        source="Close this workspace",
        target="Close this workspace",
    )
    formatted = format_verify_result(result)
    assert "VERIFIED" in formatted
    assert "100.0%" in formatted


def test_evidence_hash_present():
    """Evidence hash is generated for all results."""
    result = verify_roundtrip(
        source="Test phrase",
        target="Test phrase",
    )
    assert result.evidence_hash is not None
    assert len(result.evidence_hash) == 16


def test_result_serialization():
    """Result serializes to dict correctly."""
    result = verify_roundtrip(
        source="Close workspace",
        target="Close workspace",
    )
    d = result.to_dict()
    assert d["verdict"] == "VERIFIED"
    assert d["pass_rate"] == 1.0
    assert len(d["checks"]) > 0
