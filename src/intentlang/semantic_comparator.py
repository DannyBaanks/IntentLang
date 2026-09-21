"""Score candidate translations against a language-independent Meaning IR."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .meaning_ir import Meaning
from .meaning_parser import parse_meaning


def compare_candidates(expected: Meaning, candidates: Mapping[str, str]) -> dict[str, Any]:
    """Classify candidate outputs as semantic passes, mismatches, or unresolved.

    Exact wording is intentionally irrelevant.  A candidate passes only when
    its conservative parser recovers the same Meaning key and status.
    """
    failures: list[dict[str, Any]] = []
    passes = 0
    for language, text in candidates.items():
        actual = parse_meaning(text, language)
        if actual.status != "RESOLVED":
            failures.append({"language": language, "reason": "unresolved", "text": text})
        elif actual.key() != expected.key() or actual.status != expected.status:
            failures.append({
                "language": language, "reason": "meaning_mismatch", "text": text,
                "actual_key": actual.key(), "expected_key": expected.key(),
            })
        else:
            passes += 1
    return {
        "languages": len(candidates),
        "semantic_passes": passes,
        "semantic_failures": len(failures),
        "failures": failures,
    }


__all__ = ["compare_candidates"]
