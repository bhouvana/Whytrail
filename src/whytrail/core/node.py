"""Graph primitives underlying the provenance model (ADR §12)."""

from __future__ import annotations

import dataclasses
import enum
import itertools
import time
import typing as t

_id_counter = itertools.count(1)


class NodeKind(enum.Enum):
    VALUE = "value"
    CALL = "call"
    EXCEPTION = "exception"
    MUTATION = "mutation"
    EXTERNAL = "external"
    IMPORT = "import"


class EdgeKind(enum.Enum):
    DERIVED_FROM = "derived_from"
    RAISED_FROM = "raised_from"
    CAUSED_BY = "caused_by"
    OCCURRED_DURING = "occurred_during"
    MUTATED_BY = "mutated_by"
    PASSED_TO = "passed_to"


class Confidence(float, enum.Enum):
    """ADR §11 — every edge carries an honest confidence, never a guess
    presented as fact."""

    EXPLICIT = 1.0
    INFERRED = 0.7
    HEURISTIC = 0.4
    UNKNOWN = 0.0


@dataclasses.dataclass(slots=True)
class Node:
    id: int
    kind: NodeKind
    label: str
    location: str | None = None
    timestamp: float = dataclasses.field(default_factory=time.time)
    thread: str | None = None
    metadata: dict[str, t.Any] = dataclasses.field(default_factory=dict)
    tombstoned: bool = False

    @classmethod
    def create(
        cls,
        kind: NodeKind,
        label: str,
        *,
        location: str | None = None,
        thread: str | None = None,
        metadata: dict[str, t.Any] | None = None,
    ) -> "Node":
        return cls(
            id=next(_id_counter),
            kind=kind,
            label=label,
            location=location,
            thread=thread,
            metadata=metadata or {},
        )

    def tombstone(self) -> None:
        """Object was garbage-collected: drop payload, keep metadata shell."""
        self.tombstoned = True
        self.metadata = {"tombstoned_at": time.time()}


@dataclasses.dataclass(slots=True)
class Edge:
    source: int
    target: int
    kind: EdgeKind
    confidence: float = Confidence.EXPLICIT.value
    note: str | None = None
