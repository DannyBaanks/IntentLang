"""M1 gate: corpus identity and separation invariants."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))

from ci.run_semantic_benchmark import run_m1_gate
from intentlang.meaning_ir import Meaning, MeaningEntity, MeaningProvenance, MeaningRole


def meaning_fixture(*, agent: str = "alice", object: str | None = None) -> Meaning:
    entities = [MeaningEntity(agent, f"person.{agent}")]
    roles = [MeaningRole("agent", entity=agent)]
    if object:
        entities.append(MeaningEntity(object, f"object.{object}"))
        roles.append(MeaningRole("object", entity=object))
    return Meaning(
        predicate="observe",
        roles=tuple(roles),
        polarity="positive",
        tense="past",
        aspect="simple",
        modality="asserted",
        entities=tuple(entities),
        provenance=MeaningProvenance("fixture", "en", "fixture", "gold", "strict", "fixture"),
    )


def test_m1_gate_accepts_same_event_in_four_languages():
    report = run_m1_gate("corpus/semantic/meaning_m1.jsonl")

    assert report["schema_failures"] == 0
    assert report["identity_failures"] == 0


def test_m1_gate_rejects_agent_object_swap():
    assert meaning_fixture(agent="alice", object="watch").key() != meaning_fixture(
        agent="watch", object="alice"
    ).key()


def test_m1_gate_reports_missing_corpus_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        run_m1_gate(str(tmp_path / "missing.jsonl"))
