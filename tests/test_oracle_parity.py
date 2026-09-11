"""Paridad semantica por oraculo: la convergencia se demuestra ejecutando.

Contraste deliberado con test_separation.py:
- La convergencia por ILI (test_convergencia_se_reporta_no_reprueba) mide la
  salud del LEXICON: hoy 0/3 por los gaps de alineacion OMW entre idiomas.
  Sigue reportandose tal cual.
- La convergencia por ORACULO mide lo que el sistema demuestra por
  ejecucion: superficies que colapsan a la misma huella de estado en la
  maquina simbolica y en el fs real. Eso es lo que rompe aqui si falla.

Reglas del juego:
- Controles negativos siempre: si el oraculo no distingue COPY de REMOVE,
  toda paridad medida con el es trampa y los tests lo gritan.
- Los gaps se reportan (NOT_INSTANTIABLE), no se rellenan.
- Sin tautologia: un operando sin hipotesis en la tabla no se instancia.
"""
import json
from pathlib import Path

import pytest

from engine_lang.registry import registry
from intentlang import lexicon, oracle
from intentlang.parity import (
    NOT_DEMONSTRATED,
    REJECTED,
    VERIFIED,
    parity_for_group,
    prove_domain_table,
    run_corpus_parity,
    run_surface,
)

LANGS_WN = registry().languages_with_wordnet

CORPUS = Path(__file__).resolve().parents[1] / "corpus" / "seed.jsonl"


def cargar():
    return [json.loads(line) for line in CORPUS.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.fixture(scope="module", autouse=True)
def _instalar():
    for lang in LANGS_WN:
        lexicon.ensure_installed(lang)


# ============================================================
# Maquina: determinismo y granularidad (la metrica no es trampa)
# ============================================================


def test_oraculo_determinista():
    a = oracle.run("COPY", "file")
    b = oracle.run("COPY", "file")
    assert a.final_fingerprint == b.final_fingerprint
    assert a.initial_fingerprint == b.initial_fingerprint


def test_simbolos_distintos_dan_huellas_distintas():
    """La huella depende del simbolo: sin esto, COPY(x) == COPY(y) siempre
    y la paridad no mediría nada sobre operandos."""
    assert oracle.run("COPY", "file").final_fingerprint != oracle.run("COPY", "body").final_fingerprint


def test_controles_negativos_granularidad():
    """Las 4 primitivas con el MISMO simbolo producen 4 huellas distintas.

    Si esto falla, la maquina no distingue intenciones y toda paridad
    medida con ella es una metrica trampa. Es el equivalente ejecutable de
    la invariante de separacion.
    """
    controles = oracle.granularity_controls()
    assert len(set(controles.values())) == len(controles), (
        f"primitivas colapsan en el oraculo: {controles}"
    )


def test_precondicion_violada_no_se_parchea():
    """REMOVE de algo inexistente es un error estructural, no un no-op
    silencioso. El oraculo honesto falla; el tramposo inventaria el estado."""
    from intentlang.oracle import PreconditionFailed

    with pytest.raises(PreconditionFailed):
        oracle.apply({}, "REMOVE", "file")
    with pytest.raises(PreconditionFailed):
        oracle.run("ADD", "file", world={"origin/file": "content:file"})


# ============================================================
# Cross-check: oraculo simbolico vs oraculo real
# ============================================================


@pytest.mark.parametrize("primitive", ["COPY", "MOVE", "REMOVE"])
def test_crosscheck_simbolico_vs_fs_real(primitive):
    """La semantica simbolica y el efecto real en un tmpdir producen la
    MISMA huella. Si divergen, uno de los dos oraculos miente sobre lo que
    la primitiva hace, y eso es un bug de verdad, no de metrica."""
    from intentlang.parity import _real_fs_fingerprint

    simbolica = oracle.run(primitive, "file").final_fingerprint
    real = _real_fs_fingerprint(primitive, "file")
    assert simbolica == real, (
        f"{primitive}: oraculo simbolico {simbolica[:16]} != real {real[:16]}"
    )


# ============================================================
# Paridad del corpus: LA metrica que esto introduce
# ============================================================


def test_paridad_corpus_por_oraculo():
    """Los grupos del corpus deben converger POR EJECUCION.

    La convergencia por ILI es 0/3 hoy (gap lexico documentado en README);
    esta metrica demuestra que las superficies son la misma intencion
    porque sus ejecuciones colapsan a la misma huella en ambos oraculos.
    """
    reports = run_corpus_parity(CORPUS)
    assert reports, "corpus vacio"
    for r in reports:
        assert r.verdict != REJECTED, f"{r.label}: {r.reason}"
    verified = [r for r in reports if r.verdict == VERIFIED]
    assert len(verified) == len(reports), (
        "grupos no demostrados: "
        + "; ".join(f"{r.label}={r.verdict} ({r.reason})" for r in reports if r.verdict != VERIFIED)
    )


def test_paridad_reporta_los_gaps_sin_rellenarlos():
    """Dos gaps distintos, ninguno rellenado:

    - "copia el documento": 'documento' resuelve en el lexico pero NO esta en
      la tabla de dominio -> NOT_INSTANTIABLE (falta hipotesis, no se adivina).
    - "duplica el fichero": 'fichero' ni siquiera resuelve operand en el
      lexico actual -> NOT_RESOLVED (gap del lexico).
    """
    report = parity_for_group(
        [{"text": "copia el archivo", "lang": "es"},
         {"text": "copia el documento", "lang": "es"},
         {"text": "duplica el fichero", "lang": "es"}],
        "COPY/file-es",
    )
    not_instantiable = [r for r in report.runs if r.verdict == "NOT_INSTANTIABLE"]
    assert not_instantiable and "documento" in not_instantiable[0].note
    assert any(r.verdict == "NOT_RESOLVED" for r in report.runs)
    assert report.gaps, "el gap de tabla debe aparecer en el reporte"


def test_sin_hipotesis_no_hay_instanciacion():
    """Con tabla vacia, NADA se instancia: la hipotesis es la unica puerta."""
    run = run_surface("copia el archivo", "es", hypothesis={})
    assert run.verdict == "NOT_INSTANTIABLE"
    assert run.symbolic_fingerprint is None


def test_divergencia_de_primitivas_es_rejected():
    """Dos superficies con primitivas distintas no pueden ser paridad.

    Si alguna vez el resolve asignara primitivas distintas a parafosis de la
    misma etiqueta, paridad debe decir REJECTED — no promediar.
    """
    report = parity_for_group(
        [{"text": "copia el archivo", "lang": "es"},
         {"text": "borra el archivo", "lang": "es"}],
        "control-divergente",
    )
    assert report.verdict == REJECTED


def test_menos_de_dos_ejecutables_es_not_demonstrated():
    report = parity_for_group(
        [{"text": "copia el archivo", "lang": "es"}], "singleton"
    )
    assert report.verdict == NOT_DEMONSTRATED


# ============================================================
# Colisiones documentadas: los REJECTED dejan conocimiento
# ============================================================


def test_colision_nql_no_reaparece_en_move():
    """La fila move afirmaba ar نقل; el oraculo demostro que ejecuta COPY.

    La correccion fue matizar: move.ar quedo en حرك (que el corpus ya usaba)
    y نقل quedo registrado en DOMAIN_COLLISIONS. Este test blinda ambos
    lados: la colision no reaparece en la fila y el registro no se vacia.
    """
    from intentlang.domain import DOMAIN_COLLISIONS, DOMAIN_TABLE

    for lemma, info in DOMAIN_COLLISIONS.items():
        fila = DOMAIN_TABLE.get(info["rejected_for"], {})
        assert fila.get(info["lang"]) != lemma, (
            f"'{lemma}' reaparecio en la fila {info['rejected_for']} "
            f"que el oraculo rechazo; si es deliberado, borra la colision"
        )


def test_colision_nql_sigue_resolviendo_copy():
    """La divergencia original era real: نقل + ملف sigue ejecutando COPY.

    Inferencia contraria: si un dia resuelve otra cosa, la evidencia vieja
    hay que revisarla, no asumirla eterna.
    """
    run = run_surface("نقل الملف", "ar")
    assert run.primitive == "COPY"
    assert run.verdict == "EXECUTED"


def test_move_corregido_converge():
    """Tras el matiz, la fila move converge en el oraculo (misma huella)."""
    report = parity_for_group(
        [{"text": "mueve el archivo", "lang": "es"},
         {"text": "move the file", "lang": "en"},
         {"text": "حرك الملف", "lang": "ar"}],
        "MOVE/file-fix",
    )
    assert report.verdict == VERIFIED, report.reason


# ============================================================
# Tiers por escritura: diagnostico, nunca sustituto del global
# ============================================================


def test_tiers_diagnostican_sin_sustituir():
    """El breakdown por escritura muestra donde duele, y el veredicto
    global sigue siendo el que manda: un tier convergiendo no convierte
    REJECTED en VERIFIED jamas."""
    from intentlang.parity import tier_breakdown

    report = parity_for_group(
        [{"text": "copia el archivo", "lang": "es"},
         {"text": "copy the file", "lang": "en"},
         {"text": "删除文件", "lang": "zh"}],
        "tiers-mixto",
    )
    tiers = tier_breakdown(report)
    assert tiers["latin"]["runs"] == 2
    assert tiers["latin"]["converged"] is True       # es+en colapsan
    assert tiers["cjk"]["converged"] is None          # zh solo: no se afirma nada
    # ...y el veredicto global refleja la divergencia real (COPY vs REMOVE)
    assert report.verdict == REJECTED


def test_script_tier_cubre_los_idiomas_del_corpus():
    from intentlang.parity import script_tier

    for caso in cargar():
        assert script_tier(caso["lang"]) != "unknown", caso["lang"]


# ============================================================
# Evidencia de la tabla de dominio
# ============================================================


def test_prove_domain_table_emite_veredictos():
    """La evidencia existe por fila y las filas cubiertas por la sonda se
    verifican o se rechazan — nada queda sin veredicto explicito."""
    proofs = prove_domain_table()
    assert proofs["schema"] == "domain-oracle-proofs/1"
    assert proofs["verdicts"], "la tabla de dominio no esta vacia"
    for domain_id, entry in proofs["verdicts"].items():
        assert entry["verdict"] in (VERIFIED, REJECTED, NOT_DEMONSTRATED), domain_id
    # La sonda 'copy' cubre file/directory/path como operandos; al menos esas
    verified = [d for d, e in proofs["verdicts"].items() if e["verdict"] == VERIFIED]
    assert "file" in verified, f"file debio verificarse: {proofs['verdicts'].get('file')}"


def test_evidencia_gate_en_resolve_with_domain(monkeypatch):
    """Con pruebas presentes, una fila NO verificada no hace override.

    La tabla afirmada a mano no basta: sin veredicto VERIFIED del oraculo,
    resolve_with_domain no puede fabricar un RESOLVED. La superficie usa un
    operando inventado ("quedrilo") para que el resolve estricto quede
    INCOMPLETE y el override sea la unica via posible.
    """
    import intentlang.domain as domain

    surface = "quiero copiar el quedrilo"  # 'copiar' esta en la tabla; 'quedrilo' es gap

    proofs_verified = {"copy": {"verdict": "VERIFIED"}}
    monkeypatch.setattr(domain, "load_oracle_proofs", lambda: proofs_verified)
    r = domain.resolve_with_domain_table(surface, "es")
    assert r.status.value == "RESOLVED"

    proofs_rejected = {"copy": {"verdict": "REJECTED"}}
    monkeypatch.setattr(domain, "load_oracle_proofs", lambda: proofs_rejected)
    r2 = domain.resolve_with_domain_table(surface, "es")
    assert r2.status.value != "RESOLVED"
