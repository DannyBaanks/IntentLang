"""
M7 — Routing: determine which phrases use which translation path.

Routing logic:
- Short phrases (< 5 words) → UI Message IR path (Phase 1)
- Contextual phrases (single words, UI labels) → UI Message IR path
- Long semantic phrases (warnings, confirmations, descriptions) → Semantic Phrase Engine
- Phrases with semantic invariants → Semantic Phrase Engine

Usage:
    from intentlang.translation_engine.routing import route_phrase, TranslationPath
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from intentlang.translation_engine.semantic_phrase.extractor import (
    extract_semantics,
    ExtractedFacts,
)


class TranslationPath(Enum):
    """Which translation path to use."""
    UI_MESSAGE_IR = "ui_message_ir"  # Phase 1: dictionary-based
    SEMANTIC_PHRASE = "semantic_phrase"  # Phase 2: semantic phrase engine
    HYBRID = "hybrid"  # Both paths, merge results


@dataclass
class RoutingDecision:
    """Decision on which path to use."""
    path: TranslationPath
    reason: str
    confidence: float  # 0.0 to 1.0
    extracted_facts: Optional[ExtractedFacts] = None

    def to_dict(self) -> dict:
        return {
            "path": self.path.value,
            "reason": self.reason,
            "confidence": self.confidence,
        }


def route_phrase(
    source: str,
    locale: str = "en",
    section: str = "",
) -> RoutingDecision:
    """Determine which translation path to use for a phrase.

    Routing rules:
    1. Single words → UI_MESSAGE_IR (labels, buttons)
    2. Short phrases (< 5 words) without semantic invariants → UI_MESSAGE_IR
    3. Phrases with warnings, confirmations, destructive flags → SEMANTIC_PHRASE
    4. Long phrases (> 10 words) → SEMANTIC_PHRASE
    5. Everything else → UI_MESSAGE_IR (default)

    Args:
        source: Source phrase
        locale: Source locale
        section: Section/context in the locale file

    Returns:
        RoutingDecision with path, reason, and confidence
    """
    # Extract semantics
    facts = extract_semantics(source, locale)

    # Word count
    words = source.split()
    word_count = len(words)

    # Rule 1: Single words → UI_MESSAGE_IR
    if word_count == 1:
        return RoutingDecision(
            path=TranslationPath.UI_MESSAGE_IR,
            reason="single_word",
            confidence=0.95,
            extracted_facts=facts,
        )

    # Rule 2: Short phrases without semantic invariants → UI_MESSAGE_IR
    if word_count < 5 and not facts.negated and not facts.is_warning and not facts.destructive:
        return RoutingDecision(
            path=TranslationPath.UI_MESSAGE_IR,
            reason="short_phrase_no_semantics",
            confidence=0.85,
            extracted_facts=facts,
        )

    # Rule 3: Phrases with warnings, confirmations, destructive → SEMANTIC_PHRASE
    if facts.is_warning or facts.is_confirmation or facts.destructive:
        reasons = []
        if facts.is_warning:
            reasons.append("warning")
        if facts.is_confirmation:
            reasons.append("confirmation")
        if facts.destructive:
            reasons.append("destructive")
        return RoutingDecision(
            path=TranslationPath.SEMANTIC_PHRASE,
            reason="+".join(reasons),
            confidence=0.9,
            extracted_facts=facts,
        )

    # Rule 4: Long phrases → SEMANTIC_PHRASE
    if word_count > 10:
        return RoutingDecision(
            path=TranslationPath.SEMANTIC_PHRASE,
            reason="long_phrase",
            confidence=0.8,
            extracted_facts=facts,
        )

    # Rule 5: Phrases with conditions or consequences → SEMANTIC_PHRASE
    if facts.conditions or facts.consequences:
        return RoutingDecision(
            path=TranslationPath.SEMANTIC_PHRASE,
            reason="has_conditions_or_consequences",
            confidence=0.85,
            extracted_facts=facts,
        )

    # Rule 6: Phrases with placeholders → UI_MESSAGE_IR (handled by Phase 1 materializer)
    if facts.slots:
        return RoutingDecision(
            path=TranslationPath.UI_MESSAGE_IR,
            reason="has_placeholders",
            confidence=0.8,
            extracted_facts=facts,
        )

    # Default: UI_MESSAGE_IR
    return RoutingDecision(
        path=TranslationPath.UI_MESSAGE_IR,
        reason="default_short_phrase",
        confidence=0.7,
        extracted_facts=facts,
    )


def route_corpus(
    phrases: list[dict],
) -> dict:
    """Route a corpus of phrases.

    Args:
        phrases: List of dicts with keys: key, source, target, section

    Returns:
        Dict with routing statistics and decisions
    """
    stats = {
        "total": len(phrases),
        "ui_message_ir": 0,
        "semantic_phrase": 0,
        "hybrid": 0,
        "decisions": [],
    }

    for phrase in phrases:
        decision = route_phrase(
            source=phrase["source"],
            section=phrase.get("section", ""),
        )

        if decision.path == TranslationPath.UI_MESSAGE_IR:
            stats["ui_message_ir"] += 1
        elif decision.path == TranslationPath.SEMANTIC_PHRASE:
            stats["semantic_phrase"] += 1
        else:
            stats["hybrid"] += 1

        stats["decisions"].append({
            "key": phrase["key"],
            "source": phrase["source"][:80],
            "path": decision.path.value,
            "reason": decision.reason,
            "confidence": decision.confidence,
        })

    return stats


def format_routing_report(stats: dict) -> str:
    """Format routing report for display."""
    lines = [
        "=== Translation Routing Report ===",
        "Total phrases: %d" % stats["total"],
        "",
        "=== Path Distribution ===",
    ]

    if stats["total"] > 0:
        ui_pct = stats["ui_message_ir"] / stats["total"] * 100
        sp_pct = stats["semantic_phrase"] / stats["total"] * 100
        hy_pct = stats["hybrid"] / stats["total"] * 100
        lines.append("UI Message IR: %d (%.1f%%)" % (stats["ui_message_ir"], ui_pct))
        lines.append("Semantic Phrase: %d (%.1f%%)" % (stats["semantic_phrase"], sp_pct))
        lines.append("Hybrid: %d (%.1f%%)" % (stats["hybrid"], hy_pct))

    # Show routing reasons
    reason_counts = {}
    for d in stats["decisions"]:
        reason = d["reason"]
        reason_counts[reason] = reason_counts.get(reason, 0) + 1

    lines.append("")
    lines.append("=== Routing Reasons ===")
    for reason, count in sorted(reason_counts.items(), key=lambda x: -x[1]):
        lines.append("  %s: %d" % (reason, count))

    # Show sample decisions
    lines.append("")
    lines.append("=== Sample Decisions ===")
    for d in stats["decisions"][:10]:
        lines.append("  [%s] %s" % (d["path"], d["key"]))
        lines.append("    Source: %s" % d["source"])
        lines.append("    Reason: %s (conf: %.2f)" % (d["reason"], d["confidence"]))

    return "\n".join(lines)
