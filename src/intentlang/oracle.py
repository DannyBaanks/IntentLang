"""Oraculo semantico ejecutable: maquina de estado simbolico, sin idioma.

Para que sirve: la convergencia por ILI depende de que los wordnets de cada
idioma enlacen el mismo sentido, y hoy no lo hacen (es"archivo" -> i50132,
en"file" -> i70665). El oraculo mide paridad por EJECUCION, no por lexico:
dos superficies son paridad si, ejecutadas en esta maquina, dejan el mundo en
el mismo estado. La huella del estado es SHA-256 sobre una serializacion
canonica, asi que la evidencia es verificable y reproducible.

Modelo del mundo: `world` es un dict path -> contenido, donde path tiene la
forma "lugar/entidad" y el contenido es un string simbolico. Es
intencionadamente identico en forma a un arbol de archivos real: eso es lo
que permite el cross-check contra capabilities reales (cap.fs.*) usando la
MISMA funcion de huella sobre ambos oraculos.

Reglas de honestidad:
- Nunca se inventa una transicion: toda ejecucion pasa por `apply`, que
  exige precondiciones; una violacion produce PreconditionFailed, no un
  parche silencioso.
- La granularidad de la maquina es falsable: `granularity_controls`
  demuestra que las primitivas soportadas producen huellas DISTINTAS entre
  si. Si eso dejara de ser cierto, toda paridad medida con esta maquina
  seria trampa, y el test que lo detecta rompe el build.

Determinismo: mismo input, misma huella, garantizado por canonical_json
(sort_keys, separadores compactos, UTF-8).
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass, field

# Subconjunto del IR con semantica operacional definida en esta maquina.
# Extender esta lista es un acto deliberado: cada primitiva nueva necesita
# entrar tambien en `granularity_controls` para que su huella se demuestre
# distinta de las demas.
SUPPORTED: tuple[str, ...] = ("ADD", "COPY", "MOVE", "REMOVE")

_ORIGIN = "origin"
_DEST = "dest"


class OracleError(Exception):
    """Fallo estructural de la maquina (no una divergencia semantica)."""


class UnsupportedPrimitive(OracleError):
    """La primitiva no tiene semantica operacional en esta maquina."""


class PreconditionFailed(OracleError):
    """El mundo inicial no cumple lo que la primitiva exige. Reportar, nunca parchear."""


def canonical_json(obj) -> bytes:
    """Serializacion canonica: la unica que se hashea en todo el subsistema."""
    return json.dumps(
        obj, sort_keys=True, ensure_ascii=True, separators=(",", ":")
    ).encode("utf-8")


def entries_fingerprint(entries: Iterable[tuple[str, str]]) -> str:
    """Huella SHA-256 de un conjunto de pares (path, contenido).

    Es la MISMA funcion para el mundo simbolico y para el arbol real: la
    paridad entre oraculos es comparacion de esta huella, no de estructuras.
    """
    material = [[path, _sha256_str(content)] for path, content in sorted(entries)]
    return hashlib.sha256(canonical_json(material)).hexdigest()


def _sha256_str(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def content_of(symbol: str) -> str:
    """Contenido canonico de una entidad simbolica.

    Determinista y derivado del simbolo: el mundo real (tmpdir) escribe
    exactamente este string para que ambas huellas sean comparables.
    """
    return f"content:{symbol}"


def initial_world(symbol: str, primitive: str | None = None) -> dict[str, str]:
    """Mundo inicial canonico para ejecutar `symbol` con `primitive`.

    La precondicion de cada primitiva decide el mundo: ADD exige ausencia
    (mundo vacio), COPY/MOVE/REMOVE exigen presencia (el simbolo existe en
    origin). Un mundo inicial unico haria a ADD inejecutable y esconderia
    la diferencia semantica entre "traer a la existencia" y "operar sobre
    lo existente".
    """
    if primitive == "ADD":
        return {}
    return {f"{_ORIGIN}/{symbol}": content_of(symbol)}


@dataclass(frozen=True, slots=True)
class Execution:
    """Una ejecucion en el oraculo, con todo lo necesario para auditarla."""

    primitive: str
    symbol: str
    initial_fingerprint: str
    final_fingerprint: str
    world: dict[str, str] = field(compare=False, hash=False)

    def to_dict(self) -> dict:
        return {
            "primitive": self.primitive,
            "symbol": self.symbol,
            "initial_fingerprint": self.initial_fingerprint,
            "final_fingerprint": self.final_fingerprint,
            "world": dict(sorted(self.world.items())),
        }


def fingerprint(world: dict[str, str]) -> str:
    return entries_fingerprint(world.items())


def copy_destination(src: str, world: dict[str, str]) -> str:
    """Path del duplicado de COPY: primero de la forma `<src>.dupN`, N desde 1.

    Publica porque la semantica de COPY vive en UN solo sitio: el oraculo
    simbolico la aplica; el oraculo real (parity) la reproduce. Si divergen,
    diverge la huella y la paridad se rechaza — que es exactamente lo que se
    quiere detectar, pero nunca por una constante escrita dos veces.
    """
    n = 1
    while f"{src}.dup{n}" in world:
        n += 1
    return f"{src}.dup{n}"


def apply(world: dict[str, str], primitive: str, symbol: str) -> dict[str, str]:
    """Aplica la semantica operacional de `primitive` sobre una copia del mundo.

    El mundo de entrada no se muta (la ejecucion es pura; la evidencia exige
    poder re-derivar el estado inicial).
    """
    if primitive not in SUPPORTED:
        raise UnsupportedPrimitive(primitive)

    new = dict(world)
    src = f"{_ORIGIN}/{symbol}"

    if primitive == "ADD":
        if src in new:
            raise PreconditionFailed(f"ADD requiere ausencia y {src} ya existe")
        new[src] = content_of(symbol)
    elif primitive == "REMOVE":
        if src not in new:
            raise PreconditionFailed(f"REMOVE requiere presencia y {src} no existe")
        del new[src]
    elif primitive == "COPY":
        if src not in new:
            raise PreconditionFailed(f"COPY requiere presencia y {src} no existe")
        new[copy_destination(src, new)] = new[src]
    elif primitive == "MOVE":
        if src not in new:
            raise PreconditionFailed(f"MOVE requiere presencia y {src} no existe")
        new[f"{_DEST}/{symbol}"] = new.pop(src)
    else:
        # Inalcanzable por el guard de SUPPORTED; defensa contra edicion futura.
        raise UnsupportedPrimitive(primitive)
    return new


def run(primitive: str, symbol: str, world: dict[str, str] | None = None) -> Execution:
    """Ejecuta `primitiva(simbolo)` desde el mundo inicial canonico (o uno dado)."""
    w0 = initial_world(symbol, primitive) if world is None else dict(world)
    w1 = apply(w0, primitive, symbol)
    return Execution(
        primitive=primitive,
        symbol=symbol,
        initial_fingerprint=fingerprint(w0),
        final_fingerprint=fingerprint(w1),
        world=w1,
    )


def granularity_controls(symbol: str = "probe") -> dict[str, str]:
    """Huellas de cada primitiva sobre el mismo mundo inicial.

    Condicion de validez de la maquina: todas deben ser DISTINTAS entre si.
    Lo usa parity.run_parity (control por grupo) y tests/test_oracle_parity.py
    (control global). Si dos primitivas colapsan, la paridad medida por esta
    maquina no distingue intenciones y hay que decirlo, no ocultarlo.
    """
    return {p: run(p, symbol).final_fingerprint for p in SUPPORTED}
