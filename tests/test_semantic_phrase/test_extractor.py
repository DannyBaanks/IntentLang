"""Tests for M2 — Semantic Extractor."""
from __future__ import annotations

import pytest

from intentlang.translation_engine.semantic_phrase.extractor import (
    extract_semantics,
    ExtractedFacts,
)


def test_negation_detected():
    """Negation markers are detected."""
    facts = extract_semantics("Do not delete this file")
    assert facts.negated is True
    assert "do not" in [m.lower() for m in facts.negation_markers]


def test_no_negation():
    """Positive phrases have no negation."""
    facts = extract_semantics("Save your changes")
    assert facts.negated is False
    assert len(facts.negation_markers) == 0


def test_modal_must():
    """Strong modal is detected."""
    facts = extract_semantics("You must save before closing")
    assert facts.modality == "MUST"
    assert len(facts.modal_markers) > 0


def test_modal_should():
    """Recommendation modal is detected."""
    facts = extract_semantics("You should save your work")
    assert facts.modality == "SHOULD"


def test_modal_may():
    """Permission modal is detected."""
    facts = extract_semantics("You may continue without saving")
    assert facts.modality in ("MAY", "CAN")


def test_modal_will():
    """Future modal is detected."""
    facts = extract_semantics("This will delete your data")
    assert facts.modality == "WILL"


def test_imperative_modal():
    """Imperative mood detected as MUST."""
    facts = extract_semantics("Save your work now")
    assert facts.modality == "MUST"
    assert "imperative" in facts.modal_markers


def test_destructive_detected():
    """Destructive keywords are detected."""
    facts = extract_semantics("This will permanently delete your account")
    assert facts.destructive is True
    assert "delete" in facts.destructive_keywords


def test_no_destructive():
    """Non-destructive phrases have no destructive flag."""
    facts = extract_semantics("Your changes have been saved")
    assert facts.destructive is False


def test_warning_detected():
    """Warning keywords are detected."""
    facts = extract_semantics("Warning: This action cannot be undone")
    assert facts.is_warning is True
    assert "warning" in [w.lower() for w in facts.warning_keywords]


def test_confirmation_detected():
    """Confirmation requirements are detected."""
    facts = extract_semantics("Are you sure you want to delete this?")
    assert facts.is_confirmation is True


def test_conditions_extracted():
    """Conditional clauses are extracted."""
    facts = extract_semantics("If enabled, data will sync automatically")
    assert len(facts.conditions) > 0


def test_consequences_extracted():
    """Consequence phrases are extracted."""
    facts = extract_semantics("This will permanently delete all data")
    assert len(facts.consequences) > 0


def test_numbers_extracted():
    """Numeric quantities are extracted."""
    facts = extract_semantics("Delete 10 files permanently")
    assert "10" in facts.numbers


def test_units_extracted():
    """Units are extracted."""
    facts = extract_semantics("Upload 5 MB of data")
    assert "MB" in facts.units


def test_shortcuts_extracted():
    """Keyboard shortcuts are extracted."""
    facts = extract_semantics("Press Ctrl+K to open")
    assert "Ctrl+K" in facts.protected_tokens


def test_technical_terms_extracted():
    """Technical terms are extracted."""
    facts = extract_semantics("This API returns JSON data")
    assert "API" in facts.technical_terms
    assert "JSON" in facts.technical_terms


def test_slots_extracted():
    """Template slots are extracted."""
    facts = extract_semantics("You have {{count}} unsaved changes")
    assert "{{count}}" in facts.slots


def test_observed_facts_recorded():
    """Observed facts are recorded."""
    facts = extract_semantics("Warning: Do not delete this file")
    assert len(facts.facts) > 0
    assert any("negation" in f for f in facts.facts)
    assert any("destructive" in f for f in facts.facts)
    assert any("warning" in f for f in facts.facts)


def test_inferred_candidates_recorded():
    """Inferred candidates are recorded."""
    facts = extract_semantics("Warning: This will delete your data")
    assert len(facts.candidates) > 0


def test_complex_phrase():
    """Complex phrase extracts multiple features."""
    facts = extract_semantics(
        "Warning: If you close this workspace, all unsaved changes "
        "will be permanently deleted. This action cannot be undone."
    )
    # "cannot" is correctly detected as a negation marker
    # (describing what cannot be done, not negating the main action)
    assert facts.negated is True
    assert facts.destructive is True
    assert facts.is_warning is True
    assert len(facts.consequences) > 0


def test_extracted_facts_serialization():
    """ExtractedFacts serializes to dict correctly."""
    facts = extract_semantics("Warning: Delete this file")
    d = facts.to_dict()
    assert d["source_surface"] == "Warning: Delete this file"
    assert d["destructive"] is True
    assert d["is_warning"] is True
