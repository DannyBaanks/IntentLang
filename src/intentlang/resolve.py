"""Texto -> IR. Ensambla conceptos en intencion y decide el estado.

No adivina en ningun punto: si algo no resuelve, el estado lo dice y la IR no
puede actuar.

Modo assisted: cuando la resolucion estricta da UNKNOWN, un proponente puede
sugerir lemas -- pero el lexico sigue siendo la unica autoridad. Ver
`_resolve_assisted` para las tres bifurcaciones de esa validacion.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from . import propose as _propose
from .ir import Concept, Intent, Provenance, Status
from .lexicon import senses, source_id
from .normalize import tokens, verb_candidates
from .primitives import primitive_for


def _first_verb(lemas: list[str], lang: str) -> tuple[Concept, str, int] | tuple[None, None, None]:
    """Primer lema que resuelve a una primitiva.

    Devuelve `(concepto, primitiva, token_fuente)`. El token fuente importa:
    cuando el verbo se resolvio por reconstruccion (`copia` -> `copiar`), el
    operando tiene que descartar el token ORIGINAL, no el reconstruido. Sin
    eso, "copia el archivo" resuelve el verbo como `copiar` y despues elige
    `copia` -- el sustantivo -- como operando, en vez de `archivo`.
    """
    verbos = _all_verbs(lemas, lang)
    return verbos[0] if verbos else (None, None, None)


def _all_verbs(lemas: list[str], lang: str) -> list[tuple[Concept, str, int]]:
    """TODOS los pares (lema, primitiva) que resuelven, en orden de aparicion.

    Devuelve `(concepto, primitiva, indice)` por cada lema cuyo sentido
    mapee a una primitiva. Un MISMO lema puede alcanzar varias primitivas
    (ja '動かす' tiene 14 sentidos: CHANGE y MOVE entre ellos): quedarse
    con el primer sentido por frecuencia seria adivinar -- eso es
    competencia de intencion y la resuelve el estado AMBIGUOUS.
    """
    out: list[tuple[Concept, str, int]] = []
    vistos: set[tuple[int, str]] = set()
    for idx, lema in enumerate(lemas):
        for candidato in verb_candidates(lema, lang):
            for ili in senses(candidato, lang, pos="v"):
                prim = primitive_for(ili)
                if prim and (idx, prim) not in vistos:
                    vistos.add((idx, prim))
                    out.append((Concept(ili=ili, lemma=candidato), prim, idx))
    return out


def _first_operand(lemas: list[str], lang: str, usado: int | None) -> Concept | None:
    """Primer sustantivo que no ocupe la POSICION de la que salio el verbo.

    `usado` es un indice, no un lema. Antes se descartaba por igualdad de
    string, y eso borraba todas las repeticiones de la palabra: "copia copia"
    resolvia el verbo con la primera y despues descartaba tambien la segunda,
    devolviendo INCOMPLETE cuando habia un operando disponible. Descartar una
    posicion descarta exactamente un token.
    """
    for idx, lema in enumerate(lemas):
        if idx == usado:
            continue
        ilis = senses(lema, lang, pos="n")
        if ilis:
            return Concept(ili=ilis[0], lemma=lema)
    return None


def _has_non_executable_context(text: str, lang: str) -> bool:
    markers = {
        "en": (
            " not ", " never ", " if ", " when ", " the manual says",
            " the document says", " says: ", " said: ", " according to ",
        ),
        "es": (
            " no ", " nunca ", " si ", " cuando ", " el manual dice",
            " el documento dice", " la guía dice", " la guia dice",
            " dice: ", " dijo: ", " según ", " segun ",
        ),
        "ja": ("ない", "ません", "もし", "場合", "マニュアルには", "と言った"),
        "zh": ("不", "没", "如果", "当", "手册说", "说明书说", "据说"),
    }.get(lang, ())
    padded = f" {text.casefold()} "
    return any(marker in padded for marker in markers)


# Preposiciones que indican scope/destination (para COPY/MOVE)
_SCOPE_PREPOSITIONS = {
    "es": {"a", "al", "en", "hacia", "para"},
    "en": {"to", "into", "toward", "at", "in", "on"},
    "zh": {"到", "在", "至"},
    "ja": {"に", "へ", "で"},
    "ar": {"إلى", "في", "من"},
    "fi": {"-", "ihin", "ille", "asta", "sta"},
}


def _first_scope(lemas: list[str], lang: str, verb_idx: int | None, 
                 operand_idx: int | None) -> Concept | None:
    """Segundo sustantivo despues del verbo y operando, indicado por preposicion.
    
    Para COPY/MOVE: busca patron "copia X a Y" / "copy X to Y".
    El scope es el destino/objeto indirecto.
    """
    preps = _SCOPE_PREPOSITIONS.get(lang, set())
    if not preps:
        return None
    
    # Buscar patron: verbo ... operando ... preposicion ... sustantivo
    skip = {verb_idx, operand_idx} if verb_idx is not None and operand_idx is not None else set()
    
    for idx, lema in enumerate(lemas):
        if idx in skip:
            continue
        # Si el lema es una preposicion de scope, el siguiente sustantivo es scope
        if lema.lower() in preps:
            # Buscar el siguiente sustantivo despues de esta preposicion
            for next_idx in range(idx + 1, len(lemas)):
                if next_idx in skip:
                    continue
                ilis = senses(lemas[next_idx], lang, pos="n")
                if ilis:
                    return Concept(ili=ilis[0], lemma=lemas[next_idx])
    return None


def resolve(text: str, lang: str, mode: str = "strict",
            propose_fn: Callable[[str, str], list[str]] | None = None) -> Intent:
    """Resuelve texto humano a IR canonica.

    `mode` se escribe en la provenance sin importar la rama que se tome; no
    se infiere nunca (§ restriccion global). El modo `strict` es 100%
    determinista y jamas invoca `propose_fn`, exista o no: eso solo puede
    pasar cuando `mode == "assisted"` Y `propose_fn` no es None Y la
    resolucion estricta dio UNKNOWN.
    """
    lemas = tokens(text, lang)
    prov = Provenance(
        surface=text, language=lang, lexical_source=source_id(lang),
        resolution="lexicon", confidence="exact", mode=mode,
    )

    if _has_non_executable_context(text, lang):
        return Intent(None, None, None, Status.UNKNOWN, prov)

    verbos = _all_verbs(lemas, lang)
    if not verbos:
        if mode == "assisted" and propose_fn is not None:
            return _resolve_assisted(text, lang, lemas, prov, propose_fn)
        return Intent(None, None, None, Status.UNKNOWN, prov)

    # Intenciones en competencia: "copia y borra el archivo" resuelve dos
    # verbos a primitivas DISTINTAS. Quedarse con el primero seria adivinar
    # cual queria el usuario, y el sistema no adivina.
    #
    # La ambiguedad es de la PRIMITIVA, no de la superficie: "cambia y
    # modifica" son dos verbos distintos que resuelven ambos a CHANGE, asi
    # que no compiten y la intencion esta determinada. Lo que se pregunta no
    # es "que palabra usaste" sino "que querias hacer".
    primitivas = {p for _, p, _ in verbos}
    if len(primitivas) > 1:
        return Intent(None, None, None, Status.AMBIGUOUS, prov,
                      candidates=tuple(c.lemma for c, _, _ in verbos))

    verb, primitive, token_fuente = verbos[0]

    operand = _first_operand(lemas, lang, usado=token_fuente)
    if operand is None:
        return Intent(verb, None, None, Status.INCOMPLETE, prov, primitive=primitive)

    # Para COPY/MOVE: intentar detectar scope (destination)
    scope = None
    if primitive in ("COPY", "MOVE") and operand is not None:
        # Encontrar el indice del operando en la lista de lemas
        operand_idx = None
        for idx, lema in enumerate(lemas):
            if idx == token_fuente:
                continue
            ilis = senses(lema, lang, pos="n")
            if ilis and lema == operand.lemma:
                operand_idx = idx
                break
        scope = _first_scope(lemas, lang, verb_idx=token_fuente, operand_idx=operand_idx)

    return Intent(verb, operand, scope, Status.RESOLVED, prov, primitive=primitive)


def _resolve_assisted(text: str, lang: str, lemas: list[str], prov: Provenance,
                       propose_fn: Callable[[str, str], list[str]]) -> Intent:
    """El proponente sugiere, el lexico valida, `resolve` decide el estado.

    El modelo nunca emite IR: `propose.propose()` ya redujo las sugerencias a
    lemas que el lexico confirmo. Aca solo se decide, segun CUANTOS
    sobrevivieron, entre reintentar (1), pedir aclaracion (>1) o quedarse en
    UNKNOWN (0) -- y en ese ultimo caso, propagar la degradacion si la hubo,
    nunca en silencio.
    """
    record = _propose.propose(text, lang, propose_fn)

    if len(record.validated) == 1:
        lema = record.validated[0]
        verb, primitive, token_fuente = _first_verb([lema], lang)
        operand = _first_operand(lemas, lang, usado=token_fuente)
        nueva_prov = replace(prov, resolution="llm_proposed+lexicon_validated",
                             confidence="proposed", cache_key=record.key)
        if operand is None:
            return Intent(verb, None, None, Status.INCOMPLETE, nueva_prov,
                          primitive=primitive)
        return Intent(verb, operand, None, Status.RESOLVED, nueva_prov,
                      primitive=primitive)

    if len(record.validated) > 1:
        nueva_prov = replace(prov, resolution="llm_proposed+lexicon_validated",
                             confidence="proposed", cache_key=record.key)
        return Intent(None, None, None, Status.AMBIGUOUS, nueva_prov,
                      candidates=tuple(record.validated))

    # 0 validados: sigue UNKNOWN. Si el proponente se cayo, la degradacion
    # queda escrita en provenance -- nunca en silencio.
    nueva_prov = prov if record.degraded is None else replace(prov, degraded=record.degraded)
    return Intent(None, None, None, Status.UNKNOWN, nueva_prov)
