"""Paridad semantica entre oraculos: la convergencia se demuestra ejecutando.

Pipeline por superficie:

    texto -> resolve() -> Intent (primitiva + operando)
          -> instanciacion (el operando se baja a un simbolo sin idioma
             usando la DOMAIN_TABLE como HIPOTESIS en prueba)
          -> oraculo simbolico (oracle.py) -> huella de estado
          -> oraculo real (cap.fs.* en tmpdir) -> huella de estado

Un grupo de superficies (misma etiqueta, varios idiomas) es VERIFIED si todas
las ejecuciones producen la MISMA huella en ambos oraculos, y REJECTED si
divergen. La hipotesis (la fila de la tabla de dominio) no se confirma por
afirmacion: se confirma porque sus instanciaciones colapsan al mismo estado
observable. Los gaps no se rellenan: una superficie cuyo operando no tiene
hipotesis queda NOT_INSTANTIABLE y se reporta como gap, nunca se adivina.

Controles obligatorios por grupo: las huellas de las primitivas soportadas
sobre el mismo simbolo deben ser todas distintas (granularidad). Si el
control falla, el grupo entero queda NOT_DEMONSTRATED — medir paridad con un
oraculo que no distingue ADD de REMOVE no mide nada.
"""
from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path

from . import oracle
from .domain import DOMAIN_TABLE
from .ir import Status
from .resolve import resolve

# Primitivas del oraculo simbolico que tienen ademas un oraculo real (fs).
_REAL_CAPABILITY: dict[str, str] = {
    "COPY": "cap.fs.copy",
    "REMOVE": "cap.fs.delete",
    "MOVE": "cap.fs.move",
}

_ORIGIN = "origin"
_DEST = "dest"


# ============================================================
# Instanciacion: la hipotesis bajo prueba
# ============================================================


def symbol_for_lemma(lemma: str, hypothesis: dict[str, dict[str, str]] | None = None) -> str | None:
    """Simbolo sin idioma para un lema, segun la hipotesis (tabla de dominio).

    Sin hipotesis no hay instanciacion: devolver None es la respuesta
    honesta ("gap de tabla"), nunca un fallback al propio lema — eso haria la
    prueba circular (cada palabra se instanciaria a si misma y convergeria
    consigo misma por construccion).
    """
    table = DOMAIN_TABLE if hypothesis is None else hypothesis
    low = lemma.lower()
    for domain_id, lang_map in table.items():
        if any(low == m.lower() for m in lang_map.values()):
            return domain_id
    return None


# ============================================================
# Runs
# ============================================================


@dataclass(frozen=True, slots=True)
class SurfaceRun:
    """Una superficie llevada a traves de ambos oraculos."""

    surface: str
    lang: str
    status: str                  # Status.value de la resolucion
    primitive: str | None
    symbol: str | None
    symbolic_fingerprint: str | None
    real_fingerprint: str | None  # None si la primitiva no tiene oraculo real
    verdict: str                 # EXECUTED | NOT_RESOLVED | NOT_INSTANTIABLE
                               # | UNSUPPORTED_PRIMITIVE | ORACLE_ERROR
    note: str | None = None

    def to_dict(self) -> dict:
        return {
            "surface": self.surface,
            "lang": self.lang,
            "status": self.status,
            "primitive": self.primitive,
            "symbol": self.symbol,
            "symbolic_fingerprint": self.symbolic_fingerprint,
            "real_fingerprint": self.real_fingerprint,
            "verdict": self.verdict,
            "note": self.note,
        }


def _real_fs_fingerprint(primitive: str, symbol: str) -> str:
    """Oraculo real: ejecuta la capability fs en un tmpdir con layout canonico.

    El layout reproduce el mundo simbolico al pie de la letra (origin/simbolo
    con contenido content_of(simbolo), mismos nombres de destino), asi la
    huella es comparable con `oracle.fingerprint` y la comparacion es una
    prueba de correspondencia entre semantica simbolica y efectos reales.
    """
    from .capabilities import execute_capability

    cap = _REAL_CAPABILITY[primitive]
    origin_file = Path(_ORIGIN) / symbol
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / _ORIGIN).mkdir()
        (root / origin_file).write_text(oracle.content_of(symbol), encoding="utf-8")

        if primitive == "COPY":
            # Mismo destino que el oraculo simbolico: la semantica de COPY
            # vive en oracle.copy_destination, aqui solo se reproduce.
            dst_rel = oracle.copy_destination(
                origin_file.as_posix(),
                {origin_file.as_posix(): oracle.content_of(symbol)})
            execute_capability(cap, {
                "src": str(root / origin_file), "dst": str(root / dst_rel)})
        elif primitive == "MOVE":
            (root / _DEST).mkdir()
            execute_capability(cap, {
                "src": str(root / origin_file), "dst": str(root / _DEST / symbol)})
        elif primitive == "REMOVE":
            execute_capability(cap, {"path": str(root / origin_file)})

        entries = [
            (p.relative_to(root).as_posix(), p.read_text(encoding="utf-8"))
            for p in sorted(root.rglob("*"))
            if p.is_file()
        ]
        return oracle.entries_fingerprint(entries)


def run_surface(
    text: str,
    lang: str,
    hypothesis: dict[str, dict[str, str]] | None = None,
    crosscheck_real: bool = True,
) -> SurfaceRun:
    """Resuelve una superficie y la lleva por el (los) oraculo(s)."""
    try:
        intent = resolve(text, lang)
    except Exception as e:
        # La medicion de N idiomas no puede morir por el idioma 9: un lexico
        # no instalado o un tokenizer roto (jieba/fugashi) es un gap de
        # cobertura reportable, jamas una excepcion que tumbe el grupo.
        return SurfaceRun(
            surface=text, lang=lang, status="LEXICON_ERROR",
            primitive=None, symbol=None, symbolic_fingerprint=None,
            real_fingerprint=None, verdict="UNSUPPORTED_LANGUAGE",
            note=f"{type(e).__name__}: {e}",
        )
    # kwargs explicitos: mypy no rastrea un dict **base sin perder el tipo
    symbol: str | None = None
    symbolic_fingerprint: str | None = None
    real_fingerprint: str | None = None

    if intent.status is not Status.RESOLVED:
        return SurfaceRun(
            surface=text, lang=lang, status=intent.status.value,
            primitive=intent.primitive, symbol=None, symbolic_fingerprint=None,
            real_fingerprint=None, verdict="NOT_RESOLVED",
            note=f"resolve -> {intent.status.value}",
        )

    if intent.operand is None:
        return SurfaceRun(
            surface=text, lang=lang, status=intent.status.value,
            primitive=intent.primitive, symbol=None, symbolic_fingerprint=None,
            real_fingerprint=None, verdict="NOT_INSTANTIABLE", note="sin operando",
        )

    symbol = symbol_for_lemma(intent.operand.lemma, hypothesis)
    if symbol is None:
        return SurfaceRun(
            surface=text, lang=lang, status=intent.status.value,
            primitive=intent.primitive, symbol=None, symbolic_fingerprint=None,
            real_fingerprint=None, verdict="NOT_INSTANTIABLE",
            note=f"'{intent.operand.lemma}' sin hipotesis en la tabla de dominio",
        )

    if intent.primitive not in oracle.SUPPORTED:
        return SurfaceRun(
            surface=text, lang=lang, status=intent.status.value,
            primitive=intent.primitive, symbol=symbol, symbolic_fingerprint=None,
            real_fingerprint=None, verdict="UNSUPPORTED_PRIMITIVE",
            note=f"{intent.primitive} no tiene semantica en el oraculo",
        )

    try:
        execution = oracle.run(intent.primitive, symbol)
    except oracle.OracleError as e:
        return SurfaceRun(
            surface=text, lang=lang, status=intent.status.value,
            primitive=intent.primitive, symbol=symbol, symbolic_fingerprint=None,
            real_fingerprint=None, verdict="ORACLE_ERROR",
            note=f"{type(e).__name__}: {e}",
        )
    symbolic_fingerprint = execution.final_fingerprint

    if crosscheck_real and intent.primitive in _REAL_CAPABILITY:
        real_fingerprint = _real_fs_fingerprint(intent.primitive, symbol)

    return SurfaceRun(
        surface=text, lang=lang, status=intent.status.value,
        primitive=intent.primitive, symbol=symbol,
        symbolic_fingerprint=symbolic_fingerprint,
        real_fingerprint=real_fingerprint, verdict="EXECUTED", note=None,
    )


# ============================================================
# Veredictos de grupo
# ============================================================

VERIFIED = "VERIFIED"
REJECTED = "REJECTED"
NOT_DEMONSTRATED = "NOT_DEMONSTRATED"


@dataclass(frozen=True, slots=True)
class ParityReport:
    """Resultado de medir paridad sobre un grupo (una intencion, N superficies)."""

    label: str
    verdict: str                 # VERIFIED | REJECTED | NOT_DEMONSTRATED
    reason: str
    runs: tuple[SurfaceRun, ...]
    controls_ok: bool
    controls: dict[str, str]     # primitiva -> huella (control de granularidad)
    gaps: tuple[str, ...] = ()   # superficies no instanciables, reportadas como gap

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "verdict": self.verdict,
            "reason": self.reason,
            "runs": [r.to_dict() for r in self.runs],
            "controls_ok": self.controls_ok,
            "controls": self.controls,
            "gaps": list(self.gaps),
        }

    def fingerprint(self) -> str:
        import hashlib

        return hashlib.sha256(oracle.canonical_json(self.to_dict())).hexdigest()


def parity_for_group(
    cases: list[dict],
    label: str,
    hypothesis: dict[str, dict[str, str]] | None = None,
    crosscheck_real: bool = True,
) -> ParityReport:
    """Mide paridad de un grupo: todas las superficies deben colapsar a la
    misma huella en el oraculo simbolico Y (cuando aplica) en el real.

    Veredictos:
    - VERIFIED: >=2 superficies ejecutadas, huellas iguales en ambos
      oraculos, controles de granularidad OK.
    - REJECTED: las ejecuciones divergen (la hipotesis no sostiene la
      equivalencia, o las primitivas resueltas difieren entre idiomas).
    - NOT_DEMONSTRATED: <2 ejecuciones, o los controles fallan.
    """
    runs = tuple(
        run_surface(c["text"], c["lang"], hypothesis, crosscheck_real) for c in cases
    )
    controls = oracle.granularity_controls()
    controls_ok = len(set(controls.values())) == len(controls)

    executed = [r for r in runs if r.verdict == "EXECUTED"]
    # GAP es TODO lo no ejecutado: no instanciable, no resuelto, idioma sin
    # lexico, primitiva sin semantica, error de oraculo. Reportarlos todos es
    # la mitad del valor: el mapa de cobertura real, no el subconjunto bonito.
    gaps = tuple(
        f"{r.lang}:{r.surface} [{r.verdict}] ({r.note})"
        for r in runs
        if r.verdict != "EXECUTED"
    )

    if not controls_ok:
        return ParityReport(label, NOT_DEMONSTRATED,
                            "controles de granularidad fallaron: el oraculo no distingue primitivas",
                            runs, controls_ok, controls, gaps)
    if len(executed) < 2:
        return ParityReport(label, NOT_DEMONSTRATED,
                            f"solo {len(executed)} superficie(s) ejecutables; no hay nada que comparar",
                            runs, controls_ok, controls, gaps)

    symbolic = {r.symbolic_fingerprint for r in executed}
    if len(symbolic) != 1:
        by_surface = ", ".join(
            f"{r.lang}={r.primitive}/{r.symbol}/{(r.symbolic_fingerprint or '-')[:12]}"
            for r in executed
        )
        return ParityReport(label, REJECTED,
                            f"huellas simbolicas divergen: {by_surface}",
                            runs, controls_ok, controls, gaps)

    real = [r for r in executed if r.real_fingerprint is not None]
    if real:
        real_prints = {r.real_fingerprint for r in real}
        if len(real_prints) != 1:
            return ParityReport(label, REJECTED,
                                "las ejecuciones reales divergen entre superficies",
                                runs, controls_ok, controls, gaps)
        if real_prints.pop() != executed[0].symbolic_fingerprint:
            return ParityReport(label, REJECTED,
                                "oraculo real y simbolico divergen: la semantica simbolica no corresponde al efecto real",
                                runs, controls_ok, controls, gaps)

    return ParityReport(label, VERIFIED,
                        f"{len(executed)} superficies, misma huella en "
                        f"{'ambos oraculos' if real else 'oraculo simbolico'}",
                        runs, controls_ok, controls, gaps)


# ============================================================
# Tiers por escritura: diagnostico, NUNCA sustituto del veredicto
# ============================================================

_SCRIPT_TIER: dict[str, str] = {
    "es": "latin", "en": "latin", "fi": "latin", "tr": "latin", "vi": "latin",
    "zh": "cjk", "ja": "cjk",
    "ar": "arabic", "he": "hebrew",
    "ko": "hangul", "th": "thai", "ru": "cyrillic", "hi": "devanagari",
}


def script_tier(lang: str) -> str:
    return _SCRIPT_TIER.get(lang, "unknown")


def tier_breakdown(report: ParityReport) -> dict[str, dict]:
    """Convergencia INTRA-tier de un grupo, como diagnostico.

    Regla anti-trampa: esto existe para saber DONDE duele (tokenizer,
    escritura, semantica), no para inflar la metrica. El veredicto del
    grupo sigue siendo el global; un tier convergiendo no hace VERIFIED a
    nada. El dia que alguien reporte solo los tiers y esconda el global,
    esto se habra convertido en la metrica trampa que el README prohibe.
    """
    tiers: dict[str, list[SurfaceRun]] = {}
    for run in report.runs:
        if run.verdict == "EXECUTED":
            tiers.setdefault(script_tier(run.lang), []).append(run)
    out: dict[str, dict] = {}
    for tier, runs in tiers.items():
        fingerprints = {r.symbolic_fingerprint for r in runs}
        out[tier] = {
            "runs": len(runs),
            "langs": sorted(r.lang for r in runs),
            # None = un solo run: no hay par que comparar, no se afirma nada
            "converged": (len(fingerprints) == 1) if len(runs) >= 2 else None,
        }
    return out


# ============================================================
# Corpus y evidencia de la tabla de dominio
# ============================================================


def run_corpus_parity(
    corpus_path: Path,
    crosscheck_real: bool = True,
) -> list[ParityReport]:
    """Corre paridad sobre todos los grupos (label) de un corpus jsonl."""
    groups: dict[str, list[dict]] = {}
    for line in corpus_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            case = json.loads(line)
            groups.setdefault(case["label"], []).append(case)
    return [parity_for_group(cases, label, crosscheck_real=crosscheck_real)
            for label, cases in groups.items()]


def prove_domain_table(
    hypothesis: dict[str, dict[str, str]] | None = None,
    crosscheck_real: bool = True,
    probe_verb: str = "copy",
) -> dict:
    """Genera la evidencia de la tabla de dominio, fila por fila.

    Lo que se prueba por fila no es la fila como hecho aislado sino la
    HIPOTESIS completa: "<lema> en cada idioma nombra al mismo simbolo".
    Para eso se forma la superficie `<verbo sonda> <lema>` por idioma con
    una primitiva que el oraculo puede ejecutar (COPY via `probe_verb`,
    cuyo domain_id debe existir en la tabla), y se mide si todas las
    superficies colapsan a la misma huella.

    - Filas de VERBOS (domain_id en DOMAIN_PRIMITIVE_MAP) se prueban con un
      operando sonda ("file") y una regla extra: la primitiva resuelta debe
      ser EXACTAMENTE la que la tabla afirma. Si "copy" resolviera a MOVE,
      la huella convergeria igualmente (toda primitiva converge consigo
      misma) y la afirmacion de la tabla seria falsa: la regla lo detecta.
    - Idiomas sin sonda o sin lema se excluyen; <2 supervivientes ->
      NOT_DEMONSTRATED.
    - El resultado lo consume domain.py via `load_oracle_proofs()` y lo
      persiste el CLI. Nada de esto reescribe la tabla: la evidencia se
      apoya en ella, no la modifica.
    """
    from .domain import DOMAIN_PRIMITIVE_MAP

    table = DOMAIN_TABLE if hypothesis is None else hypothesis
    verb_lemmas = table.get(probe_verb, {})
    probe_operand = table.get("file", {})

    proofs: dict[str, dict] = {}
    for domain_id, lang_map in table.items():
        is_verb = domain_id in DOMAIN_PRIMITIVE_MAP
        if is_verb:
            cases = [
                {"text": f"{lemma} {probe_operand[lang]}", "lang": lang}
                for lang, lemma in lang_map.items()
                if lang in probe_operand
            ]
        else:
            cases = [
                {"text": f"{verb_lemmas[lang]} {lemma}", "lang": lang}
                for lang, lemma in lang_map.items()
                if lang in verb_lemmas
            ]
        if len(cases) < 2:
            proofs[domain_id] = {
                "verdict": NOT_DEMONSTRATED,
                "reason": "<2 idiomas con sonda y lema disponibles",
            }
            continue
        report = parity_for_group(cases, f"domain/{domain_id}",
                                  hypothesis=table, crosscheck_real=crosscheck_real)
        verdict, reason = report.verdict, report.reason
        if is_verb and verdict == VERIFIED:
            expected = DOMAIN_PRIMITIVE_MAP[domain_id]
            resolved = {r.primitive for r in report.runs
                        if r.verdict == "EXECUTED" and r.primitive is not None}
            if resolved != {expected}:
                verdict = REJECTED
                reason = (f"la huella converge pero la primitiva resuelta {sorted(resolved)}"
                          f" != la afirmada por la tabla ({expected})")
        proofs[domain_id] = {
            "verdict": verdict,
            "reason": reason,
            "fingerprint": report.fingerprint(),
            "controls_ok": report.controls_ok,
            "surfaces": [r.to_dict() for r in report.runs],
        }
    return {
        "schema": "domain-oracle-proofs/1",
        "verdicts": proofs,
    }


# ============================================================
# CLI
# ============================================================


def main(argv: list[str] | None = None) -> int:
    """`py -m intentlang.parity ...`

      corpus [seed.jsonl] [--no-real]   Corre paridad sobre el corpus.
      prove [--out PATH] [--no-real]    Genera la evidencia de la DOMAIN_TABLE
                                        (por defecto data/domain_oracle_proofs.json).
    """
    import argparse
    import sys

    # El reporte lleva superficies CJK/arabes: cp1252 las mata a mitad de
    # linea. UTF-8 o nada (y nunca morir por una terminal).
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(prog="intentlang.parity")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_corpus = sub.add_parser("corpus")
    default_corpus = Path(__file__).resolve().parents[2] / "corpus" / "seed.jsonl"
    p_corpus.add_argument("path", nargs="?", type=Path, default=default_corpus)
    p_corpus.add_argument("--no-real", action="store_true",
                          help="solo oraculo simbolico (sin cross-check fs real)")
    p_prove = sub.add_parser("prove")
    p_prove.add_argument("--out", type=Path,
                         default=Path(__file__).resolve().parents[2]
                         / "data" / "domain_oracle_proofs.json")
    p_prove.add_argument("--no-real", action="store_true")
    args = parser.parse_args(argv)

    crosscheck = not getattr(args, "no_real", False)

    if args.cmd == "corpus":
        reports = run_corpus_parity(args.path, crosscheck_real=crosscheck)
        verified = sum(1 for r in reports if r.verdict == VERIFIED)
        for r in reports:
            print(f"  {r.verdict:16} {r.label:14} {r.reason}")
            for tier, info in tier_breakdown(r).items():
                conv = ("converge" if info["converged"] else
                        "DIVERGE" if info["converged"] is False else "single")
                print(f"      tier {tier:10} {conv:9} langs={','.join(info['langs'])}")
            for gap in r.gaps:
                print(f"    GAP {gap}")
        print(f"paridad oraculo: {verified}/{len(reports)} grupos"
              f" ({100 * verified / len(reports):.0f}%)" if reports else "corpus vacio")
        return 0 if all(r.verdict != REJECTED for r in reports) else 1

    if args.cmd == "prove":
        proofs = prove_domain_table(crosscheck_real=crosscheck)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        import hashlib

        payload = oracle.canonical_json(proofs)
        args.out.write_bytes(payload)
        digest = hashlib.sha256(payload).hexdigest()
        counts: dict[str, int] = {}
        for entry in proofs["verdicts"].values():
            counts[entry["verdict"]] = counts.get(entry["verdict"], 0) + 1
        print(f"filas: {counts} -> {args.out}")
        print(f"sha256: {digest}")
        return 0 if "REJECTED" not in counts else 1

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
