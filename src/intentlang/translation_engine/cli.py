"""
M7 — i18n CLI: reusable tool for any React i18next project.

Usage:
    py i18n_cli.py --source path/to/en.json --target-lang es --output-dir output/
    py i18n_cli.py --source path/to/en.json --target-lang fr --output-dir output/
    py i18n_cli.py --source path/to/en.json --target-lang ja --output-dir output/

The CLI runs the full pipeline:
  M0: Extract inventory from source locale
  M1: Build UI Message IR
  M2: Resolve context for homographs
  M3: Materialize target locale
  M4: Verify roundtrip semantic invariants
  M5: Generate report

Output:
  - inventory.json: classified source strings
  - locale_<lang>.json: translated locale file
  - HARNESS_REPORT.md: human-readable report
  - harness_report.json: machine-readable report
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from intentlang.translation_engine.harness import run_harness


def main():

    parser = argparse.ArgumentParser(
        description="i18n CLI — roundtrip translation engine for React i18next projects",
        epilog="Example: py i18n_cli.py --source src/locales/en.json --target-lang es --output-dir output/"
    )
    parser.add_argument(
        "--source", required=True,
        help="Path to canonical locale JSON (e.g., en.json)"
    )
    parser.add_argument(
        "--target-lang", required=True,
        help="Target language code (e.g., es, fr, ja, zh, de)"
    )
    parser.add_argument(
        "--output-dir", required=True,
        help="Output directory for generated files"
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="Suppress progress output"
    )

    args = parser.parse_args()

    # Validate source exists
    source = Path(args.source)
    if not source.exists():
        print(f"ERROR: Source file not found: {source}")
        sys.exit(1)

    # Run pipeline
    try:
        results = run_harness(args.source, args.target_lang, args.output_dir)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    # Exit code
    if results["overall_status"] == "PASS":
        if not args.quiet:
            print(f"\nDone. Locale generated at: {results.get('readable_report', '')}")
        sys.exit(0)
    else:
        print("\nFAILED. Check report for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()
