"""
M3 — LLM Proposer: adapter for LLM-assisted phrase translation.

The LLM can PROPOSE translations, back-translations, and semantic parses,
but NEVER has final authority. The verifier decides.

In strict mode, no LLM is called — gaps stay NEEDS_REVIEW.

Usage:
    from semantic_phrase.proposer import ProposerAdapter, ProposeResult
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional, Protocol, Any

from intentlang.translation_engine.semantic_phrase.phrase_ir import PhraseIR, PhraseStatus, Provenance
from intentlang.translation_engine.semantic_phrase.extractor import ExtractedFacts


class LLMBackend(Protocol):
    """Protocol for LLM backends."""

    def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> str:
        """Send a completion request and return the response text."""
        ...


@dataclass
class ProposeResult:
    """Result of an LLM proposal."""
    proposal_type: str  # translation | backtranslation | semantic_parse
    content: str
    model: str
    provider: str
    confidence: float = 0.0
    raw_response: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "proposal_type": self.proposal_type,
            "content": self.content,
            "model": self.model,
            "provider": self.provider,
            "confidence": self.confidence,
            "error": self.error,
        }


# ── Prompt Templates ─────────────────────────────────────────────────

TRANSLATION_PROMPT = """You are a professional UI translator. Translate the following phrase from {source_locale} to {target_locale}.

Source phrase: "{source}"

Context:
- Speech act: {speech_act}
- Action: {action}
- Object: {object}
- Polarity: {polarity}
- Modality: {modality}
- Destructive: {destructive}
- Protected tokens: {protected_tokens}
- Technical terms: {technical_terms}

Requirements:
1. Preserve the semantic meaning exactly
2. Keep all placeholders ({slots}) in the same positions
3. Keep all protected tokens unchanged
4. Keep all technical terms unchanged
5. Preserve the speech act (warning stays warning, confirmation stays confirmation)
6. Preserve polarity (negative stays negative)
7. Preserve destructive semantics
8. Use natural {target_locale} phrasing

Translate to {target_locale}:"""


BACKTRANSLATION_PROMPT = """You are a professional translator. Back-translate the following phrase from {target_locale} to {source_locale}.

Target phrase: "{target}"

Requirements:
1. Produce a natural {source_locale} paraphrase
2. Preserve the semantic meaning
3. Keep all placeholders unchanged
4. Keep all technical terms unchanged

Back-translate to {source_locale}:"""


SEMANTIC_PARSE_PROMPT = """You are a semantic analyst. Parse the following phrase into structured semantic fields.

Phrase: "{phrase}"

Extract:
1. speech_act: STATEMENT | WARNING | CONFIRMATION | INSTRUCTION | ERROR | NOTIFICATION | QUESTION
2. action: the primary action verb (lowercase)
3. object: what is being acted upon (UPPERCASE)
4. polarity: positive | negative | neutral | assertive
5. modality: MUST | SHOULD | MAY | CAN | WILL | NONE
6. destructive: true | false
7. conditions: list of conditions (if any)
8. consequences: list of consequences (if any)

Respond in JSON format:
{{
  "speech_act": "...",
  "action": "...",
  "object": "...",
  "polarity": "...",
  "modality": "...",
  "destructive": ...,
  "conditions": [...],
  "consequences": [...]
}}"""


class ProposerAdapter:
    """Adapter for LLM-assisted phrase proposals.

    In strict mode, no LLM is called. All gaps stay NEEDS_REVIEW.
    """

    def __init__(
        self,
        backend: Optional[LLMBackend] = None,
        strict: bool = True,
        source_locale: str = "en",
        target_locale: str = "es",
    ):
        self.backend = backend
        self.strict = strict
        self.source_locale = source_locale
        self.target_locale = target_locale

    def propose_translation(
        self,
        source: str,
        phrase_ir: PhraseIR,
        extracted: ExtractedFacts,
    ) -> ProposeResult:
        """Propose a translation for a phrase.

        In strict mode, returns NEEDS_REVIEW without calling LLM.
        """
        if self.strict or self.backend is None:
            return ProposeResult(
                proposal_type="translation",
                content="",
                model="none",
                provider="deterministic",
                error="strict_mode: no LLM available",
            )

        prompt = TRANSLATION_PROMPT.format(
            source_locale=self.source_locale,
            target_locale=self.target_locale,
            source=source,
            speech_act=phrase_ir.speech_act,
            action=phrase_ir.action or "unknown",
            object=phrase_ir.object or "unknown",
            polarity=phrase_ir.polarity,
            modality=phrase_ir.modality,
            destructive=phrase_ir.destructive,
            protected_tokens=extracted.protected_tokens,
            technical_terms=extracted.technical_terms,
            slots=extracted.slots,
        )

        try:
            response = self.backend.complete(prompt, temperature=0.0)
            return ProposeResult(
                proposal_type="translation",
                content=response.strip(),
                model="llm",
                provider="llm_proposed",
                confidence=0.8,
                raw_response=response,
            )
        except Exception as e:
            return ProposeResult(
                proposal_type="translation",
                content="",
                model="llm",
                provider="llm_proposed",
                error=str(e),
            )

    def propose_backtranslation(
        self,
        target: str,
    ) -> ProposeResult:
        """Propose a back-translation from target to source.

        In strict mode, returns empty without calling LLM.
        """
        if self.strict or self.backend is None:
            return ProposeResult(
                proposal_type="backtranslation",
                content="",
                model="none",
                provider="deterministic",
                error="strict_mode: no LLM available",
            )

        prompt = BACKTRANSLATION_PROMPT.format(
            source_locale=self.source_locale,
            target_locale=self.target_locale,
            target=target,
        )

        try:
            response = self.backend.complete(prompt, temperature=0.0)
            return ProposeResult(
                proposal_type="backtranslation",
                content=response.strip(),
                model="llm",
                provider="llm_proposed",
                confidence=0.7,
                raw_response=response,
            )
        except Exception as e:
            return ProposeResult(
                proposal_type="backtranslation",
                content="",
                model="llm",
                provider="llm_proposed",
                error=str(e),
            )

    def propose_phrase_ir(
        self,
        surface: str,
    ) -> ProposeResult:
        """Propose semantic parse of a phrase.

        In strict mode, returns empty without calling LLM.
        """
        if self.strict or self.backend is None:
            return ProposeResult(
                proposal_type="semantic_parse",
                content="{}",
                model="none",
                provider="deterministic",
                error="strict_mode: no LLM available",
            )

        prompt = SEMANTIC_PARSE_PROMPT.format(phrase=surface)

        try:
            response = self.backend.complete(prompt, temperature=0.0)
            # Try to parse JSON from response
            # Handle markdown code blocks
            text = response.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
                if text.endswith("```"):
                    text = text[:-3]
            return ProposeResult(
                proposal_type="semantic_parse",
                content=text.strip(),
                model="llm",
                provider="llm_proposed",
                confidence=0.75,
                raw_response=response,
            )
        except Exception as e:
            return ProposeResult(
                proposal_type="semantic_parse",
                content="{}",
                model="llm",
                provider="llm_proposed",
                error=str(e),
            )


def build_phrase_ir_from_extraction(
    extracted: ExtractedFacts,
    source_surface: str,
    target_locale: str = "",
    phrase_id: str = "",
) -> PhraseIR:
    """Build a PhraseIR from deterministic extraction results.

    This is the deterministic base — no LLM involved.
    """
    from intentlang.translation_engine.semantic_phrase.phrase_ir import SpeechAct, Modality, generate_phrase_id

    # Determine speech act
    if extracted.is_warning:
        speech_act = SpeechAct.WARNING.value
    elif extracted.is_confirmation:
        speech_act = SpeechAct.CONFIRMATION.value
    elif extracted.negated:
        speech_act = SpeechAct.STATEMENT.value
    else:
        speech_act = SpeechAct.STATEMENT.value

    # Determine confirmation requirement
    requires_confirmation = extracted.is_confirmation or (
        extracted.destructive and extracted.is_warning
    )

    return PhraseIR(
        id=phrase_id or generate_phrase_id(source_surface, extracted.source_locale),
        source_locale=extracted.source_locale,
        target_locale=target_locale,
        source_surface=source_surface,
        speech_act=speech_act,
        action=None,  # Deterministic extraction doesn't reliably extract action
        object=None,  # Same for object
        polarity="negative" if extracted.negated else "neutral",
        modality=extracted.modality,
        destructive=extracted.destructive,
        requires_confirmation=requires_confirmation,
        conditions=extracted.conditions,
        consequences=extracted.consequences,
        slots=extracted.slots,
        protected_tokens=extracted.protected_tokens,
        technical_terms=extracted.technical_terms,
        status=PhraseStatus.UNKNOWN.value,
        provenance=Provenance(
            source_hash="",
            source_locale=extracted.source_locale,
            target_locale=target_locale,
            parser_mode="deterministic",
            verification_strength="deterministic",
        ),
    )
