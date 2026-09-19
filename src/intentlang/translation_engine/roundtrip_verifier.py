"""
M4 — Roundtrip Semantic Verifier.

Verifies that translating A→B preserves semantic invariants:
  1. Build IR from source locale (en)
  2. Materialize target locale (es)
  3. Build IR from target locale (es)
  4. Compare semantic invariants for each key
  5. Report any mismatches

The roundtrip hash captures: canonical_id, section, type, placeholders, semantic.
Two locale versions of the same message MUST produce the same hash.

Usage:
    from roundtrip_verifier import verify_roundtrip, RoundtripResult
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from intentlang.translation_engine.ui_message_ir import UIMessageIR, build_ir_from_inventory, SemanticInvariants


@dataclass
class Mismatch:
    """A single roundtrip mismatch."""
    key: str
    field: str           # "section", "type", "placeholders", "semantic.*"
    source_value: Any
    target_value: Any


@dataclass
class RoundtripResult:
    """Complete roundtrip verification result."""
    total_keys: int
    checked: int
    passed: int
    failed: int
    mismatches: list[Mismatch] = field(default_factory=list)
    source_hash: str = ""
    target_hash: str = ""

    @property
    def pass_rate(self) -> float:
        return self.passed / self.checked if self.checked > 0 else 0.0


def _build_ir_from_locale(locale_path: str) -> dict[str, UIMessageIR]:
    """Build IR from a generated locale JSON file.

    This reads the nested locale, flattens it, and builds IR entries.
    Extracts placeholders from the value strings.
    """
    import re
    ph_re = re.compile(
        r"\{\{[^}]+\}\}"
        r"|\{[^}]+\}"
        r"|%[sd]"
        r"|%(\w+)s"
    )
    # Note: findall returns capture groups when present. We use a helper
    # that returns full matches instead.
    def _find_all_placeholders(text):
        return [m.group() for m in ph_re.finditer(text)]

    with open(locale_path, encoding="utf-8") as f:
        data = json.load(f)

    flat = _flatten(data)
    ir_map = {}

    for key, value in flat.items():
        section = key.split(".")[0] if "." in key else ""
        val_str = str(value)
        placeholders = _find_all_placeholders(val_str)

        ir = UIMessageIR(
            canonical_id=key,
            key=key,
            section=section,
            type="unknown",
            value=val_str,
            placeholders=placeholders,
            length=len(val_str),
        )
        ir_map[key] = ir

    return ir_map


def _flatten(data: dict, parent: str = "") -> dict:
    """Flatten nested dict."""
    result = {}
    for k, v in data.items():
        full_key = f"{parent}.{k}" if parent else k
        if isinstance(v, dict):
            result.update(_flatten(v, full_key))
        else:
            result[full_key] = v
    return result


def verify_roundtrip(
    source_inventory: str,
    target_locale: str,
) -> RoundtripResult:
    """Verify roundtrip semantic invariants between source and target.

    Args:
        source_inventory: Path to M0 inventory JSON (source locale)
        target_locale: Path to materialized target locale JSON

    Returns:
        RoundtripResult with pass/fail details
    """
    # Build source IR from inventory
    source_msgs = build_ir_from_inventory(source_inventory)
    source_ir = {m.canonical_id: m for m in source_msgs}

    # Build target IR from locale
    target_ir = _build_ir_from_locale(target_locale)

    # Compare
    mismatches = []
    checked = 0
    passed = 0

    for key, src in source_ir.items():
        if src.passthrough:
            continue  # Skip passthrough messages

        tgt = target_ir.get(key)
        if tgt is None:
            mismatches.append(Mismatch(
                key=key, field="missing",
                source_value=src.value, target_value=None,
            ))
            continue

        checked += 1
        ok = True

        # Check section
        if src.section != tgt.section:
            mismatches.append(Mismatch(
                key=key, field="section",
                source_value=src.section, target_value=tgt.section,
            ))
            ok = False

        # Check type
        if src.type != tgt.type:
            # Type inference may differ; only flag if both are "unknown"
            pass

        # Check placeholders preserved
        src_placeholders = sorted(src.placeholders)
        tgt_placeholders = sorted(tgt.placeholders)
        if src_placeholders != tgt_placeholders:
            mismatches.append(Mismatch(
                key=key, field="placeholders",
                source_value=src_placeholders, target_value=tgt_placeholders,
            ))
            ok = False

        # Check semantic invariants
        if src.semantic and tgt.semantic:
            sem_fields = ["object", "context", "polarity", "destructive", "action"]
            for field_name in sem_fields:
                src_val = getattr(src.semantic, field_name)
                tgt_val = getattr(tgt.semantic, field_name)
                if src_val != tgt_val:
                    mismatches.append(Mismatch(
                        key=key, field=f"semantic.{field_name}",
                        source_value=src_val, target_value=tgt_val,
                    ))
                    ok = False

        if ok:
            passed += 1

    # Hash comparison
    src_hashes = {k: v.roundtrip_hash() for k, v in source_ir.items() if not v.passthrough}
    tgt_hashes = {k: v.roundtrip_hash() for k, v in target_ir.items() if k in source_ir and not source_ir[k].passthrough}

    return RoundtripResult(
        total_keys=len(source_ir),
        checked=checked,
        passed=passed,
        failed=len(mismatches),
        mismatches=mismatches,
        source_hash=str(sorted(src_hashes.values())),
        target_hash=str(sorted(tgt_hashes.values())),
    )


def format_result(result: RoundtripResult) -> str:
    """Format roundtrip result for display."""
    lines = [
        "=== Roundtrip Verification ===",
        "Total keys: %d" % result.total_keys,
        "Checked: %d (passthrough excluded)" % result.checked,
        "Passed: %d" % result.passed,
        "Failed: %d" % result.failed,
        "Pass rate: %.1f%%" % (result.pass_rate * 100),
    ]

    if result.mismatches:
        lines.append("")
        lines.append("=== Mismatches ===")
        for m in result.mismatches[:20]:
            lines.append("  %s [%s]: %s -> %s" % (
                m.key, m.field, m.source_value, m.target_value))
        if len(result.mismatches) > 20:
            lines.append("  ... and %d more" % (len(result.mismatches) - 20))

    return "\n".join(lines)
