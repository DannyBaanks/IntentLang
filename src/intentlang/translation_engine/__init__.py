"""
Translation Engine — roundtrip locale generation for React i18next projects.

This module provides a complete pipeline for translating UI strings:
  1. Extract inventory from source locale (M0)
  2. Build UI Message IR with semantic invariants (M1)
  3. Resolve context for homographs (M2)
  4. Materialize target locale (M3)
  5. Verify roundtrip semantic invariants (M4)
  6. Run automated validation harness (M5)

Usage as library:
    from intentlang.translation_engine import run_pipeline
    results = run_pipeline("en.json", "es", "output/")

Usage as CLI:
    python -m intentlang.translation_engine.cli --source en.json --target-lang es --output-dir output/
"""
from __future__ import annotations

from intentlang.translation_engine.context_resolver import (
    ContextHint,
    enrich_inventory_with_context,
    resolve_context,
)
from intentlang.translation_engine.extractor import build_inventory, generate_hash
from intentlang.translation_engine.harness import run_harness
from intentlang.translation_engine.materializer import (
    materialize_locale,
    materialize_single,
)
from intentlang.translation_engine.roundtrip_verifier import (
    RoundtripResult,
    verify_roundtrip,
)
from intentlang.translation_engine.ui_message_ir import (
    IR_VERSION,
    SemanticInvariants,
    UIMessageIR,
    build_ir_from_inventory,
)


def run_pipeline(
    source_path: str,
    target_lang: str,
    output_dir: str,
) -> dict:
    """Run the full translation pipeline.

    Args:
        source_path: Path to canonical locale JSON (e.g., en.json)
        target_lang: Target language code (e.g., es, fr, ja)
        output_dir: Output directory for generated files

    Returns:
        Results dict with status, stats, and file paths
    """
    return run_harness(source_path, target_lang, output_dir)


__all__ = [
    "IR_VERSION",
    "ContextHint",
    "RoundtripResult",
    "SemanticInvariants",
    "UIMessageIR",
    "build_inventory",
    "build_ir_from_inventory",
    "enrich_inventory_with_context",
    "generate_hash",
    "materialize_locale",
    "materialize_single",
    "resolve_context",
    "run_harness",
    "run_pipeline",
    "verify_roundtrip",
]
