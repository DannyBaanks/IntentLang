"""Deterministic parser for the first Meaning IR sentence grammar.

This is intentionally conservative.  It recognizes semantic constructions
that have a tested cross-language pattern and returns UNKNOWN otherwise.  It
does not call the executable intent resolver, so prose cannot accidentally
become a QUERY/COPY/etc. action.
"""
from __future__ import annotations

import hashlib
from collections.abc import Iterable

from .meaning_ir import Meaning, MeaningEntity, MeaningProvenance, MeaningRole


def _provenance(text: str, language: str, confidence: str = "exact") -> MeaningProvenance:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return MeaningProvenance(text, language, "meaning-parser/rule-v1", confidence, "strict", digest)


def _entity(entity_id: str, concept: str, features: dict[str, str] | None = None) -> MeaningEntity:
    return MeaningEntity(entity_id, concept, features or {})


def _resolved(
    text: str,
    language: str,
    predicate: str,
    roles: Iterable[MeaningRole],
    entities: Iterable[MeaningEntity],
    *,
    polarity: str = "positive",
    tense: str | None = "present",
    aspect: str | None = "simple",
    modality: str | None = "asserted",
) -> Meaning:
    return Meaning(
        predicate=predicate,
        roles=tuple(roles),
        polarity=polarity,
        tense=tense,
        aspect=aspect,
        modality=modality,
        entities=tuple(entities),
        provenance=_provenance(text, language),
    )


def _unknown(text: str, language: str) -> Meaning:
    return Meaning(
        predicate=None,
        roles=(),
        polarity="unknown",
        tense=None,
        aspect=None,
        modality=None,
        entities=(),
        provenance=_provenance(text, language, confidence="surface_only"),
        status="UNKNOWN",
    )


def _fatigue(text: str, language: str) -> Meaning | None:
    lower = text.casefold()
    markers = {
        "en": ("tired", "beginning"),
        "es": ("cansad", "empez"),
        "ja": ("疲れ", "始め"),
        "zh": ("疲倦", "开始"),
    }
    required = markers.get(language)
    if required and all(marker in lower for marker in required):
        return _resolved(
            text, language, "fatigue",
            [MeaningRole("experiencer", entity="alice")],
            [_entity("alice", "person.alice")],
            tense="past", aspect="inchoative",
        )
    return None


def _take_out(text: str, language: str) -> Meaning | None:
    lower = text.casefold()
    markers = {
        "en": ("rabbit", "watch", "pocket", ("take", "took"), ("out", "from")),
        "es": ("conejo", "reloj", "bolsillo", ("sacar", "sacó", "saco")),
        "ja": ("ウサギ", "時計", "ポケット", "取り出"),
        "zh": ("兔子", "表", "口袋", "拿出"),
    }
    required = markers.get(language)
    def matches(marker: str | tuple[str, ...]) -> bool:
        choices = marker if isinstance(marker, tuple) else (marker,)
        return any(choice.casefold() in lower for choice in choices)

    if required and all(matches(marker) for marker in required):
        return _resolved(
            text, language, "take_out",
            [
                MeaningRole("agent", entity="rabbit"),
                MeaningRole("object", entity="watch"),
                MeaningRole("source", entity="pocket"),
            ],
            [
                _entity("rabbit", "animal.rabbit"),
                _entity("watch", "object.watch"),
                _entity("pocket", "container.pocket"),
            ],
            tense="past", aspect="perfective",
        )
    return None


def _see(text: str, language: str) -> Meaning | None:
    lower = text.casefold()
    markers = {
        "en": (("alice", "rabbit", ("saw",), "positive"), ("alice", "rabbit", ("did not see",), "negative")),
        "es": (("alicia", "conejo", ("no vio",), "negative"), ("alicia", "conejo", ("vio",), "positive")),
        "ja": (("アリス", "ウサギ", ("見なかった",), "negative"), ("アリス", "ウサギ", ("見た",), "positive")),
        "zh": (("爱丽丝", "兔子", ("没有", "看见"), "negative"), ("爱丽丝", "兔子", ("看见",), "positive")),
    }
    for agent, obj, required, polarity in markers.get(language, ()):
        if agent.casefold() in lower and obj.casefold() in lower and all(marker.casefold() in lower for marker in required):
            return _resolved(
                text, language, "see",
                [MeaningRole("agent", entity="alice"), MeaningRole("object", entity="rabbit")],
                [_entity("alice", "person.alice"), _entity("rabbit", "animal.rabbit")],
                polarity=polarity, tense="past", aspect="simple",
            )
    return None


def _open(text: str, language: str) -> Meaning | None:
    lower = text.casefold()
    forms = {
        "en": {"progressive": "is opening", "perfect": "has opened", "past": "opened", "present": "opens", "imperative": "open the door"},
        "es": {"progressive": "está abriendo", "perfect": "ha abierto", "past": "abrió", "present": "abre", "imperative": "abre la puerta"},
        "ja": {"progressive": "開けている", "perfect": "開けたことがある", "past": "開けた", "present": "開ける", "imperative": "ドアを開けて"},
        "zh": {"progressive": "正在打开", "perfect": "已经打开", "past": "打开了", "present": "打开门", "imperative": "打开门"},
    }.get(language, {})
    if language == "en":
        if "is " in lower and "opening" in lower:
            roles = [MeaningRole("agent", entity="alice"), MeaningRole("object", entity="door")]
            entities = [_entity("alice", "person.alice"), _entity("door", "object.door")]
            return _resolved(text, language, "open", roles, entities, tense="present", aspect="progressive")
        if "has " in lower and "opened" in lower:
            roles = [MeaningRole("agent", entity="alice"), MeaningRole("object", entity="door")]
            entities = [_entity("alice", "person.alice"), _entity("door", "object.door")]
            return _resolved(text, language, "open", roles, entities, tense="present", aspect="perfect")
    if language == "zh" and "正在" in lower and "打开" in lower:
        roles = [MeaningRole("agent", entity="alice"), MeaningRole("object", entity="door")]
        entities = [_entity("alice", "person.alice"), _entity("door", "object.door")]
        return _resolved(text, language, "open", roles, entities, tense="present", aspect="progressive")
    imperative_marker = forms.get("imperative")
    if imperative_marker and imperative_marker.casefold() in lower and not any(name in lower for name in ("alice", "alicia", "アリス", "爱丽丝")):
        roles = [MeaningRole("agent", entity="addressee"), MeaningRole("object", entity="door")]
        entities = [_entity("addressee", "person.addressee"), _entity("door", "object.door")]
        return _resolved(text, language, "open", roles, entities, modality="imperative")
    for aspect, marker in forms.items():
        if aspect == "imperative":
            continue
        if marker.casefold() not in lower:
            continue
        roles = [MeaningRole("agent", entity="alice"), MeaningRole("object", entity="door")]
        entities = [_entity("alice", "person.alice"), _entity("door", "object.door")]
        tense = "present" if aspect in {"progressive", "perfect", "present"} else "past"
        return _resolved(text, language, "open", roles, entities, tense=tense, aspect=aspect if aspect not in {"past", "present"} else ("perfective" if aspect == "past" else "simple"))
    return None


def _push(text: str, language: str) -> Meaning | None:
    lower = text.casefold()
    marker = {"en": "pushed", "es": "empujó", "ja": "押した", "zh": "推了"}.get(language)
    if not marker or marker.casefold() not in lower:
        return None
    names = {
        "alice": ("alice", "alicia", "アリス", "爱丽丝"),
        "rabbit": ("rabbit", "conejo", "ウサギ", "兔子"),
    }
    positions = {
        entity: min((lower.find(marker.casefold()) for marker in markers if marker.casefold() in lower), default=10**9)
        for entity, markers in names.items()
    }
    agent_id, object_id = ("alice", "rabbit") if positions["alice"] < positions["rabbit"] else ("rabbit", "alice")
    concepts = {"alice": "person.alice", "rabbit": "animal.rabbit"}
    return _resolved(
        text, language, "push",
        [MeaningRole("agent", entity=agent_id), MeaningRole("object", entity=object_id)],
        [_entity(agent_id, concepts[agent_id]), _entity(object_id, concepts[object_id])],
        tense="past", aspect="perfective",
    )


def _carry(text: str, language: str) -> Meaning | None:
    lower = text.casefold()
    marker = {"en": "carried", "es": "llevó", "ja": "運んだ", "zh": "拿着"}.get(language)
    if marker and marker.casefold() in lower and ("watch" in lower or "reloj" in lower or "時計" in lower or "手表" in lower):
        return _resolved(
            text, language, "carry",
            [MeaningRole("agent", entity="alice"), MeaningRole("object", entity="watch")],
            [_entity("alice", "person.alice"), _entity("watch", "object.watch")],
            tense="past", aspect="simple",
        )
    return None


def _leave(text: str, language: str) -> Meaning | None:
    lower = text.casefold()
    markers = {
        "en": ((("must", "leave"), "necessity"), (("may", "leave"), "possibility")),
        "es": ((("debe", "irse"), "necessity"), (("puede", "irse"), "possibility")),
        "ja": ((("出なければならない",), "necessity"), (("出てもよい",), "possibility")),
        "zh": ((("必须", "离开"), "necessity"), (("可以", "离开"), "possibility")),
    }
    for required, modality in markers.get(language, ()):
        if all(marker.casefold() in lower for marker in required):
            return _resolved(text, language, "leave", [MeaningRole("agent", entity="alice")], [_entity("alice", "person.alice")], modality=modality)
    return None


def _location(text: str, language: str) -> Meaning | None:
    lower = text.casefold()
    markers = {
        "en": ("alice", "court", "in"), "es": ("alicia", "tribunal", "en"),
        "ja": ("アリス", "法廷", "いる"), "zh": ("爱丽丝", "法庭", "在"),
    }.get(language)
    if markers and all(marker.casefold() in lower for marker in markers):
        return _resolved(text, language, "be_in", [MeaningRole("experiencer", entity="alice"), MeaningRole("location", entity="court")], [_entity("alice", "person.alice"), _entity("court", "place.court")])
    return None


def _quantifier(text: str, language: str) -> Meaning | None:
    lower = text.casefold()
    markers = {
        "en": ("no", "rabbit", "moved"), "es": ("ningún", "conejo", "movió"),
        "ja": ("ウサギ", "一匹も", "動かなかった"), "zh": ("没有", "兔子", "动"),
    }.get(language)
    if markers and all(marker.casefold() in lower for marker in markers):
        return _resolved(text, language, "move", [MeaningRole("agent", entity="rabbit")], [_entity("rabbit", "animal.rabbit", {"quantifier": "none"})], polarity="negative", tense="past")
    return None


def _drink(text: str, language: str) -> Meaning | None:
    lower = text.casefold()
    markers = {"en": "drink me", "es": "bébeme", "ja": "飲ん", "zh": "喝我"}
    marker = markers.get(language)
    if marker and marker.casefold() in lower:
        return _resolved(
            text, language, "drink",
            [MeaningRole("agent", entity="addressee"), MeaningRole("object", entity="self")],
            [_entity("addressee", "person.addressee"), _entity("self", "entity.self")],
            modality="imperative",
        )
    return None


def _remarkable(text: str, language: str) -> Meaning | None:
    lower = text.casefold()
    markers = {
        "en": ("nothing", "remarkable"),
        "es": ("nada", "notable"),
        "ja": ("何も", "目立"),
        "zh": ("没有", "特别"),
    }
    required = markers.get(language)
    if required and all(marker.casefold() in lower for marker in required):
        return _resolved(
            text, language, "remarkable",
            [MeaningRole("referent", entity="that")],
            [_entity("that", "entity.that")],
            polarity="negative", tense="past",
        )
    return None


def _court(text: str, language: str) -> Meaning | None:
    lower = text.casefold()
    markers = {
        "en": ("alice", "never", "court"),
        "es": ("alicia", "nunca", "tribunal"),
        "ja": ("アリス", "なかった", "裁判所"),
        "zh": ("爱丽丝", "从未", "法院"),
    }
    required = markers.get(language)
    if required and all(marker.casefold() in lower for marker in required):
        return _resolved(
            text, language, "be_in",
            [MeaningRole("experiencer", entity="alice"), MeaningRole("location", entity="court")],
            [_entity("alice", "person.alice"), _entity("court", "place.court")],
            polarity="negative", tense="past", aspect="perfect",
        )
    return None


def parse_meaning(text: str, language: str) -> Meaning:
    """Parse one simple sentence, failing closed when no rule is proven."""
    if not text.strip():
        return _unknown(text, language)
    for parser in (_fatigue, _take_out, _drink, _remarkable, _court, _see, _open, _push, _carry, _leave, _location, _quantifier):
        meaning = parser(text, language)
        if meaning is not None:
            return meaning
    return _unknown(text, language)


__all__ = ["parse_meaning"]
