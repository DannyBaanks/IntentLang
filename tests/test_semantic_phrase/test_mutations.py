"""Tests for M5 — Mutation Harness."""
from __future__ import annotations

import pytest

from intentlang.translation_engine.semantic_phrase.mutations import (
    run_mutation_harness,
    build_mutation_catalog,
    format_mutation_result,
)


def test_mutation_catalog_has_mutations():
    """Mutation catalog contains mutations."""
    catalog = build_mutation_catalog()
    assert len(catalog) > 0


def test_mutation_catalog_has_categories():
    """Each mutation has a category."""
    catalog = build_mutation_catalog()
    for mutation in catalog:
        assert mutation.category
        assert mutation.expected_detection


def test_mutation_harness_runs():
    """Mutation harness runs without errors."""
    result = run_mutation_harness()
    assert result.total_mutations > 0


def test_mutation_harness_detects_negation():
    """Negation removal mutation is detected."""
    from intentlang.translation_engine.semantic_phrase.extractor import extract_semantics
    from intentlang.translation_engine.semantic_phrase.verifier import verify_roundtrip

    source = "Do not delete this file"
    mutated = "Delete this file"

    source_extracted = extract_semantics(source)
    target_extracted = extract_semantics(mutated)

    result = verify_roundtrip(
        source=source,
        target=mutated,
        source_extracted=source_extracted,
        target_extracted=target_extracted,
    )

    # Should not be VERIFIED
    assert result.verdict != "VERIFIED"


def test_mutation_harness_detects_modality():
    """Modality change mutation is detected."""
    from intentlang.translation_engine.semantic_phrase.extractor import extract_semantics
    from intentlang.translation_engine.semantic_phrase.verifier import verify_roundtrip

    source = "You must save your changes"
    mutated = "You may save your changes"

    source_extracted = extract_semantics(source)
    target_extracted = extract_semantics(mutated)

    result = verify_roundtrip(
        source=source,
        target=mutated,
        source_extracted=source_extracted,
        target_extracted=target_extracted,
    )

    # Should not be VERIFIED
    assert result.verdict != "VERIFIED"


def test_mutation_harness_detects_slot_loss():
    """Placeholder loss mutation is detected."""
    from intentlang.translation_engine.semantic_phrase.extractor import extract_semantics
    from intentlang.translation_engine.semantic_phrase.verifier import verify_roundtrip

    source = "You have {count} unsaved changes"
    mutated = "You have unsaved changes"

    source_extracted = extract_semantics(source)
    target_extracted = extract_semantics(mutated)

    result = verify_roundtrip(
        source=source,
        target=mutated,
        source_extracted=source_extracted,
        target_extracted=target_extracted,
    )

    # Should not be VERIFIED
    assert result.verdict != "VERIFIED"


def test_mutation_harness_detects_destructive():
    """Destructive action change mutation is detected."""
    from intentlang.translation_engine.semantic_phrase.extractor import extract_semantics
    from intentlang.translation_engine.semantic_phrase.verifier import verify_roundtrip

    source = "This will permanently delete your account"
    mutated = "This will archive your account"

    source_extracted = extract_semantics(source)
    target_extracted = extract_semantics(mutated)

    result = verify_roundtrip(
        source=source,
        target=mutated,
        source_extracted=source_extracted,
        target_extracted=target_extracted,
    )

    # Should not be VERIFIED
    assert result.verdict != "VERIFIED"


def test_format_mutation_result():
    """Mutation result formatting works."""
    result = run_mutation_harness()
    formatted = format_mutation_result(result)
    assert "Mutation Harness" in formatted
    assert "Total mutations" in formatted
