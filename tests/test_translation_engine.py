"""Regression tests for the UI locale translation pipeline."""
from __future__ import annotations

import json
from pathlib import Path

from intentlang.translation_engine.extractor import (
    build_inventory,
    extract_accelerators,
    is_technical,
)
from intentlang.translation_engine.harness import run_harness
from intentlang.translation_engine.materializer import _materialize_text, materialize_locale


def _write_locale(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "common": {"save": "save", "template": "{{name}}"},
                "office": {"cheer": ["done!", "ship it 🚀"]},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_inventory_keeps_array_values_and_placeholders(tmp_path: Path):
    source = tmp_path / "en.json"
    _write_locale(source)

    inventory = build_inventory(str(source))

    assert inventory["office.cheer"]["value"] == ["done!", "ship it 🚀"]
    assert inventory["common.template"]["placeholders"] == ["{{name}}"]


def test_materializer_keeps_array_shape(tmp_path: Path):
    source = tmp_path / "en.json"
    inventory_path = tmp_path / "inventory.json"
    target = tmp_path / "es.json"
    _write_locale(source)
    inventory = build_inventory(str(source))
    inventory_path.write_text(
        json.dumps({"inventory": inventory}, ensure_ascii=False),
        encoding="utf-8",
    )

    materialize_locale(str(inventory_path), "es", str(target))
    result = json.loads(target.read_text(encoding="utf-8"))

    assert isinstance(result["office"]["cheer"], list)
    assert len(result["office"]["cheer"]) == 2


def test_unknown_single_word_keeps_original_case():
    assert _materialize_text("Slack", "es", "settings") == "Slack"


def test_ui_caps_are_translatable_but_known_abbreviations_are_not():
    assert not is_technical("DONE", "kanban", "colDone")
    assert is_technical("API", "settings", "api")


def test_ampersand_in_prose_is_not_an_accelerator():
    assert extract_accelerators("Q&A history") == []
    assert extract_accelerators("&S Save") == ["&S"]


def test_harness_persists_overall_status(tmp_path: Path):
    source = tmp_path / "en.json"
    output = tmp_path / "output"
    _write_locale(source)

    result = run_harness(str(source), "es", str(output))
    report = json.loads((output / "harness_report.json").read_text(encoding="utf-8"))

    assert result["overall_status"] == "PASS"
    assert report["overall_status"] == "PASS"
    assert report["report"] == str(output / "harness_report.json")
