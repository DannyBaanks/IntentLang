"""Language-independent representation of sentence meaning.

Meaning IR is separate from executable Intent IR: it describes prose safely
without turning arbitrary text into an action.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

MEANING_SCHEMA = "meaning/1"
MEANING_STATUSES = ("RESOLVED", "AMBIGUOUS", "UNKNOWN", "INCOMPLETE")


def _features(value: Mapping[str, Any] | tuple[tuple[str, Any], ...] | None) -> tuple[tuple[str, str], ...]:
    if value is None:
        return ()
    items = value.items() if isinstance(value, Mapping) else value
    return tuple(sorted((str(key), str(item)) for key, item in items))


def _features_dict(value: tuple[tuple[str, str], ...]) -> dict[str, str]:
    return dict(value)


@dataclass(frozen=True, slots=True)
class MeaningEntity:
    id: str
    concept: str
    features: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "features", _features(self.features))


@dataclass(frozen=True, slots=True)
class MeaningRole:
    name: str
    entity: str | None = None
    concept: str | None = None
    features: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "features", _features(self.features))


@dataclass(frozen=True, slots=True)
class MeaningProvenance:
    surface: str
    language: str
    semantic_backend: str
    confidence: str
    mode: str
    source_hash: str


@dataclass(frozen=True, slots=True)
class Meaning:
    predicate: str | None
    roles: tuple[MeaningRole, ...]
    polarity: str
    tense: str | None
    aspect: str | None
    modality: str | None
    entities: tuple[MeaningEntity, ...]
    provenance: MeaningProvenance
    schema: str = MEANING_SCHEMA
    status: str = "RESOLVED"

    def __post_init__(self) -> None:
        if self.schema != MEANING_SCHEMA:
            raise ValueError(f"schema must be {MEANING_SCHEMA}")
        if self.status not in MEANING_STATUSES:
            raise ValueError(f"invalid status: {self.status}")
        if not isinstance(self.roles, tuple):
            object.__setattr__(self, "roles", tuple(self.roles))
        if not isinstance(self.entities, tuple):
            object.__setattr__(self, "entities", tuple(self.entities))

    def key(self) -> tuple:
        """Semantic identity, excluding surface, language, and provenance."""
        entities = {entity.id: entity for entity in self.entities}
        role_key = tuple(sorted(
            (
                role.name,
                entities[role.entity].concept if role.entity in entities else role.concept,
                role.features,
            )
            for role in self.roles
        ))
        entity_key = tuple(sorted((entity.concept, entity.features) for entity in self.entities))
        return (
            self.predicate, role_key, entity_key, self.polarity,
            self.tense, self.aspect, self.modality,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "status": self.status,
            "predicate": self.predicate,
            "roles": [
                {
                    "name": role.name,
                    "entity": role.entity,
                    "concept": role.concept,
                    "features": _features_dict(role.features),
                }
                for role in self.roles
            ],
            "polarity": self.polarity,
            "tense": self.tense,
            "aspect": self.aspect,
            "modality": self.modality,
            "entities": [
                {"id": entity.id, "concept": entity.concept, "features": _features_dict(entity.features)}
                for entity in self.entities
            ],
            "provenance": asdict(self.provenance),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Meaning:
        validate_meaning(data)
        return cls(
            schema=data["schema"], status=data["status"], predicate=data["predicate"],
            roles=tuple(
                MeaningRole(row["name"], row.get("entity"), row.get("concept"), _features(row.get("features")))
                for row in data["roles"]
            ),
            polarity=data["polarity"], tense=data["tense"], aspect=data["aspect"],
            modality=data["modality"],
            entities=tuple(
                MeaningEntity(row["id"], row["concept"], _features(row.get("features")))
                for row in data["entities"]
            ),
            provenance=MeaningProvenance(**data["provenance"]),
        )


def validate_meaning(data: Mapping[str, Any]) -> None:
    if "predicate" not in data:
        raise ValueError("missing field: predicate")
    required = {
        "schema", "status", "predicate", "roles", "polarity", "tense", "aspect",
        "modality", "entities", "provenance",
    }
    missing = sorted(required - data.keys())
    if missing:
        raise ValueError(f"missing field: {missing[0]}")
    if data["schema"] != MEANING_SCHEMA:
        raise ValueError(f"schema must be {MEANING_SCHEMA}")
    if data["status"] not in MEANING_STATUSES:
        raise ValueError(f"invalid status: {data['status']}")
    if data["status"] == "RESOLVED" and not data["predicate"]:
        raise ValueError("predicate is required for RESOLVED meaning")
    if not isinstance(data["roles"], list):
        raise ValueError("roles must be a list")
    if not isinstance(data["entities"], list):
        raise ValueError("entities must be a list")
    for field in ("surface", "language", "semantic_backend", "confidence", "mode", "source_hash"):
        if field not in data["provenance"]:
            raise ValueError(f"provenance.{field} is required")


__all__ = [
    "MEANING_SCHEMA", "MEANING_STATUSES", "Meaning", "MeaningEntity",
    "MeaningProvenance", "MeaningRole", "validate_meaning",
]
