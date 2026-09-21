"""Redact credentials before text leaves the local process."""
from __future__ import annotations

import re

_SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization\s*:\s*bearer\s+)[^\s,;]+"),
    re.compile(r"\b(?:sk|rk|pk)-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
    re.compile(r"\bnvapi-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\b(?:ghp|github_pat)_[A-Za-z0-9_]{12,}\b"),
)


def sanitize(value: str) -> str:
    """Redact common provider credentials without changing ordinary prose."""
    result = value
    for pattern in _SECRET_PATTERNS:
        result = pattern.sub(lambda match: f"{match.group(1)}[REDACTED]" if match.lastindex else "[REDACTED]", result)
    return result


__all__ = ["sanitize"]
