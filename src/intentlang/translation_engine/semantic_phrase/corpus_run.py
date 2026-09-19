"""
M6 — Assisted Corpus Run: process NEEDS_REVIEW phrases through semantic phrase pipeline.

This script processes phrases from the Phase 1 NEEDS_REVIEW set through the
semantic phrase engine. In strict mode (no LLM), it identifies which phrases
can be verified deterministically and which truly need human review.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from intentlang.translation_engine.semantic_phrase import (
    extract_semantics,
    verify_roundtrip,
    PhraseStatus,
)
from intentlang.translation_engine.semantic_phrase.corpus import (
    extract_corpus,
    CorpusEntry,
)


def load_needs_review_phrases(
    en_json_path: str,
    es_json_path: Optional[str] = None,
) -> list[dict]:
    """Load phrases that need review from Phase 1 output.

    Returns list of dicts with keys: key, source, target, section, status
    """
    en_path = Path(en_json_path)
    if not en_path.exists():
        return []

    with open(en_path, "r", encoding="utf-8") as f:
        en_data = json.load(f)

    es_data = {}
    if es_json_path:
        es_path = Path(es_json_path)
        if es_path.exists():
            with open(es_path, "r", encoding="utf-8") as f:
                es_data = json.load(f)

    phrases = []

    def get_nested(obj, keys):
        """Get value from nested dict using list of keys."""
        for key in keys:
            if isinstance(obj, dict) and key in obj:
                obj = obj[key]
            else:
                return None
        return obj

    def traverse(obj, path=None, section=""):
        if path is None:
            path = []

        if isinstance(obj, dict):
            for k, v in obj.items():
                new_path = path + [k]
                if isinstance(v, str):
                    # This is a leaf string - get target from ES
                    target = get_nested(es_data, new_path)
                    if target is None:
                        target = ""
                    # Determine status based on target content
                    if not target:
                        status = "missing"
                    elif target.startswith("[NEEDS_REVIEW]"):
                        status = "needs_review"
                    elif target == v:
                        status = "untranslated"
                    else:
                        status = "translated"
                    key_str = ".".join(new_path)
                    phrases.append({
                        "key": key_str,
                        "source": v,
                        "target": target,
                        "section": section or k,
                        "status": status,
                    })
                else:
                    traverse(v, new_path, section=k)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                new_path = path + [str(i)]
                if isinstance(item, str):
                    target = get_nested(es_data, new_path)
                    if target is None:
                        target = ""
                    if not target:
                        status = "missing"
                    elif target.startswith("[NEEDS_REVIEW]"):
                        status = "needs_review"
                    elif target == item:
                        status = "untranslated"
                    else:
                        status = "translated"
                    key_str = ".".join(new_path)
                    phrases.append({
                        "key": key_str,
                        "source": item,
                        "target": target,
                        "section": section,
                        "status": status,
                    })
                else:
                    traverse(item, new_path, section)

    traverse(en_data)

    # Return phrases with targets (translated or needs_review)
    return [p for p in phrases if p["target"] and p["status"] in ("translated", "needs_review")]


def run_corpus_analysis(
    en_json_path: str,
    es_json_path: str,
    output_path: str = "semantic_phrase_corpus_report.json",
) -> dict:
    """Run semantic phrase analysis on corpus.

    1. Load NEEDS_REVIEW phrases with targets
    2. Extract semantic invariants for source and target
    3. Verify roundtrip
    4. Categorize results
    """
    phrases = load_needs_review_phrases(en_json_path, es_json_path)

    results = {
        "total_phrases": len(phrases),
        "verified": 0,
        "needs_review": 0,
        "rejected": 0,
        "details": [],
    }

    for phrase in phrases:
        source = phrase["source"]
        target = phrase["target"]

        # Extract semantics
        source_extracted = extract_semantics(source)
        target_extracted = extract_semantics(target)

        # Verify roundtrip
        verify_result = verify_roundtrip(
            source=source,
            target=target,
            source_extracted=source_extracted,
            target_extracted=target_extracted,
        )

        # Categorize
        if verify_result.verdict == PhraseStatus.VERIFIED.value:
            results["verified"] += 1
        elif verify_result.verdict == PhraseStatus.NEEDS_REVIEW.value:
            results["needs_review"] += 1
        elif verify_result.verdict == PhraseStatus.REJECTED.value:
            results["rejected"] += 1

        results["details"].append({
            "key": phrase["key"],
            "source": source[:100],
            "target": target[:100],
            "verdict": verify_result.verdict,
            "pass_rate": round(verify_result.pass_rate, 3),
            "failed_checks": [
                c.field for c in verify_result.checks if not c.passed
            ],
            "source_facts": {
                "negated": source_extracted.negated,
                "modality": source_extracted.modality,
                "destructive": source_extracted.destructive,
                "is_warning": source_extracted.is_warning,
            },
            "target_facts": {
                "negated": target_extracted.negated,
                "modality": target_extracted.modality,
                "destructive": target_extracted.destructive,
                "is_warning": target_extracted.is_warning,
            },
        })

    # Save report
    output = Path(output_path)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    return results


def format_corpus_report(results: dict) -> str:
    """Format corpus report for display."""
    lines = [
        "=== Semantic Phrase Corpus Analysis ===",
        "Total phrases: %d" % results["total_phrases"],
        "Verified: %d" % results["verified"],
        "Needs review: %d" % results["needs_review"],
        "Rejected: %d" % results["rejected"],
        "",
        "=== Verdict Distribution ===",
    ]

    if results["total_phrases"] > 0:
        v_pct = results["verified"] / results["total_phrases"] * 100
        r_pct = results["needs_review"] / results["total_phrases"] * 100
        j_pct = results["rejected"] / results["total_phrases"] * 100
        lines.append("Verified: %.1f%%" % v_pct)
        lines.append("Needs review: %.1f%%" % r_pct)
        lines.append("Rejected: %.1f%%" % j_pct)

    # Show failed check distribution
    check_counts = {}
    for detail in results["details"]:
        for check in detail["failed_checks"]:
            check_counts[check] = check_counts.get(check, 0) + 1

    if check_counts:
        lines.append("")
        lines.append("=== Failed Check Distribution ===")
        for check, count in sorted(check_counts.items(), key=lambda x: -x[1]):
            lines.append("  %s: %d" % (check, count))

    # Show sample rejected phrases
    rejected = [d for d in results["details"] if d["verdict"] == "REJECTED"]
    if rejected:
        lines.append("")
        lines.append("=== Sample Rejected Phrases ===")
        for d in rejected[:5]:
            lines.append("  Key: %s" % d["key"])
            lines.append("    Source: %s" % d["source"])
            lines.append("    Target: %s" % d["target"])
            lines.append("    Failed: %s" % ", ".join(d["failed_checks"]))
            lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    en_path = sys.argv[1] if len(sys.argv) > 1 else "locales/en.json"
    es_path = sys.argv[2] if len(sys.argv) > 2 else "locales/es.json"
    output_path = sys.argv[3] if len(sys.argv) > 3 else "semantic_phrase_corpus_report.json"

    results = run_corpus_analysis(en_path, es_path, output_path)
    print(format_corpus_report(results))
