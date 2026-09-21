"""M2: parse simple multilingual sentences into Meaning IR."""
from __future__ import annotations

import pytest

from intentlang.meaning_parser import parse_meaning


@pytest.mark.parametrize(
    ("lang", "text"),
    [
        ("en", "Alice was beginning to get very tired"),
        ("es", "Alicia empezaba a estar muy cansada"),
        ("ja", "アリスはとても疲れ始めていた"),
        ("zh", "爱丽丝开始感到非常疲倦"),
    ],
)
def test_fatigue_variants_converge(lang, text):
    meaning = parse_meaning(text, lang)

    assert meaning.status == "RESOLVED"
    assert meaning.predicate == "fatigue"
    assert meaning.aspect == "inchoative"
    assert meaning.key()[0] == "fatigue"


@pytest.mark.parametrize(
    ("lang", "text"),
    [
        ("en", "The rabbit took a watch out of its waistcoat pocket"),
        ("es", "El conejo sacó un reloj del bolsillo de su chaleco"),
        ("ja", "ウサギはチョッキのポケットから時計を取り出した"),
        ("zh", "兔子从马甲口袋里拿出一块表"),
    ],
)
def test_take_out_variants_preserve_agent_object_and_source(lang, text):
    meaning = parse_meaning(text, lang)

    assert meaning.status == "RESOLVED"
    assert meaning.predicate == "take_out"
    assert {role.name for role in meaning.roles} == {"agent", "object", "source"}


def test_prose_watch_is_not_an_executable_query():
    meaning = parse_meaning("The rabbit took a watch out of its waistcoat pocket", "en")

    assert meaning.predicate != "query"
    assert meaning.provenance.mode == "strict"


def test_unknown_sentence_fails_closed():
    meaning = parse_meaning("Alice blorps the rabbit", "en")

    assert meaning.status == "UNKNOWN"
    assert meaning.predicate is None
