"""
M0 — Corpus: extract phrases that need semantic analysis.

Identifies phrases from the translation engine inventory that are:
- Multi-word (not single labels/buttons)
- Long enough to carry complex semantics
- Not already marked as passthrough

These are the candidates for the Semantic Phrase Engine.

Usage:
    from semantic_phrase.corpus import extract_corpus, CorpusEntry
"""
from __future__ import annotations

import json
import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

CORPUS_VERSION = "1.0.0"

# Phrase types that typically need semantic analysis
SEMANTIC_TYPES = {
    "dialog", "notification", "error", "warning", "tooltip",
    "confirmation", "instruction", "description", "prose",
    "status", "prompt", "hud",
}

# Patterns indicating complex semantics
COMPLEX_PATTERNS = [
    re.compile(r"\bwill\b.*\bdelete\b", re.IGNORECASE),
    re.compile(r"\bmust\b", re.IGNORECASE),
    re.compile(r"\bshall not\b", re.IGNORECASE),
    re.compile(r"\bcannot\b", re.IGNORECASE),
    re.compile(r"\bif\b.*\bthen\b", re.IGNORECASE),
    re.compile(r"\bunless\b", re.IGNORECASE),
    re.compile(r"\bdiscard\b", re.IGNORECASE),
    re.compile(r"\bunsaved\b", re.IGNORECASE),
    re.compile(r"\bconfirmation\b", re.IGNORECASE),
    re.compile(r"\bthis action\b", re.IGNORECASE),
    re.compile(r"\bare you sure\b", re.IGNORECASE),
    re.compile(r"\bpermanently\b", re.IGNORECASE),
    re.compile(r"\bmay\b.*\bresult\b", re.IGNORECASE),
    re.compile(r"\bwarning\b", re.IGNORECASE),
    re.compile(r"\bnote\b:", re.IGNORECASE),
]


@dataclass
class CorpusEntry:
    """A single phrase extracted for semantic analysis."""
    key: str
    value: str
    section: str
    type: str
    length: int
    placeholders: list[str] = field(default_factory=list)
    accelerators: list[str] = field(default_factory=list)
    phrase_type: str = "unknown"  # warning, tooltip, prose, etc.
    complexity_score: float = 0.0
    reasons: list[str] = field(default_factory=list)
    content_hash: str = ""


def _classify_phrase_type(value: str, section: str, key: str) -> str:
    """Classify the semantic type of a phrase."""
    v = value.strip().lower()
    k = key.lower()

    # Warning patterns
    if any(w in v for w in ["will delete", "will remove", "will discard",
                             "cannot be undone", "permanent", "this action",
                             "are you sure", "warning", "caution"]):
        return "warning"

    # Confirmation patterns
    if any(w in v for w in ["confirm", "are you sure", "do you want",
                             "proceed", "yes, ", "no, "]):
        return "confirmation"

    # Instruction patterns
    if any(w in v for w in ["press", "click", "select", "enter",
                             "type", "hold", "drag"]):
        return "instruction"

    # Error explanation
    if any(w in v for w in ["failed", "error", "could not", "unable to",
                             "invalid", "not found"]):
        return "error"

    # Tooltip/description
    if any(w in v for w in ["tooltip", "hint", "help", "description"]):
        return "tooltip"

    # Notification
    if any(w in v for w in ["notification", "alert", "update available",
                             "you have", "new"]):
        return "notification"

    # Prose (longer text)
    if len(v) > 50:
        return "prose"

    return "description"


def _compute_complexity(value: str, section: str, key: str) -> tuple[float, list[str]]:
    """Compute complexity score and reasons for a phrase."""
    score = 0.0
    reasons = []
    v = value.strip()

    # Length factor
    if len(v) > 100:
        score += 0.3
        reasons.append("long_phrase")
    elif len(v) > 50:
        score += 0.15
        reasons.append("medium_phrase")

    # Word count
    words = v.split()
    if len(words) > 15:
        score += 0.2
        reasons.append("many_words")

    # Complex patterns
    for pattern in COMPLEX_PATTERNS:
        if pattern.search(v):
            score += 0.15
            reasons.append(f"pattern:{pattern.pattern[:30]}")
            break  # Only count once

    # Conditional logic
    if re.search(r"\bif\b.*\bthen\b", v, re.IGNORECASE):
        score += 0.2
        reasons.append("conditional")

    # Negation
    if re.search(r"\bnot\b|\bnever\b|\bno\b", v, re.IGNORECASE):
        score += 0.1
        reasons.append("negation")

    # Modality
    if re.search(r"\bmust\b|\bshall\b|\bshould\b", v, re.IGNORECASE):
        score += 0.15
        reasons.append("modality_strong")
    elif re.search(r"\bmay\b|\bmight\b|\bcan\b", v, re.IGNORECASE):
        score += 0.1
        reasons.append("modality_weak")

    # Placeholders
    ph_count = len(re.findall(r"\{\{[^}]+\}\}|\{[^}]+\}|%[sd]", v))
    if ph_count > 0:
        score += 0.05 * ph_count
        reasons.append("placeholders:%d" % ph_count)

    return min(score, 1.0), reasons


def _content_hash(value: str) -> str:
    """Deterministic hash of the phrase content."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def extract_corpus(
    inventory_path: str,
    min_length: int = 30,
    min_complexity: float = 0.2,
) -> list[CorpusEntry]:
    """Extract phrases needing semantic analysis.

    Args:
        inventory_path: Path to M0 inventory JSON
        min_length: Minimum character length to consider
        min_complexity: Minimum complexity score to include

    Returns:
        List of CorpusEntry objects, sorted by complexity descending
    """
    with open(inventory_path, encoding="utf-8") as f:
        data = json.load(f)

    entries = []
    for key, entry in data["inventory"].items():
        # Skip passthrough
        if not entry.get("translatable", True):
            continue

        value = entry.get("value", "")
        if len(value) < min_length:
            continue

        # Classify and score
        phrase_type = _classify_phrase_type(value, entry.get("section", ""), key)
        complexity, reasons = _compute_complexity(value, entry.get("section", ""), key)

        if complexity < min_complexity and phrase_type == "description":
            continue

        corpus_entry = CorpusEntry(
            key=key,
            value=value,
            section=entry.get("section", ""),
            type=entry.get("type", "unknown"),
            length=len(value),
            placeholders=entry.get("placeholders", []),
            accelerators=entry.get("accelerators", []),
            phrase_type=phrase_type,
            complexity_score=complexity,
            reasons=reasons,
            content_hash=_content_hash(value),
        )
        entries.append(corpus_entry)

    # Sort by complexity descending
    entries.sort(key=lambda e: e.complexity_score, reverse=True)

    return entries


def save_corpus(entries: list[CorpusEntry], output_path: str) -> dict:
    """Save corpus to JSON with metadata.

    Returns stats dict.
    """
    corpus = {
        "meta": {
            "version": CORPUS_VERSION,
            "total_entries": len(entries),
            "phrase_types": {},
            "avg_complexity": 0.0,
        },
        "entries": [],
    }

    # Stats
    type_counts = {}
    total_complexity = 0.0
    for e in entries:
        type_counts[e.phrase_type] = type_counts.get(e.phrase_type, 0) + 1
        total_complexity += e.complexity_score

    corpus["meta"]["phrase_types"] = dict(sorted(type_counts.items()))
    corpus["meta"]["avg_complexity"] = (
        total_complexity / len(entries) if entries else 0.0
    )

    # Entries
    for e in entries:
        corpus["entries"].append({
            "key": e.key,
            "value": e.value,
            "section": e.section,
            "type": e.type,
            "length": e.length,
            "placeholders": e.placeholders,
            "accelerators": e.accelerators,
            "phrase_type": e.phrase_type,
            "complexity_score": round(e.complexity_score, 3),
            "reasons": e.reasons,
            "content_hash": e.content_hash,
        })

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(corpus, f, indent=2, ensure_ascii=False)

    return corpus["meta"]
