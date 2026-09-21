"""Deterministic realization from Meaning IR.

The realizer deliberately has no access to source text or source language.  It
is a small, conservative proof-of-concept: unsupported meanings fail closed
instead of guessing a sentence whose semantics might drift.
"""
from __future__ import annotations

from .meaning_ir import Meaning

SUPPORTED_LANGUAGES = frozenset({"en", "es", "ja", "zh"})


def _role(meaning: Meaning, name: str) -> str | None:
    for role in meaning.roles:
        if role.name == name:
            return role.entity
    return None


def _ok(meaning: Meaning, predicate: str, *roles: tuple[str, str]) -> bool:
    return (
        meaning.status == "RESOLVED"
        and meaning.predicate == predicate
        and all(_role(meaning, name) == entity for name, entity in roles)
    )


def _transitive(meaning: Meaning, predicate: str, language: str) -> str | None:
    agent = _role(meaning, "agent")
    obj = _role(meaning, "object")
    if agent not in {"alice", "rabbit"} or obj not in {"alice", "rabbit", "watch"}:
        return None
    names = {
        "en": {"alice": "Alice", "rabbit": "the rabbit", "watch": "the watch"},
        "es": {"alice": "Alicia", "rabbit": "al conejo", "watch": "el reloj"},
        "ja": {"alice": "アリス", "rabbit": "ウサギ", "watch": "時計"},
        "zh": {"alice": "爱丽丝", "rabbit": "兔子", "watch": "手表"},
    }[language]
    subject = names[agent]
    target = names[obj]
    if predicate == "push":
        verbs = {"en": "pushed", "es": "empujó", "ja": "押した", "zh": "推了"}
    else:
        verbs = {"en": "carried", "es": "llevó", "ja": "運んだ", "zh": "拿着"}
    if language == "en":
        return f"{subject} {verbs[language]} {target}"
    if language == "es":
        return f"{subject} {verbs[language]} {target}"
    return f"{subject}は{target}{verbs[language]}"


def realize_meaning(meaning: Meaning, language: str) -> str | None:
    """Realize a resolved Meaning IR value in one supported language."""
    if language not in SUPPORTED_LANGUAGES or meaning.status != "RESOLVED":
        return None

    if _ok(meaning, "fatigue", ("experiencer", "alice")):
        return {"en": "Alice was beginning to get very tired", "es": "Alicia empezaba a estar muy cansada", "ja": "アリスはとても疲れ始めていた", "zh": "爱丽丝开始感到非常疲倦"}[language]

    if _ok(meaning, "take_out", ("agent", "rabbit"), ("object", "watch"), ("source", "pocket")):
        return {"en": "The rabbit took a watch out of its waistcoat pocket", "es": "El conejo sacó un reloj del bolsillo de su chaleco", "ja": "ウサギはチョッキのポケットから時計を取り出した", "zh": "兔子从马甲口袋里拿出一块表"}[language]

    if _ok(meaning, "drink", ("agent", "addressee"), ("object", "self")) and meaning.modality == "imperative":
        return {"en": "Drink me", "es": "Bébeme", "ja": "私を飲んで", "zh": "喝我"}[language]

    if _ok(meaning, "remarkable", ("referent", "that")) and meaning.polarity == "negative":
        return {"en": "There was nothing very remarkable in that", "es": "No había nada muy notable en eso", "ja": "それには特に目立ったことは何もなかった", "zh": "那没有什么特别值得注意的地方"}[language]

    if _ok(meaning, "be_in", ("experiencer", "alice"), ("location", "court")):
        if meaning.polarity == "negative" and meaning.aspect == "perfect":
            return {"en": "Alice had never been in a court of justice before", "es": "Alicia nunca había estado antes en un tribunal", "ja": "アリスは以前に裁判所へ行ったことがなかった", "zh": "爱丽丝以前从未到过法院"}[language]
        if meaning.polarity == "positive":
            return {"en": "Alice is in the court", "es": "Alicia está en el tribunal", "ja": "アリスは法廷にいる", "zh": "爱丽丝在法庭里"}[language]
        return None

    if _ok(meaning, "see", ("agent", "alice"), ("object", "rabbit")):
        if language == "en":
            return "Alice did not see the rabbit" if meaning.polarity == "negative" else "Alice saw the rabbit"
        if language == "es":
            return "Alicia no vio al conejo" if meaning.polarity == "negative" else "Alicia vio al conejo"
        if language == "ja":
            return "アリスはウサギを見なかった" if meaning.polarity == "negative" else "アリスはウサギを見た"
        return "爱丽丝没有看见兔子" if meaning.polarity == "negative" else "爱丽丝看见了兔子"

    if _ok(meaning, "open", ("agent", "addressee"), ("object", "door")) and meaning.modality == "imperative":
        return {"en": "Open the door", "es": "Abre la puerta", "ja": "ドアを開けて", "zh": "打开门"}[language]

    if _ok(meaning, "open", ("agent", "alice"), ("object", "door")):
        forms = {
            "progressive": {"en": "Alice is opening the door", "es": "Alicia está abriendo la puerta", "ja": "アリスはドアを開けている", "zh": "爱丽丝正在打开门"},
            "perfect": {"en": "Alice has opened the door", "es": "Alicia ha abierto la puerta", "ja": "アリスはドアを開けたことがある", "zh": "爱丽丝已经打开了门"},
            "perfective": {"en": "Alice opened the door", "es": "Alicia abrió la puerta", "ja": "アリスはドアを開けた", "zh": "爱丽丝打开了门"},
            "simple": {"en": "Alice opens the door", "es": "Alicia abre la puerta", "ja": "アリスはドアを開ける", "zh": "爱丽丝打开门"},
        }
        return forms.get(meaning.aspect or "", {}).get(language)

    if meaning.predicate in {"push", "carry"} and meaning.polarity == "positive" and meaning.aspect in {"perfective", "simple"}:
        return _transitive(meaning, meaning.predicate, language)

    if _ok(meaning, "leave", ("agent", "alice")) and meaning.modality in {"necessity", "possibility"}:
        forms = {
            "necessity": {"en": "Alice must leave", "es": "Alicia debe irse", "ja": "アリスは出なければならない", "zh": "爱丽丝必须离开"},
            "possibility": {"en": "Alice may leave", "es": "Alicia puede irse", "ja": "アリスは出てもよい", "zh": "爱丽丝可以离开"},
        }
        return forms[meaning.modality][language]

    if _ok(meaning, "move", ("agent", "rabbit")) and meaning.polarity == "negative":
        quantifier = next((dict(entity.features).get("quantifier") for entity in meaning.entities if entity.id == "rabbit"), None)
        if quantifier == "none":
            return {"en": "No rabbit moved", "es": "Ningún conejo se movió", "ja": "ウサギは一匹も動かなかった", "zh": "没有兔子动了"}[language]
    return None


__all__ = ["realize_meaning"]
