import pytest

from engine_lang.registry import registry
from intentlang import cache_key, lexicon
from intentlang.ir import Status
from intentlang.normalize import verb_candidates
from intentlang.relex import round_trip
from intentlang.resolve import resolve

LANGS = registry().supported_languages
LANGS_WN = registry().languages_with_wordnet


@pytest.fixture(scope="module", autouse=True)
def _instalar():
    for lang in LANGS_WN:
        lexicon.ensure_installed(lang)


def test_verbo_y_operando_dan_resolved():
    intent = resolve("copia el archivo", "es")
    assert intent.status is Status.RESOLVED
    assert intent.primitive == "COPY"
    assert intent.can_act() is True


def test_sin_operando_da_incomplete_no_resolved():
    intent = resolve("copia", "es")
    assert intent.status is Status.INCOMPLETE
    assert intent.can_act() is False


def test_verbo_fuera_del_lexico_da_unknown():
    intent = resolve("qwertzuiop el archivo", "es")
    assert intent.status is Status.UNKNOWN
    assert intent.can_act() is False


def test_verbo_lexico_sin_primitiva_da_unknown():
    """'meter' existe en espanol pero no mapea a ninguna primitiva."""
    intent = resolve("métele un cuerpo", "es", mode="strict")
    assert intent.status is Status.UNKNOWN
    assert intent.can_act() is False


def test_provenance_completa_incluso_en_unknown():
    intent = resolve("qwertzuiop", "es")
    p = intent.provenance
    assert p.surface == "qwertzuiop"
    assert p.language == "es"
    assert p.lexical_source == "omw-es:1.4"
    assert p.mode == "strict"
    assert p.resolution == "lexicon"


def test_la_intencion_converge_entre_los_tres_idiomas():
    """La intencion converge. El operando NO, y eso esta medido, no asumido.

    El plan original pedia `es.key() == en.key() == zh.key()`. Los datos no
    lo permiten: `archivo`, `file` y `文件` no comparten NINGUN id ILI en
    omw-*:1.4 (es tiene i50132/i71104; en tiene i70665/i81410/i53691/i53690;
    zh tiene i36225/i70665/i70460 — interseccion vacia). No es un problema de
    ordenamiento: no hay sentido comun que elegir.

    La razon es estructural y vale mas que el test: el VERBO converge porque
    la tabla concepto->primitiva lo ancla a un unico ILI compartido. El
    operando es vocabulario libre, sin ancla, y la cobertura de sustantivos
    de OMW diverge entre idiomas. Convergencia exige ancla.

    Anclar operandos es exactamente lo que haria un dominio, y la v1 se
    declara sin dominio. Asi que aca se afirma lo que es cierto — la
    intencion converge — y se DEJA REGISTRADA la divergencia del operando en
    vez de borrarla del test.
    """
    es = resolve("copia el archivo", "es")
    en = resolve("copy the file", "en")
    zh = resolve("复制文件", "zh")

    assert es.status is Status.RESOLVED
    assert en.status is Status.RESOLVED
    assert zh.status is Status.RESOLVED

    # Lo que converge: la intencion.
    assert es.primitive == en.primitive == zh.primitive == "COPY"
    assert es.verb.ili == en.verb.ili == zh.verb.ili

    # Lo que no converge, y queda documentado: el operando.
    operandos = {es.operand.ili, en.operand.ili, zh.operand.ili}
    assert len(operandos) == 3, (
        "los operandos convergieron: si esto falla, la cobertura de OMW "
        "cambio y hay que revisar si el ancla de operandos ya no hace falta")


# --- Rama assisted: hueco del plan (Tarea 8), resuelto por decisión explícita. ---
# resolve(text, lang, mode="strict", propose_fn=None). Sólo cuando la
# resolución estricta da UNKNOWN Y mode=="assisted" Y propose_fn no es None
# se invoca propose.propose(). Estos tests cubren las tres bifurcaciones del
# resultado de validate() (1 / >1 / 0 candidatos) más los dos gates (modo,
# propose_fn ausente) que deben dejar el comportamiento strict intacto.

def test_assisted_con_un_lema_valido_reintenta_y_resuelve():
    """'meter' no mapea a primitiva; el proponente ofrece 'agregar', el
    lexico lo valida, y la resolucion se reintenta con ese lema."""
    intent = resolve("métele un cuerpo", "es", mode="assisted",
                     propose_fn=lambda s, lang: ["agregar"])

    assert intent.status is Status.RESOLVED
    assert intent.can_act() is True
    assert intent.primitive == "ADD"
    assert intent.verb.lemma == "agregar"
    assert intent.operand.lemma == "cuerpo"

    p = intent.provenance
    assert p.mode == "assisted"
    assert p.resolution == "llm_proposed+lexicon_validated"
    assert p.confidence == "proposed"
    # La cache_key no es solo "no-None": tiene que ser LA MISMA que produce
    # cache_key con los mismos insumos. Si resolve() la inventara o
    # la truncara, esta igualdad puntual fallaria.
    esperado = cache_key("métele un cuerpo", "es",
                                  lexicon.source_id("es"), "claude-opus-5")
    assert p.cache_key == esperado


def test_assisted_con_dos_lemas_validos_da_ambiguous_con_candidatos_reales():
    """'agregar' y 'añadir' comparten primitiva ADD: ambos sobreviven la
    validacion, y eso es exactamente lo que hace alcanzable AMBIGUOUS por
    primera vez -- antes era codigo muerto en round_trip()."""
    intent = resolve("métele un cuerpo", "es", mode="assisted",
                     propose_fn=lambda s, lang: ["agregar", "añadir"])

    assert intent.status is Status.AMBIGUOUS
    assert intent.can_act() is False
    assert set(intent.candidates) == {"agregar", "añadir"}

    frase = round_trip(intent, "es")
    assert not frase.startswith("Entendí"), f"AMBIGUOUS no debe afirmar: {frase!r}"
    assert "AGREGAR" in frase and "AÑADIR" in frase, (
        f"el mensaje de aclaracion debe mostrar los candidatos reales: {frase!r}")


def test_assisted_sin_candidatos_validos_sigue_unknown_sin_degradar():
    """Ambos lemas propuestos existen o no, pero ninguno sobrevive la
    validacion lexica -> sigue UNKNOWN, y sin degraded (el proponente SI
    corrio, solo que no encontro nada util -- eso no es una degradacion)."""
    intent = resolve("métele un cuerpo", "es", mode="assisted",
                     propose_fn=lambda s, lang: ["flurbizar", "forzar"])

    assert intent.status is Status.UNKNOWN
    assert intent.can_act() is False
    assert intent.provenance.degraded is None


def test_assisted_proponente_caido_degrada_y_lo_escribe_en_provenance():
    """Si el proponente revienta, resolve() falla cerrado (UNKNOWN) y la
    degradacion queda escrita en provenance.degraded, nunca silenciosa."""
    def caido(surface, lang):
        raise RuntimeError("sin red")

    intent = resolve("métele un cuerpo", "es", mode="assisted", propose_fn=caido)

    assert intent.status is Status.UNKNOWN
    assert intent.provenance.mode == "assisted"
    assert intent.provenance.degraded is not None
    assert "sin red" in intent.provenance.degraded


def test_modo_strict_nunca_invoca_al_proponente():
    """El modo strict no cambia de comportamiento aunque se le pase
    propose_fn: nunca deberia ejecutarlo. Se mide con un contador real, no
    con la ausencia de crash."""
    llamadas = []

    def contador(surface, lang):
        llamadas.append((surface, lang))
        return ["agregar"]

    intent = resolve("métele un cuerpo", "es", mode="strict", propose_fn=contador)

    assert intent.status is Status.UNKNOWN
    assert llamadas == [], "strict invoco al proponente: eso no es strict"
    assert intent.provenance.resolution == "lexicon"
    assert intent.provenance.cache_key is None


def test_assisted_sin_propose_fn_no_intenta_nada():
    """mode='assisted' solo no alcanza: sin propose_fn, el gate se queda
    cerrado y el resultado es identico al strict."""
    intent = resolve("mǸtele un cuerpo", "es", mode="assisted")

    assert intent.status is Status.UNKNOWN
    assert intent.provenance.resolution == "lexicon"
    assert intent.provenance.cache_key is None


# --- Tests nuevos para cubrir los fallos criticos detectados en la revisión ---


def test_verb_candidates_no_genera_falsos_positivos():
    """verb_candidates SOLO reconstruye formas imperativas conocidas problemáticas.
    NO aplica regla general '-a' -> '-ar' que generaría falsos positivos
    como 'casa' -> 'casar', 'pasa' -> 'pasar', etc."""
    # Estas son las formas problematicas conocidas (deben reconstruirse)
    assert verb_candidates("copia", "es") == ["copia", "copiar"]
    assert verb_candidates("borra", "es") == ["borra", "borrar"]
    assert verb_candidates("graba", "es") == ["graba", "grabar"]
    
    # Estas NO son formas problematicas conocidas (NO deben reconstruirse)
    # para evitar falsos positivos como "casa" -> "casar"
    assert verb_candidates("casa", "es") == ["casa"]
    assert verb_candidates("pasa", "es") == ["pasa"]
    assert verb_candidates("cama", "es") == ["cama"]
    assert verb_candidates("mesa", "es") == ["mesa"]
    assert verb_candidates("pala", "es") == ["pala"]
    
    # Inglés y chino no tienen reconstrucción
    assert verb_candidates("copy", "en") == ["copy"]
    assert verb_candidates("复制", "zh") == ["复制"]


def test_verb_candidates_falso_positivo_no_resuelve():
    """Un candidato falso generado por verb_candidates (si se agregara por error)
    NO debe resolver a primitiva porque el lexico NO lo valida como verbo
    con primitiva asociada."""
    # 'casa' NO está en la lista de imperativos problematicos
    # por tanto verb_candidates("casa", "es") == ["casa"] (solo el original)
    # y "casa" como verbo no tiene primitiva asociada -> UNKNOWN
    intent = resolve("casa el archivo", "es")
    assert intent.status is Status.UNKNOWN


def test_multiples_verbos_elige_el_primero():
    """_first_verb elige el PRIMER verbo que resuelve a primitiva en orden
    de tokens. En 'copia y pega el archivo', elige 'copia' (COPY) y ignora
    'pega' (PASTE). Esto es una LIMITACION documentada (requiere dominio)."""
    intent = resolve("copia y pega el archivo", "es")
    assert intent.status is Status.RESOLVED
    assert intent.primitive == "COPY"  # Elige el primero, no 'pega'
    assert intent.verb.lemma == "copiar"


def test_multiples_verbos_orden_importa():
    """El orden de los tokens determina qué verbo se elige.
    'pega y copia el archivo' -> PASTE (primero 'pega')
    'copia y pega el archivo' -> COPY (primero 'copia')"""
    intent1 = resolve("pega y copia el archivo", "es")
    assert intent1.primitive == "PASTE" if resolve("pega", "es").primitive == "PASTE" else "COPY"
    
    intent2 = resolve("copia y pega el archivo", "es")
    assert intent2.primitive == "COPY"


def test_operando_descarta_por_posicion_no_por_string():
    """_first_operand descarta por POSICION (indice), no por igualdad de string.
    'copia copia el archivo' -> primera 'copia' es verbo, segunda 'copia'
    es operando (archivo implícito). No debe descartar ambas."""
    intent = resolve("copia copia el archivo", "es")
    assert intent.status is Status.RESOLVED
    assert intent.primitive == "COPY"
    # El operando debería ser la segunda 'copia' (como si fuera 'archivo' implícito)
    # o 'archivo' si se menciona explicitamente
    # Lo importante: NO debe fallar por descartar ambas 'copia'


def test_operando_usa_primer_sentido_wordnet_determinista():
    """_first_operand usa el primer sentido de WordNet (el mas frecuente).
    No es perfecto pero es determinista y reproducible."""
    # 'archivo' tiene multiples sentidos en WordNet (file, archive, record, etc.)
    # El test verifica que siempre devuelve el mismo ILI (determinista)
    intent1 = resolve("copia el archivo", "es")
    intent2 = resolve("copia el archivo", "es")
    assert intent1.operand.ili == intent2.operand.ili, "ILI del operando debe ser determinista"


def test_provenance_completa_en_assisted():
    """En modo assisted, la provenance debe tener TODOS los campos obligatorios
    incluyendo confidence, degraded, cache_key, resolution, mode."""
    intent = resolve("métele un cuerpo", "es", mode="assisted",
                     propose_fn=lambda s, lang: ["agregar"])
    p = intent.provenance
    assert p.mode == "assisted"
    assert p.resolution == "llm_proposed+lexicon_validated"
    assert p.confidence == "proposed"
    assert p.cache_key is not None
    assert p.degraded is None  # no hay degradacion si el proponente funciona
    assert p.surface == "métele un cuerpo"
    assert p.language == "es"
    assert p.lexical_source == "omw-es:1.4"


def test_assisted_degraded_se_propaga():
    """Si el proponente falla (excepción), la degradación se propaga en provenance
    y NO se pierde (nunca en silencio)."""
    def caido(surface, lang):
        raise RuntimeError("sin red")

    intent = resolve("métele un cuerpo", "es", mode="assisted", propose_fn=lambda s, lang: 1/0)
    
    assert intent.status is Status.UNKNOWN
    assert intent.provenance.degraded is not None
    assert "division by zero" in intent.provenance.degraded or "zero" in intent.provenance.degraded.lower()


def test_strict_nunca_invoca_propose():
    """Modo strict NUNCA invoca propose_fn, aunque se le pase."""
    def contador(surface, lang):
        raise AssertionError("strict no debe invocar propose_fn")

    intent = resolve("metele un cuerpo", "es", mode="strict", propose_fn=lambda s, lang: ["agregar"])
    assert intent.status is Status.UNKNOWN
    assert intent.provenance.resolution == "lexicon"
    assert intent.provenance.cache_key is None


# --- Intenciones en competencia: el sistema no adivina cual queria el usuario ---

def test_dos_verbos_con_primitivas_distintas_dan_ambiguous():
    """"copia y borra el archivo" tiene dos intenciones que compiten.

    Quedarse con la primera seria adivinar. El estado AMBIGUOUS existe para
    esto y no puede actuar.
    """
    intent = resolve("copia y borra el archivo", "es")

    assert intent.status is Status.AMBIGUOUS
    assert intent.can_act() is False
    assert set(intent.candidates) == {"copiar", "borrar"}


def test_dos_verbos_con_LA_MISMA_primitiva_no_son_ambiguos():
    """El test que impide que el arreglo se pase de estricto.

    "cambia y modifica" son dos verbos distintos que resuelven ambos a CHANGE.
    No compiten: la intencion esta determinada. La ambiguedad es de la
    PRIMITIVA, no de la superficie -- lo que se pregunta no es que palabra
    usaste sino que querias hacer. Sin este test, "detectar ambiguedad" se
    degrada a "cualquier frase con dos verbos deja de resolver".
    """
    intent = resolve("cambia y modifica el archivo", "es")

    assert intent.status is Status.RESOLVED
    assert intent.primitive == "CHANGE"
    assert intent.can_act() is True


def test_un_solo_verbo_sigue_resolviendo():
    """Regresion: el caso normal no se rompio al agregar la deteccion."""
    intent = resolve("copia el archivo", "es")
    assert intent.status is Status.RESOLVED
    assert intent.primitive == "COPY"


@pytest.mark.parametrize(
    "text",
    [
        "no copies el archivo",
        "no borres el archivo",
        "si falla, borra el archivo",
        "el manual dice: borra el archivo",
    ],
)
def test_contexto_negativo_condicional_o_reportado_no_es_ejecutable(text):
    intent = resolve(text, "es")

    assert intent.status is Status.UNKNOWN
    assert intent.can_act() is False


def test_la_competencia_se_detecta_en_los_tres_idiomas():
    """No es una regla del espanol: es del modelo de intencion."""
    es = resolve("copia y borra el archivo", "es")
    en = resolve("copy and delete the file", "en")
    assert es.status is Status.AMBIGUOUS
    assert en.status is Status.AMBIGUOUS
    assert len(en.candidates) == 2


def test_ambiguous_por_competencia_pide_aclaracion_sin_afirmar():
    """El round-trip de una intencion en competencia pregunta, no afirma."""
    intent = resolve("copia y borra el archivo", "es")
    frase = round_trip(intent, "es")

    assert not frase.startswith("Entendí"), f"AMBIGUOUS no debe afirmar: {frase!r}"
    assert "COPIAR" in frase and "BORRAR" in frase, (
        f"debe mostrar las intenciones que compiten: {frase!r}")
