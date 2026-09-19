"""
M0 — Inventory Extractor for i18n locale files.

Reads a canonical locale JSON (e.g., en.json), flattens all keys,
classifies each string by UI context type, and produces a reproducible
inventory artifact.

Usage:
    py extractor.py --source path/to/en.json --output inventory.json
"""
from __future__ import annotations

import argparse
import json
import re
import hashlib
from pathlib import Path
from typing import Any

# ── Classification patterns ──────────────────────────────────────────

# Placeholders like {{varName}}, {0}, %s, %d
PLACEHOLDER_RE = re.compile(
    r"\{\{[^}]+\}\}"    # {{varName}}
    r"|\{[^}]+\}"       # {0}, {count}
    r"|%[sd]"            # %s, %d
    r"|%\(\w+\)s"        # %(name)s
)

# Keyboard accelerators: &x (GTK), _x (Qt), Ctrl+X, Cmd+X
ACCELERATOR_RE = re.compile(
    r"&[a-zA-Z]"         # &S (save)
    r"|_[a-zA-Z]"        # _S (save)
    r"|Ctrl\+[a-zA-Z]"   # Ctrl+S
    r"|Cmd\+[a-zA-Z]"    # Cmd+S
    r"|Alt\+[a-zA-Z]"    # Alt+S
    r"|Shift\+[a-zA-Z]"  # Shift+S
    r"|\bCtrl\b"
    r"|\bCmd\b"
    r"|\bAlt\b"
    r"|\bShift\b"
)

# Technical tokens that should NOT be translated
TECHNICAL_TOKENS = {
    "MCP", "OAuth", "API", "SDK", "CLI", "SSH", "HTTP", "HTTPS", "URL",
    "JSON", "YAML", "XML", "HTML", "CSS", "JS", "TS", "TSX", "JSX",
    "Node", "Node.js", "React", "Electron", "Vite", "TypeScript",
    "JavaScript", "Python", "Rust", "Go", "C++", "C#", "Java",
    "Git", "GitHub", "GitLab", "npm", "npx", "yarn", "pnpm",
    "VSCode", "VS Code", "Cursor", "Windsurf",
    "OpenAI", "Anthropic", "Claude", "GPT", "Gemini", "Llama",
    "WebSocket", "gRPC", "REST", "GraphQL",
    "SQLite", "PostgreSQL", "MySQL", "Redis", "MongoDB",
    "Docker", "Kubernetes", "AWS", "GCP", "Azure",
    "Markdown", "LaTeX", "PDF", "PNG", "JPG", "SVG",
    "USB", "TLS", "SSL", "SSH", "DNS", "TCP", "UDP",
    "IDE", "LSP", "DAP", "AST", "IR", " REPL",
    "Ada", "Munder Difflin", "munder-difflin",
    "/skill", "/help",
}

# Brand names / proper nouns that should not be translated
BRAND_PATTERNS = re.compile(
    r"^(?:Ada|Munder|Difflin|Michael)$"  # known app god name / app name
)

# Section → type heuristics
SECTION_TYPE_MAP = {
    "common": "label",
    "commandBar": "input",
    "blockedBanner": "notification",
    "costHud": "hud",
    "badge": "label",
    "settings": "settings",
    "sidebar": "navigation",
    "threads": "navigation",
    "kanban": "board",
    "office": "workspace",
    "officeTheme": "theme",
    "onboarding": "dialog",
    "setupPanel": "dialog",
    "settingsHero": "settings",
    "gitPanes": "panel",
    "gitTab": "tab",
    "fileEditor": "editor",
    "fileTree": "navigation",
    "idePanel": "panel",
    "imagePreview": "preview",
    "integrations": "settings",
    "memoryGraph": "visualization",
    "memoryPanel": "panel",
    "mcpDefaults": "settings",
    "queueComposer": "composer",
    "realtimeToggle": "toggle",
    "schedulesSection": "section",
    "skillsTab": "tab",
    "toolWaterfall": "waterfall",
    "triggerHistory": "history",
    "triggersTab": "tab",
    "triggersUi": "ui",
    "updatesSection": "section",
    "webhooksSection": "section",
    "workersTab": "tab",
    "addAgent": "action",
    "agentCard": "card",
    "agentControl": "control",
    "agentDetail": "detail",
    "agentStrip": "strip",
    "aiEngines": "settings",
    "askMe": "prompt",
    "contextSection": "section",
    "devicePicker": "picker",
    "fullscreenTerminal": "terminal",
    "orgSection": "section",
    "commandCenter": "command",
}


def classify_string(value: str, section: str, key: str) -> str:
    """Classify a UI string by its semantic type."""
    v = value.strip()

    # Empty or whitespace only
    if not v:
        return "empty"

    # Section-based heuristics first
    if section in SECTION_TYPE_MAP:
        base_type = SECTION_TYPE_MAP[section]

        # Refine based on value patterns
        if v.endswith("?"):
            return "dialog"
        if v.endswith("…") or v.endswith("..."):
            return "status"
        if v.startswith("{{") and v.endswith("}}"):
            return "variable"
        if PLACEHOLDER_RE.search(v):
            return "template"

        return base_type

    # Fallback heuristics
    if v.endswith("?"):
        return "dialog"
    if v.endswith("…") or v.endswith("..."):
        return "status"
    if PLACEHOLDER_RE.search(v):
        return "template"
    if len(v) <= 3 and v.isupper():
        return "abbreviation"

    return "unknown"


def extract_placeholders(value: str) -> list[str]:
    """Extract all placeholder tokens from a string."""
    return PLACEHOLDER_RE.findall(value)


def extract_accelerators(value: str) -> list[str]:
    """Extract keyboard accelerator tokens."""
    return ACCELERATOR_RE.findall(value)


def is_technical(value: str, section: str, key: str) -> bool:
    """Check if a string is a technical token that should not be translated.

    Conservative: only skip if the VALUE itself is technical, not just the key name.
    A key named 'tokenLimit' can have a translatable value like 'limit {{value}}'.
    """
    v = value.strip()

    # Exact match in known technical tokens
    if v in TECHNICAL_TOKENS:
        return True

    # Path-like tokens (start with / or contain path separators) — but not slash commands
    if v.startswith("/") and len(v) <= 30 and not re.match(r"^/[a-z]", v):
        return True

    # URLs and endpoints
    if v.startswith("http://") or v.startswith("https://"):
        return True

    # Command syntax: /word (slash commands) — only if the whole value is just the command
    if re.match(r"^/[a-zA-Z]+$", v):
        return True

    # Single-word tokens that are only letters and known technical
    if v in TECHNICAL_TOKENS:
        return True

    # Abbreviations (all caps, <=5 chars)
    if v.isupper() and len(v) <= 5 and v.replace(" ", "").isalpha():
        return True

    # Greek letters / symbols used in UI (Σ, ·, etc.) — these are decorative
    if len(v) <= 2 and not v.isascii():
        return True

    return False


def is_brand(value: str) -> bool:
    """Check if a string is a brand name."""
    v = value.strip()
    return bool(BRAND_PATTERNS.match(v))


def infer_type_from_key(key: str) -> str:
    """Infer type from the key name itself."""
    k = key.lower()
    if k.endswith("title") or k.endswith("label"):
        return "label"
    if k.endswith("placeholder"):
        return "placeholder"
    if k.endswith("tooltip") or k.endswith("hint"):
        return "tooltip"
    if k.endswith("error") or k.endswith("warning"):
        return "error"
    if k.endswith("button") or k.endswith("action"):
        return "button"
    if k.endswith("heading") or k.endswith("header"):
        return "heading"
    return "unknown"


def flatten_locale(data: dict, parent_key: str = "") -> list[dict]:
    """Flatten nested locale dict into list of {key, value, section}."""
    items = []
    for k, v in data.items():
        full_key = f"{parent_key}.{k}" if parent_key else k
        section = parent_key.split(".")[0] if parent_key else ""

        if isinstance(v, dict):
            items.extend(flatten_locale(v, full_key))
        else:
            items.append({
                "key": full_key,
                "value": str(v),
                "section": section,
            })
    return items


def build_inventory(source_path: str) -> dict:
    """Build complete inventory from a locale JSON file."""
    with open(source_path, encoding="utf-8") as f:
        data = json.load(f)

    items = flatten_locale(data)
    inventory = {}

    for item in items:
        key = item["key"]
        value = item["value"]
        section = item["section"]

        # Classify
        str_type = classify_string(value, section, key)
        if str_type == "unknown":
            inferred = infer_type_from_key(key.split(".")[-1])
            if inferred != "unknown":
                str_type = inferred

        # Extract metadata
        placeholders = extract_placeholders(value)
        accelerators = extract_accelerators(value)
        technical = is_technical(value, section, key)
        brand = is_brand(value)

        # Determine if translatable
        translatable = True
        skip_reason = None
        if technical:
            translatable = False
            skip_reason = "technical_token"
        elif brand:
            translatable = False
            skip_reason = "brand_name"
        elif not value.strip():
            translatable = False
            skip_reason = "empty_string"
        elif value.strip() in ("/", ".", "..", "~"):
            translatable = False
            skip_reason = "path_separator"

        inventory[key] = {
            "value": value,
            "section": section,
            "type": str_type,
            "placeholders": placeholders,
            "accelerators": accelerators,
            "length": len(value),
            "translatable": translatable,
            "skip_reason": skip_reason,
        }

    return inventory


def generate_hash(inventory: dict) -> str:
    """Generate deterministic hash of inventory for reproducibility."""
    canonical = json.dumps(inventory, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def main():
    parser = argparse.ArgumentParser(description="M0 — i18n Inventory Extractor")
    parser.add_argument("--source", required=True, help="Path to canonical locale JSON (e.g., en.json)")
    parser.add_argument("--output", required=True, help="Output path for inventory JSON")
    args = parser.parse_args()

    source = Path(args.source)
    if not source.exists():
        print(f"ERROR: Source file not found: {source}")
        raise SystemExit(1)

    inventory = build_inventory(str(source))
    inv_hash = generate_hash(inventory)

    # Stats
    total = len(inventory)
    translatable = sum(1 for v in inventory.values() if v["translatable"])
    skipped = total - translatable
    sections = set(v["section"] for v in inventory.values())
    types = {}
    for v in inventory.values():
        t = v["type"]
        types[t] = types.get(t, 0) + 1

    output = {
        "meta": {
            "source_file": str(source),
            "source_hash": inv_hash,
            "total_keys": total,
            "translatable": translatable,
            "skipped": skipped,
            "sections": sorted(sections),
            "type_distribution": dict(sorted(types.items())),
        },
        "inventory": inventory,
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Keys: {total}")
    print(f"Sections: {len(sections)}")
    print(f"Translatable: {translatable}")
    print(f"Skipped (technical/brand/empty): {skipped}")
    print(f"Hash: {inv_hash}")
    print(f"Output: {out_path}")


if __name__ == "__main__":
    main()
