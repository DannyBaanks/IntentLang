"""
M1 — UI Message IR: the canonical representation for translatable UI strings.

This IR sits between raw locale strings and IntentLang's primitives.
It captures semantic invariants that survive translation:

  - canonical_id: stable identifier for the message
  - key: original locale key (e.g., "common.save")
  - section: UI section (e.g., "common", "settings")
  - type: UI context type (label, button, dialog, etc.)
  - value: the source string (en)
  - placeholders: tokens that must be preserved across translations
  - semantic: object, context, polarity, destructive flag
  - passthrough: whether this message should NOT be translated

Design decisions:
  - Placeholders are opaque tokens — the IR does not interpret them
  - Semantic fields are optional; if absent, the message is "untyped"
  - The IR is JSON-serializable and versioned
  - IntentLang integration happens at materialization time, not here

Usage:
    from ui_message_ir import UIMessageIR, build_ir_from_inventory
"""
from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass, field, asdict
from typing import Optional

IR_VERSION = "1.0.0"


@dataclass
class SemanticInvariants:
    """Semantic properties that must survive translation."""
    object: Optional[str] = None
    context: Optional[str] = None
    polarity: Optional[str] = None
    destructive: bool = False
    action: Optional[str] = None


@dataclass
class UIMessageIR:
    """A single translatable UI message in canonical form."""
    canonical_id: str
    key: str
    section: str
    type: str
    value: str
    placeholders: list[str] = field(default_factory=list)
    accelerators: list[str] = field(default_factory=list)
    semantic: Optional[SemanticInvariants] = None
    passthrough: bool = False
    skip_reason: Optional[str] = None
    length: int = 0
    ir_version: str = IR_VERSION

    def to_dict(self) -> dict:
        d = asdict(self)
        d["ir_version"] = IR_VERSION
        return d

    @classmethod
    def from_dict(cls, d: dict) -> UIMessageIR:
        sem = d.get("semantic")
        if sem and isinstance(sem, dict):
            sem = SemanticInvariants(**sem)
        return cls(
            canonical_id=d["canonical_id"],
            key=d["key"],
            section=d["section"],
            type=d["type"],
            value=d["value"],
            placeholders=d.get("placeholders", []),
            accelerators=d.get("accelerators", []),
            semantic=sem,
            passthrough=d.get("passthrough", False),
            skip_reason=d.get("skip_reason"),
            length=d.get("length", len(d.get("value", ""))),
            ir_version=d.get("ir_version", IR_VERSION),
        )

    def roundtrip_hash(self) -> str:
        """Hash of semantic invariants — used for roundtrip verification."""
        data = {
            "canonical_id": self.canonical_id,
            "section": self.section,
            "type": self.type,
            "placeholders": sorted(self.placeholders),
            "semantic": asdict(self.semantic) if self.semantic else None,
        }
        canonical = json.dumps(data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def build_ir_from_inventory(inventory_path: str) -> list[UIMessageIR]:
    """Build IR list from M0 inventory artifact."""
    with open(inventory_path, encoding="utf-8") as f:
        data = json.load(f)

    messages = []
    for key, entry in data["inventory"].items():
        passthrough = not entry.get("translatable", True)
        skip_reason = entry.get("skip_reason")
        semantic = _infer_semantics(key, entry)

        msg = UIMessageIR(
            canonical_id=key,
            key=key,
            section=entry.get("section", ""),
            type=entry.get("type", "unknown"),
            value=entry.get("value", ""),
            placeholders=entry.get("placeholders", []),
            accelerators=entry.get("accelerators", []),
            semantic=semantic,
            passthrough=passthrough,
            skip_reason=skip_reason,
            length=entry.get("length", 0),
        )
        messages.append(msg)

    return messages


def _infer_semantics(key: str, entry: dict) -> Optional[SemanticInvariants]:
    """Heuristic semantic inference from key name and type."""
    k = key.lower()
    v = entry.get("value", "").lower()
    t = entry.get("type", "")

    obj = None
    for noun, obj_name in [
        ("file", "FILE"), ("agent", "AGENT"), ("command", "COMMAND"),
        ("skill", "SKILL"), ("thread", "THREAD"), ("memory", "MEMORY"),
        ("webhook", "WEBHOOK"), ("schedule", "SCHEDULE"), ("queue", "QUEUE"),
        ("integration", "INTEGRATION"), ("token", "TOKEN"), ("worker", "WORKER"),
        ("git", "GIT"), ("badge", "BADGE"), ("office", "OFFICE"),
        ("kanban", "KANBAN"),
    ]:
        if noun in k:
            obj = obj_name
            break

    context = None
    if t == "dialog":
        context = "dialog"
    elif t == "tooltip":
        context = "tooltip"
    elif t == "placeholder":
        context = "input"
    elif t == "notification":
        context = "notification"
    elif t == "error":
        context = "error_message"

    polarity = "neutral"
    negative_words = {
        "delete", "remove", "destroy", "drop", "clear", "reset",
        "revoke", "disconnect", "disable", "deactivate", "ban",
        "discard", "deny", "reject", "cancel", "fail", "error",
        "warn", "warning", "blocked", "off",
    }
    positive_words = {
        "create", "add", "enable", "activate", "connect",
        "approve", "accept", "success", "ok", "done", "ready",
        "on", "start", "resume", "restart", "retry", "save",
        "confirm", "grant", "allow",
    }

    for word in negative_words:
        if word in k or word in v:
            polarity = "negative"
            break
    if polarity == "neutral":
        for word in positive_words:
            if word in k or word in v:
                polarity = "positive"
                break

    destructive = any(
        w in k
        for w in ["delete", "remove", "destroy", "drop", "clear", "reset", "ban"]
    )

    action = None
    for verb in ["save", "delete", "create", "open", "close", "copy", "move",
                  "edit", "send", "submit", "cancel", "confirm", "approve",
                  "reject", "connect", "disconnect", "enable", "disable",
                  "start", "stop", "pause", "resume", "retry", "upload",
                  "download", "export", "import", "share", "search", "filter"]:
        if verb in k:
            action = verb
            break

    if obj or context or polarity != "neutral" or destructive or action:
        return SemanticInvariants(
            object=obj,
            context=context,
            polarity=polarity,
            destructive=destructive,
            action=action,
        )
    return None
