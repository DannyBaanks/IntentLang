"""Entrada de linea de comandos y arnes de juicio humano.

El arnes es la barra de exito del proyecto: muestra lo que el sistema entendio
y guarda el veredicto humano en judgments.jsonl. Cada veredicto aprobado se
promueve a seed.jsonl con label, asi la metrica humana arranca el corpus
que despues corre solo como regresion.
"""
from __future__ import annotations

import argparse
import getpass
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from engine_lang.registry import registry

from .discovery import discover
from .executor import execute_program
from .llm_oracle import (
    DEFAULT_GEMINI_MODEL,
    DEFAULT_OPENAI_MODEL,
    KeyringCredentialStore,
    OracleConfig,
    infer_provider,
)
from .lowering import lower_text_to_program
from .relex import round_trip
from .resolve import resolve

UTC = timezone.utc  # noqa: UP017 - supports the repository's mypy typeshed

CORPUS = Path(__file__).resolve().parents[2] / "corpus" / "seed.jsonl"
JUDGMENTS = Path(__file__).resolve().parents[2] / "corpus" / "judgments.jsonl"


def record_judgment(text: str, lang: str, verdict: str,
                    path: Path = JUDGMENTS) -> None:
    """Append-only. Los juicios van a judgments.jsonl (no al corpus de regresion)."""
    intent = resolve(text, lang)
    registro = {
        "text": text, "lang": lang, "verdict": verdict,
        "key": list(intent.key()), "status": intent.status.value,
        "at": datetime.now(UTC).isoformat(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(registro, ensure_ascii=False) + "\n")


def promote_judgment(text: str, lang: str, label: str,
                     path: Path = CORPUS) -> None:
    """Agrega juicio aprobado al corpus de regresion con label."""
    intent = resolve(text, lang)
    registro = {
        "text": text, "lang": lang, "label": label,
        "key": list(intent.key()), "status": intent.status.value,
        "at": datetime.now(UTC).isoformat(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(registro, ensure_ascii=False) + "\n")


def list_judgments(path: Path = JUDGMENTS) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except (AttributeError, ValueError):
                pass

    parser = argparse.ArgumentParser(prog="intentlang")
    sub = parser.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("resolve", help="resolver texto a IR")
    r.add_argument("text")
    lang_choices = registry().supported_languages
    r.add_argument("--lang", required=True, choices=lang_choices)
    r.add_argument("--mode", default="strict", choices=["strict", "assisted"])

    j = sub.add_parser("judge", help="arnes de juicio humano -> judgments.jsonl")
    j.add_argument("text")
    j.add_argument("--lang", required=True, choices=lang_choices)

    p = sub.add_parser("promote", help="promover juicio aprobado a seed.jsonl con label")
    p.add_argument("text")
    p.add_argument("--lang", required=True, choices=lang_choices)
    p.add_argument("--label", required=True, help="label esperado (ej: COPY/file)")

    sub.add_parser("list-judgments", help="listar juicios pendientes")

    oc = sub.add_parser("oracle-config", help="configurar el oraculo LLM localmente")
    oc.add_argument("--provider", choices=["auto", "gemini", "openai-compatible"], default="auto")
    oc.add_argument("--model", help="modelo; si se omite se usa el recomendado del proveedor")
    oc.add_argument("--google-search", action="store_true", help="activar grounding con Google Search en Gemini")
    sub.add_parser("oracle-status", help="mostrar proveedor/modelo configurado sin revelar la clave")

    # execute: resolve -> lower -> execute capabilities
    x = sub.add_parser("execute", help="resolver + ejecutar capabilities")
    x.add_argument("text")
    x.add_argument("--lang", required=True, choices=lang_choices)
    x.add_argument("--mode", default="strict", choices=["strict", "assisted"])
    x.add_argument("--run", action="store_true", help="ejecutar capabilities reales (no solo IR)")

    # discover: surface -> candidates -> verify -> register
    d = sub.add_parser("discover", help="descubrir primitiva desde surface UNKNOWN")
    d.add_argument("text")
    d.add_argument("--lang", required=True, choices=lang_choices)

    args = parser.parse_args(argv)

    if args.cmd == "resolve":
        intent = resolve(args.text, args.lang, getattr(args, "mode", "strict"))
        print(json.dumps(intent.to_dict(), ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "execute":
        prog = lower_text_to_program(args.text, args.lang, getattr(args, "mode", "strict"))
        if getattr(args, "run", False):
            result = execute_program(prog)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["status"] == "OK" else 1
        else:
            print(json.dumps(prog.to_dict(), ensure_ascii=False, indent=2))
            print("# Program IR generado. Usa --run para ejecutar capabilities reales.")
            return 0

    if args.cmd == "discover":
        from .discovery import DEFAULT_TEST_CASES
        test_cases = DEFAULT_TEST_CASES.get(args.text.split()[0].upper(), [])
        cand = discover(args.text, args.lang, test_cases)
        if cand:
            print(json.dumps({
                "primitive": cand.primitive,
                "capability": cand.capability,
                "confidence": cand.confidence,
                "contract": cand.contract,
            }, ensure_ascii=False, indent=2))
            print(f"# Registrada: {cand.primitive} -> {cand.capability}")
        else:
            print(f"# No se encontro candidato para: {args.text}")
        return 0

    if args.cmd == "list-judgments":
        for judgment in list_judgments():
            print(json.dumps(judgment, ensure_ascii=False))
        return 0

    if args.cmd == "oracle-config":
        api_key = getpass.getpass("API key del proveedor (no se mostrara): ").strip()
        if not api_key:
            print("No se guardo: la clave esta vacia", file=sys.stderr)
            return 2
        provider = infer_provider(api_key, None if args.provider == "auto" else args.provider)
        default_model = DEFAULT_GEMINI_MODEL if provider == "gemini" else DEFAULT_OPENAI_MODEL
        KeyringCredentialStore().save(OracleConfig(
            provider=provider,
            api_key=api_key,
            model=args.model or default_model,
            google_search=args.google_search,
        ))
        print(f"Oraculo configurado localmente: {provider}, modelo {args.model or default_model}")
        print("La clave no se imprime ni se envia hasta ejecutar una verificacion.")
        return 0

    if args.cmd == "oracle-status":
        try:
            config = KeyringCredentialStore().load()
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            print(f"Oraculo no configurado: {exc}", file=sys.stderr)
            return 1
        print(json.dumps({
            "provider": config.provider,
            "model": config.model,
            "google_search": config.google_search,
            "credentials_location": "OS keyring (intentlang/oracle)",
        }, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "promote":
        promote_judgment(args.text, args.lang, args.label)
        print(f"promovido a seed.jsonl: {args.text} [{args.lang}] -> {args.label}")
        return 0

    # judge
    intent = resolve(args.text, args.lang, getattr(args, "mode", "strict"))
    print(round_trip(intent, args.lang))
    veredicto = input("[si / no / ambiguo] > ").strip().lower()
    record_judgment(args.text, args.lang, veredicto)
    print(f"anotado en judgments.jsonl: {veredicto}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
