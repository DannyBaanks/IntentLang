"""
M2 — Context Resolver: disambiguates homographs using UI context.

Words like "left", "close", "open", "light" have different translations
depending on context. This module uses the IR's section, type, and semantic
invariants to pick the correct sense before materialization.

Usage:
    from context_resolver import resolve_context, ContextHint
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ContextHint:
    """Resolved context for a message that needs disambiguation."""
    word: str
    sense: str           # "direction.left", "remaining.left", "verb.close", etc.
    confidence: float    # 0.0-1.0
    source: str          # "section_type", "key_pattern", "value_pattern", "semantic"


# ── Homograph rules ─────────────────────────────────────────────────
# Each rule maps (word, context) -> sense
# Context is matched against section, type, key, and value patterns

HOMOGRAPH_RULES: dict[str, list[dict]] = {
    "left": [
        {"sense": "direction.left", "match": {"type": ["navigation", "panel"]}, "conf": 0.9},
        {"sense": "direction.left", "match": {"key_contains": ["arrow", "side", "align"]}, "conf": 0.95},
        {"sense": "remaining.left", "match": {"value_contains": ["items", "tokens", "remaining"]}, "conf": 0.9},
        {"sense": "remaining.left", "match": {"key_contains": ["remain", "count", "balance"]}, "conf": 0.85},
    ],
    "right": [
        {"sense": "direction.right", "match": {"type": ["navigation", "panel"]}, "conf": 0.9},
        {"sense": "direction.right", "match": {"key_contains": ["arrow", "side", "align"]}, "conf": 0.95},
        {"sense": "correct.right", "match": {"value_contains": ["correct", "right answer"]}, "conf": 0.9},
    ],
    "close": [
        {"sense": "verb.close", "match": {"type": ["action", "button", "label"]}, "conf": 0.85},
        {"sense": "verb.close", "match": {"key_contains": ["close", "dismiss"]}, "conf": 0.95},
        {"sense": "adjective.close", "match": {"value_contains": ["near", "proximity"]}, "conf": 0.8},
    ],
    "open": [
        {"sense": "verb.open", "match": {"type": ["action", "button", "label"]}, "conf": 0.85},
        {"sense": "verb.open", "match": {"key_contains": ["open", "launch"]}, "conf": 0.95},
        {"sense": "adjective.open", "match": {"value_contains": ["door", "window"]}, "conf": 0.8},
    ],
    "light": [
        {"sense": "adjective.light", "match": {"key_contains": ["theme", "mode", "color"]}, "conf": 0.9},
        {"sense": "noun.light", "match": {"value_contains": ["lamp", "bulb"]}, "conf": 0.85},
    ],
    "run": [
        {"sense": "verb.run", "match": {"type": ["action", "button"]}, "conf": 0.85},
        {"sense": "verb.run", "match": {"key_contains": ["execute", "start"]}, "conf": 0.9},
        {"sense": "noun.run", "match": {"value_contains": ["jog", "marathon"]}, "conf": 0.8},
    ],
    "set": [
        {"sense": "verb.set", "match": {"type": ["action", "settings"]}, "conf": 0.85},
        {"sense": "noun.set", "match": {"value_contains": ["collection", "group"]}, "conf": 0.8},
    ],
    "clear": [
        {"sense": "verb.clear", "match": {"type": ["action"]}, "conf": 0.85},
        {"sense": "adjective.clear", "match": {"value_contains": ["transparent", "visible"]}, "conf": 0.8},
    ],
    "check": [
        {"sense": "verb.check", "match": {"type": ["action"]}, "conf": 0.85},
        {"sense": "noun.check", "match": {"value_contains": ["mark", "tick"]}, "conf": 0.8},
    ],
    "save": [
        {"sense": "verb.save", "match": {"type": ["action", "button", "label"]}, "conf": 0.9},
        {"sense": "verb.save", "match": {"key_contains": ["save", "store"]}, "conf": 0.95},
    ],
    "type": [
        {"sense": "noun.type", "match": {"value_contains": ["kind", "category"]}, "conf": 0.8},
        {"sense": "verb.type", "match": {"type": ["action", "input"]}, "conf": 0.85},
    ],
    "point": [
        {"sense": "noun.point", "match": {"value_contains": ["score", "mark"]}, "conf": 0.8},
        {"sense": "verb.point", "match": {"type": ["action"]}, "conf": 0.85},
    ],
    "post": [
        {"sense": "noun.post", "match": {"value_contains": ["message", "article"]}, "conf": 0.8},
        {"sense": "verb.post", "match": {"type": ["action"]}, "conf": 0.85},
    ],
    "address": [
        {"sense": "noun.address", "match": {"key_contains": ["url", "email", "location"]}, "conf": 0.9},
        {"sense": "verb.address", "match": {"value_contains": ["handle", "deal"]}, "conf": 0.8},
    ],
    "issue": [
        {"sense": "noun.issue", "match": {"key_contains": ["bug", "ticket", "report"]}, "conf": 0.9},
        {"sense": "verb.issue", "match": {"type": ["action"]}, "conf": 0.8},
    ],
    "content": [
        {"sense": "noun.content", "match": {}, "conf": 0.95},  # almost always noun in UI
    ],
    "present": [
        {"sense": "adjective.present", "match": {"value_contains": ["now", "current"]}, "conf": 0.8},
        {"sense": "verb.present", "match": {"type": ["action"]}, "conf": 0.85},
    ],
    "figure": [
        {"sense": "noun.figure", "match": {"value_contains": ["number", "image"]}, "conf": 0.8},
    ],
    "subject": [
        {"sense": "noun.subject", "match": {"value_contains": ["topic", "email"]}, "conf": 0.8},
    ],
}


def _match_rule(entry: dict, match: dict) -> bool:
    """Check if an IR entry matches a rule's match criteria."""
    for criterion, values in match.items():
        if criterion == "type":
            if entry.get("type") not in values:
                return False
        elif criterion == "section":
            if entry.get("section") not in values:
                return False
        elif criterion == "key_contains":
            key_lower = entry.get("key", "").lower()
            if not any(v in key_lower for v in values):
                return False
        elif criterion == "value_contains":
            val_lower = entry.get("value", "").lower()
            if not any(v in val_lower for v in values):
                return False
    return True


def resolve_context(word: str, entry: dict) -> Optional[ContextHint]:
    """Resolve the sense of a homograph using IR context.

    Args:
        word: The word to disambiguate (lowercase).
        entry: The IR entry dict (from inventory or UIMessageIR.to_dict()).

    Returns:
        ContextHint if a rule matched, None if no disambiguation needed.
    """
    word_lower = word.lower()
    rules = HOMOGRAPH_RULES.get(word_lower, [])

    if not rules:
        return None

    best = None
    best_conf = 0.0

    for rule in rules:
        if _match_rule(entry, rule["match"]):
            if rule["conf"] > best_conf:
                best_conf = rule["conf"]
                best = ContextHint(
                    word=word,
                    sense=rule["sense"],
                    confidence=rule["conf"],
                    source="homograph_rule",
                )

    return best


def get_all_homographs() -> list[str]:
    """Return all words with homograph rules."""
    return sorted(HOMOGRAPH_RULES.keys())


def enrich_inventory_with_context(inventory_path: str, output_path: str) -> dict:
    """Enrich an inventory file with resolved contexts.

    Returns stats dict.
    """
    import json

    with open(inventory_path, encoding="utf-8") as f:
        data = json.load(f)

    resolved = 0
    ambiguous = 0

    for key, entry in data["inventory"].items():
        raw_value = entry.get("value", "")
        value = " ".join(str(item) for item in raw_value) \
            if isinstance(raw_value, list) else str(raw_value)
        words = value.lower().replace(",", "").replace(".", "").split()

        contexts = []
        for word in words:
            hint = resolve_context(word, entry)
            if hint:
                contexts.append({
                    "word": hint.word,
                    "sense": hint.sense,
                    "confidence": hint.confidence,
                })

        if contexts:
            entry["context_hints"] = contexts
            resolved += 1
        else:
            ambiguous += 1

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return {"resolved": resolved, "ambiguous": ambiguous, "total": len(data["inventory"])}
