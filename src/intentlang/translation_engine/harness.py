"""
M5 — Validation Harness: automated pipeline for locale generation.

Runs the full M0→M1→M2→M3→M4 pipeline and generates a report.

Usage:
    py harness.py --source path/to/en.json --target-lang es --output-dir output/
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from intentlang.translation_engine.context_resolver import enrich_inventory_with_context
from intentlang.translation_engine.extractor import build_inventory, generate_hash
from intentlang.translation_engine.materializer import materialize_locale
from intentlang.translation_engine.roundtrip_verifier import verify_roundtrip
from intentlang.translation_engine.ui_message_ir import IR_VERSION, build_ir_from_inventory


def run_harness(
    source_path: str,
    target_lang: str,
    output_dir: str,
) -> dict:
    """Run the full pipeline and return results dict."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    results: dict[str, Any] = {
        "timestamp": datetime.now(UTC).isoformat(),
        "source": source_path,
        "target_lang": target_lang,
        "ir_version": IR_VERSION,
        "steps": {},
    }

    # Step 1: Extract inventory (M0)
    print("[M0] Extracting inventory...")
    inventory_path = str(output / "inventory.json")
    inventory = build_inventory(source_path)
    inv_hash = generate_hash(inventory)

    # Write inventory
    total = len(inventory)
    translatable = sum(1 for v in inventory.values() if v["translatable"])
    skipped = total - translatable
    sections = {v["section"] for v in inventory.values()}

    inventory_output = {
        "meta": {
            "source_file": source_path,
            "source_hash": inv_hash,
            "total_keys": total,
            "translatable": translatable,
            "skipped": skipped,
            "sections": sorted(sections),
        },
        "inventory": inventory,
    }
    with open(inventory_path, "w", encoding="utf-8") as f:
        json.dump(inventory_output, f, indent=2, ensure_ascii=False)

    results["steps"]["M0"] = {
        "status": "OK",
        "total_keys": total,
        "translatable": translatable,
        "skipped": skipped,
        "sections": len(sections),
        "hash": inv_hash,
    }
    print(f"  Keys: {total}, Translatable: {translatable}, Skipped: {skipped}")

    # Step 2: Build IR (M1)
    print("[M1] Building IR...")
    enriched_path = str(output / "inventory_enriched.json")

    # Copy inventory as enriched (context enrichment happens in M2)
    with open(inventory_path, encoding="utf-8") as f:
        inv_data = json.load(f)
    with open(enriched_path, "w", encoding="utf-8") as f:
        json.dump(inv_data, f, indent=2, ensure_ascii=False)

    messages = build_ir_from_inventory(inventory_path)
    with_semantic = sum(1 for m in messages if m.semantic)

    results["steps"]["M1"] = {
        "status": "OK",
        "ir_messages": len(messages),
        "with_semantic": with_semantic,
    }
    print(f"  IR messages: {len(messages)}, With semantic: {with_semantic}")

    # Step 3: Context resolution (M2)
    print("[M2] Resolving context...")
    ctx_stats = enrich_inventory_with_context(inventory_path, enriched_path)

    results["steps"]["M2"] = {
        "status": "OK",
        "resolved": ctx_stats["resolved"],
        "ambiguous": ctx_stats["ambiguous"],
    }
    print(f"  Resolved: {ctx_stats['resolved']}, Ambiguous: {ctx_stats['ambiguous']}")

    # Step 4: Materialize target locale (M3)
    print(f"[M3] Materializing {target_lang} locale...")
    locale_path = str(output / (f"locale_{target_lang}.json"))
    mat_stats = materialize_locale(inventory_path, target_lang, locale_path)

    results["steps"]["M3"] = {
        "status": "OK",
        "translated": mat_stats["translated"],
        "untranslated": mat_stats["untranslated"],
        "passthrough": mat_stats["passthrough"],
    }
    print(
        f"  Translated: {mat_stats['translated']}, Untranslated: {mat_stats['untranslated']}, "
        f"Passthrough: {mat_stats['passthrough']}"
    )

    # Step 5: Roundtrip verification (M4)
    print("[M4] Verifying roundtrip...")
    rt_result = verify_roundtrip(inventory_path, locale_path)

    results["steps"]["M4"] = {
        "status": "OK" if rt_result.failed == 0 else "FAIL",
        "checked": rt_result.checked,
        "passed": rt_result.passed,
        "failed": rt_result.failed,
        "pass_rate": f"{rt_result.pass_rate * 100:.1f}%",
        "mismatches": [
            {"key": m.key, "field": m.field, "source": m.source_value, "target": m.target_value}
            for m in rt_result.mismatches[:20]
        ],
    }
    print(
        f"  Checked: {rt_result.checked}, Passed: {rt_result.passed}, "
        f"Failed: {rt_result.failed} ({rt_result.pass_rate * 100:.1f}%)"
    )

    # Overall status
    all_ok = all(s["status"] == "OK" for s in results["steps"].values())
    results["overall_status"] = "PASS" if all_ok else "FAIL"

    # Report paths and payload must be finalized before either report is
    # serialized. Previously overall_status was added after the JSON report was
    # written, so callers received PASS while the persisted evidence omitted it.
    report_path = str(output / "harness_report.json")
    readable_path = str(output / "HARNESS_REPORT.md")
    results["report"] = report_path
    results["readable_report"] = readable_path

    # Write report
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Write human-readable report
    with open(readable_path, "w", encoding="utf-8") as f:
        f.write("# i18n Harness Report\n\n")
        f.write("**Timestamp:** {}\n".format(results["timestamp"]))
        f.write(f"**Source:** {source_path}\n")
        f.write(f"**Target:** {target_lang}\n")
        f.write(f"**IR Version:** {IR_VERSION}\n")
        f.write("**Overall:** {}\n\n".format(results["overall_status"]))

        for step, info in sorted(results["steps"].items()):
            status = info.get("status", "UNKNOWN")
            f.write(f"## {step} [{status}]\n\n")
            for k, v in info.items():
                if k == "status":
                    continue
                f.write(f"- **{k}:** {v}\n")
            f.write("\n")

        if rt_result.mismatches:
            f.write("## Mismatches\n\n")
            for m in rt_result.mismatches[:20]:
                f.write(f"- `{m.key}` [{m.field}]: `{m.source_value}` → `{m.target_value}`\n")
            if len(rt_result.mismatches) > 20:
                f.write(f"- ... and {len(rt_result.mismatches) - 20} more\n")

    print(f"\n=== Overall: {results['overall_status']} ===")
    print(f"Report: {report_path}")

    return results


def main():
    parser = argparse.ArgumentParser(description="M5 — i18n Validation Harness")
    parser.add_argument("--source", required=True, help="Path to canonical locale JSON")
    parser.add_argument("--target-lang", required=True, help="Target language code")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    args = parser.parse_args()

    results = run_harness(args.source, args.target_lang, args.output_dir)
    sys.exit(0 if results["overall_status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
