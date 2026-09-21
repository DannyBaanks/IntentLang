"""
Semantic Phrase Engine — LLM-assisted translation with deterministic authority.

This module provides a complete pipeline for translating semantically complex
phrases where the LLM can PROPOSE but IntentLang DECIDES.

Pipeline:
  1. Extract semantic invariants (M2 - deterministic)
  2. LLM proposes translation (M3 - optional)
  3. Verify roundtrip (M4 - deterministic)
  4. Emit verdict (VERIFIED / NEEDS_REVIEW / REJECTED)

Usage:
    from intentlang.translation_engine.semantic_phrase import (
        run_phrase_pipeline,
        extract_semantics,
        verify_roundtrip,
    )
"""
from __future__ import annotations

from intentlang.translation_engine.semantic_phrase.corpus import CorpusEntry, extract_corpus
from intentlang.translation_engine.semantic_phrase.extractor import (
    ExtractedFacts,
    extract_semantics,
)
from intentlang.translation_engine.semantic_phrase.mutations import (
    MutationResult,
    run_mutation_harness,
)
from intentlang.translation_engine.semantic_phrase.phrase_ir import (
    PhraseIR,
    PhraseStatus,
    Provenance,
)
from intentlang.translation_engine.semantic_phrase.proposer import ProposerAdapter, ProposeResult
from intentlang.translation_engine.semantic_phrase.verifier import VerifyResult, verify_roundtrip


def run_phrase_pipeline(
    source: str,
    target: str,
    source_locale: str = "en",
    target_locale: str = "es",
    proposer: ProposerAdapter | None = None,
) -> VerifyResult:
    """Run the complete phrase translation pipeline.

    1. Extract semantic invariants from source
    2. Optionally let LLM propose translation
    3. Extract semantic invariants from target
    4. Verify roundtrip
    5. Return verdict

    Args:
        source: Source phrase
        target: Target phrase (or empty if proposing)
        source_locale: Source language code
        target_locale: Target language code
        proposer: Optional LLM proposer (strict mode if None)

    Returns:
        VerifyResult with verdict and checks
    """
    # 1. Extract source semantics
    source_extracted = extract_semantics(source, source_locale)

    # 2. If target is empty and proposer available, propose
    if not target and proposer:
        from semantic_phrase.proposer import build_phrase_ir_from_extraction
        source_ir = build_phrase_ir_from_extraction(
            source_extracted, source, target_locale
        )
        proposal = proposer.propose_translation(source, source_ir, source_extracted)
        if proposal.content:
            target = proposal.content

    # 3. Extract target semantics
    target_extracted = extract_semantics(target, target_locale) if target else None

    # 4. Verify roundtrip
    if target:
        result = verify_roundtrip(
            source=source,
            target=target,
            source_locale=source_locale,
            target_locale=target_locale,
            source_extracted=source_extracted,
            target_extracted=target_extracted,
        )
    else:
        # No target available
        result = VerifyResult(
            verdict=PhraseStatus.NEEDS_REVIEW.value,
            source_phrase=source,
            target_phrase="",
            limitations=["no_target_available"],
        )

    return result


__all__ = [
    "CorpusEntry",
    "ExtractedFacts",
    "MutationResult",
    "PhraseIR",
    "PhraseStatus",
    "ProposeResult",
    "ProposerAdapter",
    "Provenance",
    "VerifyResult",
    "extract_corpus",
    "extract_semantics",
    "run_mutation_harness",
    "run_phrase_pipeline",
    "verify_roundtrip",
]
