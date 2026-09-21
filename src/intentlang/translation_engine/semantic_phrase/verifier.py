"""
M4 — Semantic Roundtrip Verifier.

Verifies that translating A→B preserves semantic invariants:
  1. Parse source to IR_A
  2. Materialize target (or receive it)
  3. Parse target to IR_B
  4. Compare semantic invariants
  5. Emit structured verdict

The backtranslation is auxiliary evidence, not authority.

Usage:
    from semantic_phrase.verifier import verify_roundtrip, VerifyResult
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from intentlang.translation_engine.semantic_phrase.extractor import (
    ExtractedFacts,
    extract_semantics,
)
from intentlang.translation_engine.semantic_phrase.phrase_ir import (
    PhraseIR,
    PhraseStatus,
)


@dataclass
class InvariantCheck:
    """A single invariant check result."""
    field: str
    source_value: Any
    target_value: Any
    passed: bool
    reason: str | None = None


@dataclass
class VerifyResult:
    """Complete roundtrip verification result."""
    verdict: str  # PhraseStatus value
    source_phrase: str
    target_phrase: str
    source_ir: PhraseIR | None = None
    target_ir: PhraseIR | None = None
    backtranslation: str | None = None
    checks: list[InvariantCheck] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    verifier_mode: str = "deterministic"
    evidence_hash: str | None = None

    @property
    def passed(self) -> bool:
        return self.verdict in (
            PhraseStatus.VERIFIED.value,
            PhraseStatus.VERIFIED_WITH_LIMITATIONS.value,
        )

    @property
    def pass_rate(self) -> float:
        if not self.checks:
            return 0.0
        return sum(1 for c in self.checks if c.passed) / len(self.checks)

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "source_phrase": self.source_phrase,
            "target_phrase": self.target_phrase,
            "backtranslation": self.backtranslation,
            "checks": [
                {
                    "field": c.field,
                    "source_value": c.source_value,
                    "target_value": c.target_value,
                    "passed": c.passed,
                    "reason": c.reason,
                }
                for c in self.checks
            ],
            "limitations": self.limitations,
            "verifier_mode": self.verifier_mode,
            "evidence_hash": self.evidence_hash,
            "pass_rate": round(self.pass_rate, 3),
        }


def _check_field(
    field_name: str,
    source_val: Any,
    target_val: Any,
    required: bool = True,
) -> InvariantCheck:
    """Check a single semantic field."""
    if source_val is None and target_val is None:
        return InvariantCheck(field_name, None, None, True)
    if source_val is None:
        return InvariantCheck(field_name, None, target_val, True,
                              reason="source_unknown")
    if target_val is None:
        if required:
            return InvariantCheck(field_name, source_val, None, False,
                                  reason="target_unknown_required")
        return InvariantCheck(field_name, source_val, None, True,
                              reason="target_unknown_optional")

    # Normalize for comparison
    s = str(source_val).lower().strip()
    t = str(target_val).lower().strip()

    if s == t:
        return InvariantCheck(field_name, source_val, target_val, True)

    return InvariantCheck(field_name, source_val, target_val, False,
                          reason="value_mismatch")


def verify_roundtrip(
    source: str,
    target: str,
    source_locale: str = "en",
    target_locale: str = "es",
    source_ir: PhraseIR | None = None,
    target_ir: PhraseIR | None = None,
    backtranslation: str | None = None,
    source_extracted: ExtractedFacts | None = None,
    target_extracted: ExtractedFacts | None = None,
) -> VerifyResult:
    """Verify semantic roundtrip between source and target phrases.

    The authority is the deterministic comparison of semantic invariants,
    NOT the backtranslation.

    Args:
        source: Source phrase
        target: Target phrase
        source_locale: Source language code
        target_locale: Target language code
        source_ir: Pre-parsed source IR (optional)
        target_ir: Pre-parsed target IR (optional)
        backtranslation: Back-translated phrase (auxiliary evidence only)
        source_extracted: Pre-extracted source facts (optional)
        target_extracted: Pre-extracted target facts (optional)

    Returns:
        VerifyResult with verdict and structured checks
    """
    checks = []
    limitations = []

    # Extract or use provided facts
    if source_extracted is None:
        source_extracted = extract_semantics(source, source_locale)
    if target_extracted is None:
        target_extracted = extract_semantics(target, target_locale)

    # Build IRs if not provided
    if source_ir is None:
        from intentlang.translation_engine.semantic_phrase.proposer import (
            build_phrase_ir_from_extraction,
        )
        source_ir = build_phrase_ir_from_extraction(
            source_extracted, source, target_locale
        )
    if target_ir is None:
        from intentlang.translation_engine.semantic_phrase.proposer import (
            build_phrase_ir_from_extraction,
        )
        target_ir = build_phrase_ir_from_extraction(
            target_extracted, target, target_locale, source_locale
        )

    # ── Invariant Checks ─────────────────────────────────────────────

    # 1. Speech act preserved
    checks.append(_check_field(
        "speech_act", source_ir.speech_act, target_ir.speech_act
    ))

    # 2. Action preserved (if both have it)
    if source_ir.action or target_ir.action:
        checks.append(_check_field(
            "action", source_ir.action, target_ir.action, required=False
        ))

    # 3. Object preserved (if both have it)
    if source_ir.object or target_ir.object:
        checks.append(_check_field(
            "object", source_ir.object, target_ir.object, required=False
        ))

    # 4. Polarity preserved
    checks.append(_check_field(
        "polarity", source_ir.polarity, target_ir.polarity
    ))

    # 5. Modality preserved
    checks.append(_check_field(
        "modality", source_ir.modality, target_ir.modality
    ))

    # 6. Destructive flag preserved
    checks.append(_check_field(
        "destructive", source_ir.destructive, target_ir.destructive
    ))

    # 7. Confirmation requirement preserved
    checks.append(_check_field(
        "requires_confirmation",
        source_ir.requires_confirmation,
        target_ir.requires_confirmation,
    ))

    # 8. Conditions preserved (set comparison)
    src_cond = sorted(source_ir.conditions)
    tgt_cond = sorted(target_ir.conditions)
    checks.append(_check_field("conditions", src_cond, tgt_cond, required=False))

    # 9. Consequences preserved (set comparison)
    src_cons = sorted(source_ir.consequences)
    tgt_cons = sorted(target_ir.consequences)
    checks.append(_check_field("consequences", src_cons, tgt_cons, required=False))

    # 10. Protected tokens preserved
    src_tokens = sorted(source_ir.protected_tokens)
    tgt_tokens = sorted(target_ir.protected_tokens)
    checks.append(_check_field("protected_tokens", src_tokens, tgt_tokens))

    # 11. Technical terms preserved
    src_tech = sorted(source_ir.technical_terms)
    tgt_tech = sorted(target_ir.technical_terms)
    checks.append(_check_field("technical_terms", src_tech, tgt_tech, required=False))

    # 12. Slots/placeholders preserved
    src_slots = sorted(source_ir.slots)
    tgt_slots = sorted(target_ir.slots)
    checks.append(_check_field("slots", src_slots, tgt_slots))

    # 13. Negation consistency
    src_neg = source_extracted.negated
    tgt_neg = target_extracted.negated
    checks.append(_check_field("negation", src_neg, tgt_neg))

    # ── Backtranslation as auxiliary evidence ──────────────────────────

    if backtranslation:
        # Compare backtranslation semantic hash with source
        from intentlang.translation_engine.semantic_phrase.extractor import (
            extract_semantics as extract,
        )
        bt_extracted = extract(backtranslation, source_locale)

        # If negation differs between source and backtranslation, flag it
        if source_extracted.negated != bt_extracted.negated:
            limitations.append("backtranslation_negation_mismatch")

        # If modality differs
        if source_extracted.modality != bt_extracted.modality:
            limitations.append("backtranslation_modality_mismatch")

    # ── Determine Verdict ─────────────────────────────────────────────

    failed_checks = [c for c in checks if not c.passed]
    passed_checks = [c for c in checks if c.passed]

    if not failed_checks:
        # All checks passed
        if limitations:
            verdict = PhraseStatus.VERIFIED_WITH_LIMITATIONS.value
        else:
            verdict = PhraseStatus.VERIFIED.value
    elif len(failed_checks) <= 2 and all(
        c.reason in ("target_unknown_required", "target_unknown_optional")
        for c in failed_checks
    ):
        # Only unknown fields failed — needs review, not rejection
        verdict = PhraseStatus.NEEDS_REVIEW.value
    elif len(failed_checks) >= 3:
        # Multiple structural failures — likely rejected
        verdict = PhraseStatus.REJECTED.value
    else:
        # Some failures — needs review
        verdict = PhraseStatus.NEEDS_REVIEW.value

    # Build evidence hash
    evidence_data = {
        "source": source,
        "target": target,
        "verdict": verdict,
        "checks_passed": len(passed_checks),
        "checks_failed": len(failed_checks),
    }
    import hashlib
    evidence_hash = hashlib.sha256(
        json.dumps(evidence_data, sort_keys=True).encode()
    ).hexdigest()[:16]

    return VerifyResult(
        verdict=verdict,
        source_phrase=source,
        target_phrase=target,
        source_ir=source_ir,
        target_ir=target_ir,
        backtranslation=backtranslation,
        checks=checks,
        limitations=limitations,
        verifier_mode="deterministic" if not backtranslation else "lexical_plus_model",
        evidence_hash=evidence_hash,
    )


def format_verify_result(result: VerifyResult) -> str:
    """Format verification result for display."""
    lines = [
        "=== Semantic Roundtrip Verification ===",
        f"Verdict: {result.verdict}",
        "Pass rate: %.1f%%" % (result.pass_rate * 100),
        "",
        f"Source: \"{result.source_phrase[:80]}\"",
        f"Target: \"{result.target_phrase[:80]}\"",
    ]

    if result.backtranslation:
        lines.append(f"Back-translation: \"{result.backtranslation[:80]}\"")

    lines.append("")
    lines.append("=== Invariant Checks ===")
    for c in result.checks:
        status = "PASS" if c.passed else "FAIL"
        lines.append(f"  [{status}] {c.field}: {c.source_value} -> {c.target_value}")
        if c.reason:
            lines.append(f"         reason: {c.reason}")

    if result.limitations:
        lines.append("")
        lines.append("=== Limitations ===")
        lines.extend(f"  - {lim}" for lim in result.limitations)

    return "\n".join(lines)
