"""
M2 — Semantic Extractor: deterministic extraction of phrase invariants.

Extracts semantic properties from phrases using pattern matching and
linguistic heuristics. No LLM involved — this is the deterministic base.

The LLM can later PROPOSE additional fields, but these are the ground truth.

Usage:
    from semantic_phrase.extractor import extract_semantics, ExtractedFacts
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

# ── Pattern Libraries ────────────────────────────────────────────────

# Negation markers
NEGATION_RE = re.compile(
    r"\bnot\b|\bnever\b|\bno\b|\bcannot\b|\bcan't\b|\bwon't\b"
    r"|\bdon't\b|\bdoesn't\b|\bdidn't\b|\bisn't\b|\baren't\b"
    r"|\bwasn't\b|\bweren't\b|\bhasn't\b|\bhaven't\b|\bhadn't\b"
    r"|\bmustn't\b|\bshall not\b|\bshould not\b|\bwill not\b"
    r"|\bcould not\b|\bwould not\b|\bdo not\b",
    re.IGNORECASE,
)

# Modal markers
MODAL_PATTERNS = {
    "MUST": re.compile(r"\bmust\b|\bshall\b", re.IGNORECASE),
    "SHOULD": re.compile(r"\bshould\b", re.IGNORECASE),
    "MAY": re.compile(r"\bmay\b|\bmight\b", re.IGNORECASE),
    "CAN": re.compile(r"\bcan\b|\bcould\b", re.IGNORECASE),
    "WILL": re.compile(r"\bwill\b|\bshall\b", re.IGNORECASE),
}

# Destructive keywords
DESTRUCTIVE_RE = re.compile(
    r"\bdelete\b|\bdeleted\b|\bdeleting\b|\bremove\b|\bremoved\b|\bremoving\b"
    r"|\bdestroy\b|\bdiscard\b|\bdrop\b"
    r"|\bclear\b|\breset\b|\brevoke\b|\bban\b|\bterminate\b"
    r"|\bdisconnect\b|\bdisable\b|\bdeactivate\b|\bunsubscribe\b"
    r"|\boverwrite\b|\breplace\b",
    re.IGNORECASE,
)

# Warning keywords
WARNING_RE = re.compile(
    r"\bwarning\b|\bcaution\b|\bdanger\b|\brisk\b|\bcareful\b"
    r"|\bnote\b|\bimportant\b|\bcritical\b|\burgent\b",
    re.IGNORECASE,
)

# Confirmation keywords
CONFIRMATION_RE = re.compile(
    r"\bconfirm\b|\bare you sure\b|\bdo you want\b|\bproceed\b"
    r"|\bthis action\b|\bthis will\b|\bby continuing\b",
    re.IGNORECASE,
)

# Consequence markers
CONSEQUENCE_RE = re.compile(
    r"\bwill\b.*\b(delete|remove|discard|lose|destroy|reset|clear)\b"
    r"|\bcannot be undone\b|\bpermanent\b|\bpermanently\b"
    r"|\bthis will\b|\bresult in\b",
    re.IGNORECASE,
)

# Conditional markers
CONDITION_RE = re.compile(
    r"\bif\b.*\bthen\b|\bunless\b|\bwhen\b.*\bwill\b"
    r"|\bprovided that\b|\bin case\b|\bshould\b.*\boccur\b",
    re.IGNORECASE,
)

# Number extraction
NUMBER_RE = re.compile(r"\b(\d+(?:\.\d+)?)\b")

# Unit patterns
UNIT_RE = re.compile(
    r"\b(tokens?|bytes?|KB|MB|GB|TB|ms|seconds?|minutes?|hours?|days?|weeks?|months?|years?|%)"
    r"\b",
    re.IGNORECASE,
)

# Protected tokens (shortcuts, technical identifiers)
SHORTCUT_RE = re.compile(
    r"Ctrl\+[A-Z]|Cmd\+[A-Z]|Alt\+[A-Z]|Shift\+[A-Z]"
    r"|⌘[A-Z]|⌥[A-Z]|⇧[A-Z]",
)

# Technical terms (programming/CLI)
TECHNICAL_RE = re.compile(
    r"\b(API|SDK|CLI|SSH|HTTP|HTTPS|URL|JSON|YAML|XML|HTML|CSS|JS|TS)"
    r"|\b(React|Electron|Node|TypeScript|JavaScript|Python|Rust|Go)"
    r"|\b(Git|GitHub|GitLab|npm|npx|yarn|pnpm)"
    r"|\b(Docker|Kubernetes|AWS|GCP|Azure)"
    r"|\b(MCP|OAuth|WebSocket|gRPC|REST|GraphQL)\b",
    re.IGNORECASE,
)

# Slot patterns (variables in templates)
SLOT_RE = re.compile(
    r"\{\{[^}]+\}\}"     # {{varName}}
    r"|\{[^}]+\}"         # {0}, {count}
    r"|%[sd]"             # %s, %d
    r"|%(\w+)s"           # %(name)s - group 1
)

# Non-capturing version for findall
SLOT_FINDALL_RE = re.compile(
    r"\{\{[^}]+\}\}"     # {{varName}}
    r"|\{[^}]+\}"         # {0}, {count}
    r"|%[sd]"             # %s, %d
)


@dataclass
class ExtractedFacts:
    """Deterministically extracted semantic facts from a phrase."""
    # Source text
    source_surface: str
    source_locale: str

    # Extracted facts
    negated: bool = False
    negation_markers: list[str] = field(default_factory=list)

    modality: str = "NONE"
    modal_markers: list[str] = field(default_factory=list)

    destructive: bool = False
    destructive_keywords: list[str] = field(default_factory=list)

    is_warning: bool = False
    warning_keywords: list[str] = field(default_factory=list)

    is_confirmation: bool = False
    confirmation_keywords: list[str] = field(default_factory=list)

    conditions: list[str] = field(default_factory=list)
    consequences: list[str] = field(default_factory=list)

    numbers: list[str] = field(default_factory=list)
    units: list[str] = field(default_factory=list)

    protected_tokens: list[str] = field(default_factory=list)
    technical_terms: list[str] = field(default_factory=list)
    slots: list[str] = field(default_factory=list)

    # Extraction metadata
    facts: list[str] = field(default_factory=list)  # observed_fact entries
    candidates: list[str] = field(default_factory=list)  # inferred_candidate entries

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return {
            "source_surface": self.source_surface,
            "source_locale": self.source_locale,
            "negated": self.negated,
            "negation_markers": self.negation_markers,
            "modality": self.modality,
            "modal_markers": self.modal_markers,
            "destructive": self.destructive,
            "destructive_keywords": self.destructive_keywords,
            "is_warning": self.is_warning,
            "warning_keywords": self.warning_keywords,
            "is_confirmation": self.is_confirmation,
            "confirmation_keywords": self.confirmation_keywords,
            "conditions": self.conditions,
            "consequences": self.consequences,
            "numbers": self.numbers,
            "units": self.units,
            "protected_tokens": self.protected_tokens,
            "technical_terms": self.technical_terms,
            "slots": self.slots,
            "facts": self.facts,
            "candidates": self.candidates,
        }


def _extract_modality(text: str) -> tuple[str, list[str]]:
    """Extract modal strength from text."""
    markers = []
    for modal, pattern in MODAL_PATTERNS.items():
        matches = pattern.findall(text)
        if matches:
            markers.extend(matches)
            # Return first match priority: MUST > SHALL > SHOULD > WILL > MAY > CAN
            if modal in ("MUST", "SHALL"):
                return "MUST", markers
            if modal == "SHOULD":
                return "SHOULD", markers
            if modal == "WILL":
                return "WILL", markers
            if modal in ("MAY",):
                return "MAY", markers
            if modal == "CAN":
                return "CAN", markers

    # Check for imperative mood (no subject, command form)
    words = text.strip().split()
    if words and words[0].lower() in (
        "delete", "remove", "close", "open", "save", "copy", "move",
        "click", "press", "enter", "select", "type", "hold", "drag",
        "confirm", "approve", "reject", "cancel", "submit",
    ):
        return "MUST", ["imperative"]

    return "NONE", []


def _extract_conditions(text: str) -> list[str]:
    """Extract conditional clauses."""
    conditions = []
    # "if X then Y"
    for match in re.finditer(r"\bif\b\s+(.+?)\s+then\b", text, re.IGNORECASE):
        conditions.append(match.group(1).strip())
    # "if X, Y" (without then)
    for match in re.finditer(r"\bif\b\s+(.+?),", text, re.IGNORECASE):
        cond = match.group(1).strip()
        if cond not in conditions:  # avoid duplicates
            conditions.append(cond)
    # "unless X"
    for match in re.finditer(r"\bunless\b\s+(.+?)(?:\.|,|$)", text, re.IGNORECASE):
        conditions.append("NOT: " + match.group(1).strip())
    # "when X"
    for match in re.finditer(r"\bwhen\b\s+(.+?)(?:\.|,|$)", text, re.IGNORECASE):
        conditions.append(match.group(1).strip())
    return conditions


def _extract_consequences(text: str) -> list[str]:
    """Extract consequence phrases."""
    consequences = []
    # "will X" where X is destructive
    for match in re.finditer(r"\bwill\b\s+(.+?)(?:\.|,|$)", text, re.IGNORECASE):
        consequences.append(match.group(1).strip())
    # "this will X"
    for match in re.finditer(r"\bthis will\b\s+(.+?)(?:\.|,|$)", text, re.IGNORECASE):
        consequences.append(match.group(1).strip())
    # "cannot be undone"
    if re.search(r"\bcannot be undone\b", text, re.IGNORECASE):
        consequences.append("irreversible")
    return consequences


def extract_semantics(surface: str, locale: str = "en") -> ExtractedFacts:
    """Extract semantic facts from a phrase deterministically.

    This is the M2 extractor — pure pattern matching, no LLM.

    Args:
        surface: The source phrase text
        locale: Source locale code

    Returns:
        ExtractedFacts with all deterministic observations
    """
    facts = ExtractedFacts(source_surface=surface, source_locale=locale)

    # Negation
    neg_matches = NEGATION_RE.findall(surface)
    if neg_matches:
        facts.negated = True
        facts.negation_markers = list(set(neg_matches))
        facts.facts.append("observed_fact: negation detected")

    # Modality
    modal, modal_markers = _extract_modality(surface)
    facts.modality = modal
    facts.modal_markers = modal_markers
    if modal != "NONE":
        facts.facts.append("observed_fact: modality=%s" % modal)

    # Destructive
    dest_matches = DESTRUCTIVE_RE.findall(surface)
    if dest_matches:
        facts.destructive = True
        facts.destructive_keywords = list(set(dest_matches))
        facts.facts.append("observed_fact: destructive action")

    # Warning
    warn_matches = WARNING_RE.findall(surface)
    if warn_matches:
        facts.is_warning = True
        facts.warning_keywords = list(set(warn_matches))
        facts.facts.append("observed_fact: warning speech act")

    # Confirmation
    conf_matches = CONFIRMATION_RE.findall(surface)
    if conf_matches:
        facts.is_confirmation = True
        facts.confirmation_keywords = list(set(conf_matches))
        facts.facts.append("observed_fact: confirmation required")

    # Conditions
    facts.conditions = _extract_conditions(surface)
    if facts.conditions:
        facts.facts.append("observed_fact: conditional logic")

    # Consequences
    facts.consequences = _extract_consequences(surface)
    if facts.consequences:
        facts.facts.append("observed_fact: consequences specified")

    # Numbers
    num_matches = NUMBER_RE.findall(surface)
    if num_matches:
        facts.numbers = list(set(num_matches))
        facts.facts.append("observed_fact: numeric quantities")

    # Units
    unit_matches = UNIT_RE.findall(surface)
    if unit_matches:
        facts.units = list(set(unit_matches))
        facts.facts.append("observed_fact: units present")

    # Protected tokens (shortcuts)
    shortcut_matches = SHORTCUT_RE.findall(surface)
    if shortcut_matches:
        facts.protected_tokens = list(set(shortcut_matches))
        facts.facts.append("observed_fact: keyboard shortcuts")

    # Technical terms
    tech_matches = TECHNICAL_RE.findall(surface)
    if tech_matches:
        # flatten tuples from groups
        flat = []
        for t in tech_matches:
            if isinstance(t, tuple):
                flat.extend(x for x in t if x)
            else:
                flat.append(t)
        facts.technical_terms = list(set(flat))
        facts.facts.append("observed_fact: technical terms")

    # Slots/placeholders
    slot_matches = SLOT_FINDALL_RE.findall(surface)
    if slot_matches:
        facts.slots = list(set(slot_matches))
        facts.facts.append("observed_fact: template slots")

    # Inferred candidates (not deterministic, but high-confidence inferences)
    if facts.destructive and facts.is_warning:
        facts.candidates.append("inferred_candidate: requires_confirmation=true")
    if facts.negated and facts.destructive:
        facts.candidates.append("inferred_candidate: safety_negation=true")
    if facts.modality == "MUST" and facts.destructive:
        facts.candidates.append("inferred_candidate: forced_destructive=true")

    return facts
