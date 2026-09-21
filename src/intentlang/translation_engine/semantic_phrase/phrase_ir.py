"""
M1 — Phrase IR: canonical representation for semantically complex phrases.

This IR captures semantic invariants that must survive translation:
- Speech act, intent, action, object
- Polarity, modality, tense, destructive flag
- Conditions, consequences, constraints
- Slots, protected tokens, technical terms
- Provenance with full audit trail

Schema version: phrase-ir/1

Usage:
    from semantic_phrase.phrase_ir import PhraseIR, PhraseStatus
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from enum import Enum

PHRASE_IR_VERSION = "phrase-ir/1"


class PhraseStatus(str, Enum):
    """Status of a phrase translation."""
    VERIFIED = "VERIFIED"
    VERIFIED_WITH_LIMITATIONS = "VERIFIED_WITH_LIMITATIONS"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    AMBIGUOUS = "AMBIGUOUS"
    UNKNOWN = "UNKNOWN"
    REJECTED = "REJECTED"
    NOT_DEMONSTRATED = "NOT_DEMONSTRATED"


class SpeechAct(str, Enum):
    """Speech act categories for UI phrases."""
    STATEMENT = "STATEMENT"
    WARNING = "WARNING"
    CONFIRMATION = "CONFIRMATION"
    INSTRUCTION = "INSTRUCTION"
    ERROR = "ERROR"
    NOTIFICATION = "NOTIFICATION"
    QUESTION = "QUESTION"
    REQUEST = "REQUEST"
    PROMISE = "PROMISE"
    UNKNOWN = "UNKNOWN"


class Modality(str, Enum):
    """Modal strength categories."""
    MUST = "MUST"        # obligation
    SHALL = "SHALL"      # strong obligation
    SHOULD = "SHOULD"    # recommendation
    MAY = "MAY"          # permission
    CAN = "CAN"          # ability
    WILL = "WILL"        # future certainty
    NONE = "NONE"        # no modal
    UNKNOWN = "UNKNOWN"


@dataclass
class Provenance:
    """Full audit trail for phrase processing."""
    source_hash: str
    target_hash: str | None = None
    source_locale: str = ""
    target_locale: str = ""
    phrase_ir_version: str = PHRASE_IR_VERSION
    parser_mode: str = "deterministic"  # deterministic | llm_assisted
    extraction_model: str | None = None
    translation_model: str | None = None
    backtranslation_model: str | None = None
    verifier_version: str = "1.0.0"
    context_source: str | None = None
    result: str | None = None
    evidence_hash: str | None = None
    prompt_version: str | None = None
    verification_strength: str = "deterministic"
    # ^ deterministic | single_model_roundtrip | dual_model_roundtrip
    #   lexical_plus_model | human_confirmed

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class PhraseIR:
    """A semantically annotated phrase for translation.

    Schema: phrase-ir/1
    Fields may be None/UNKNOWN when not deterministically extractable.
    """
    schema: str = PHRASE_IR_VERSION
    id: str = ""

    # Locale info
    source_locale: str = "en"
    target_locale: str = ""
    source_surface: str = ""

    # Semantic fields
    speech_act: str = SpeechAct.UNKNOWN.value
    intent: str | None = None
    subject: str | None = None
    action: str | None = None
    object: str | None = None

    # Logical properties
    polarity: str = "neutral"       # positive | negative | neutral | assertive
    modality: str = Modality.NONE.value
    tense: str | None = None     # past | present | future | None
    destructive: bool = False
    requires_confirmation: bool = False

    # Structural elements
    conditions: list[str] = field(default_factory=list)
    consequences: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)

    # Slots and tokens
    slots: list[str] = field(default_factory=list)
    protected_tokens: list[str] = field(default_factory=list)
    technical_terms: list[str] = field(default_factory=list)

    # Context
    context: str | None = None
    register: str | None = None  # formal | informal | technical | casual

    # Provenance
    provenance: Provenance | None = None
    status: str = PhraseStatus.UNKNOWN.value

    def to_dict(self) -> dict:
        """Serialize to dict, preserving all fields."""
        d = {
            "schema": self.schema,
            "id": self.id,
            "source_locale": self.source_locale,
            "target_locale": self.target_locale,
            "source_surface": self.source_surface,
            "speech_act": self.speech_act,
            "intent": self.intent,
            "subject": self.subject,
            "action": self.action,
            "object": self.object,
            "polarity": self.polarity,
            "modality": self.modality,
            "tense": self.tense,
            "destructive": self.destructive,
            "requires_confirmation": self.requires_confirmation,
            "conditions": self.conditions,
            "consequences": self.consequences,
            "constraints": self.constraints,
            "slots": self.slots,
            "protected_tokens": self.protected_tokens,
            "technical_terms": self.technical_terms,
            "context": self.context,
            "register": self.register,
            "status": self.status,
        }
        if self.provenance:
            d["provenance"] = self.provenance.to_dict()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> PhraseIR:
        """Deserialize from dict."""
        prov = d.get("provenance")
        if prov and isinstance(prov, dict):
            prov = Provenance(**prov)
        return cls(
            schema=d.get("schema", PHRASE_IR_VERSION),
            id=d.get("id", ""),
            source_locale=d.get("source_locale", "en"),
            target_locale=d.get("target_locale", ""),
            source_surface=d.get("source_surface", ""),
            speech_act=d.get("speech_act", SpeechAct.UNKNOWN.value),
            intent=d.get("intent"),
            subject=d.get("subject"),
            action=d.get("action"),
            object=d.get("object"),
            polarity=d.get("polarity", "neutral"),
            modality=d.get("modality", Modality.NONE.value),
            tense=d.get("tense"),
            destructive=d.get("destructive", False),
            requires_confirmation=d.get("requires_confirmation", False),
            conditions=d.get("conditions", []),
            consequences=d.get("consequences", []),
            constraints=d.get("constraints", []),
            slots=d.get("slots", []),
            protected_tokens=d.get("protected_tokens", []),
            technical_terms=d.get("technical_terms", []),
            context=d.get("context"),
            register=d.get("register"),
            provenance=prov,
            status=d.get("status", PhraseStatus.UNKNOWN.value),
        )

    def semantic_hash(self) -> str:
        """Deterministic hash of semantic invariants.

        Two phrases with the same semantic meaning MUST produce the same hash,
        regardless of surface wording.
        """
        data = {
            "speech_act": self.speech_act,
            "action": self.action,
            "object": self.object,
            "polarity": self.polarity,
            "modality": self.modality,
            "destructive": self.destructive,
            "requires_confirmation": self.requires_confirmation,
            "conditions": sorted(self.conditions),
            "consequences": sorted(self.consequences),
            "constraints": sorted(self.constraints),
            "slots": sorted(self.slots),
            "protected_tokens": sorted(self.protected_tokens),
            "technical_terms": sorted(self.technical_terms),
        }
        canonical = json.dumps(data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]

    def is_verified(self) -> bool:
        """Check if this phrase has been verified."""
        return self.status in (
            PhraseStatus.VERIFIED.value,
            PhraseStatus.VERIFIED_WITH_LIMITATIONS.value,
        )

    def needs_review(self) -> bool:
        """Check if this phrase needs human review."""
        return self.status in (
            PhraseStatus.NEEDS_REVIEW.value,
            PhraseStatus.AMBIGUOUS.value,
        )


def generate_phrase_id(source_surface: str, source_locale: str) -> str:
    """Generate a deterministic ID for a phrase."""
    content = f"{source_locale}:{source_surface}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]
