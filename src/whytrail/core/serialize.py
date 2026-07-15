"""Graph serialization and replay (ADR §12, §14 -- v2.0).

A JSON-lines event log: one line per node, one line per edge, in the
order they were recorded. Deliberately simple -- this is meant for
snapshot()/replay() and offline inspection, not a wire protocol (that
question is deferred to v3.0's cross-process propagation work, which
is a different problem: propagating a *live* trace context, not
persisting a *finished* graph).
"""

from __future__ import annotations

import json
import typing as t

from .graph import ProvenanceGraph
from .node import Edge, EdgeKind, Node, NodeKind


def dumps(graph: ProvenanceGraph) -> str:
    lines = []
    for node in graph._nodes.values():  # noqa: SLF001 - serialize is core-internal, not a plugin
        lines.append(json.dumps(_node_to_dict(node)))
    for edge in graph._edges:  # noqa: SLF001
        lines.append(json.dumps(_edge_to_dict(edge)))
    return "\n".join(lines)


def dump(graph: ProvenanceGraph, fp: t.TextIO) -> None:
    fp.write(dumps(graph))


def loads(data: str) -> ProvenanceGraph:
    """Rebuild a read-only replay graph from a snapshot. Nodes are
    reconstructed without their original objects -- a snapshot outlives
    the process that made it, so there is nothing to hold a weakref
    to; every replayed node behaves like a tombstone with its
    metadata intact."""
    graph = ProvenanceGraph()
    for line in data.splitlines():
        line = line.strip()
        if not line:
            continue
        payload = json.loads(line)
        if payload["type"] == "node":
            _restore_node(graph, payload)
        elif payload["type"] == "edge":
            _restore_edge(graph, payload)
    return graph


def load(fp: t.TextIO) -> ProvenanceGraph:
    return loads(fp.read())


def _node_to_dict(node: Node) -> dict[str, t.Any]:
    return {
        "type": "node",
        "id": node.id,
        "kind": node.kind.value,
        "label": node.label,
        "location": node.location,
        "timestamp": node.timestamp,
        "thread": node.thread,
        "tombstoned": node.tombstoned,
        "metadata": _json_safe(node.metadata),
    }


def _edge_to_dict(edge: Edge) -> dict[str, t.Any]:
    return {
        "type": "edge",
        "source": edge.source,
        "target": edge.target,
        "kind": edge.kind.value,
        "confidence": edge.confidence,
        "note": edge.note,
    }


def _restore_node(graph: ProvenanceGraph, payload: dict[str, t.Any]) -> None:
    node = Node(
        id=payload["id"],
        kind=NodeKind(payload["kind"]),
        label=payload["label"],
        location=payload.get("location"),
        timestamp=payload.get("timestamp", 0.0),
        thread=payload.get("thread"),
        metadata=payload.get("metadata", {}),
        tombstoned=True,  # replayed graphs never hold live object references
    )
    graph._nodes[node.id] = node  # noqa: SLF001


def _restore_edge(graph: ProvenanceGraph, payload: dict[str, t.Any]) -> None:
    edge = Edge(
        source=payload["source"],
        target=payload["target"],
        kind=EdgeKind(payload["kind"]),
        confidence=payload.get("confidence", 1.0),
        note=payload.get("note"),
    )
    graph._edges.append(edge)  # noqa: SLF001
    graph._edges_by_target[edge.target].append(edge)  # noqa: SLF001
    graph._edges_by_source[edge.source].append(edge)  # noqa: SLF001


def _json_safe(metadata: dict[str, t.Any]) -> dict[str, t.Any]:
    safe: dict[str, t.Any] = {}
    for key, value in metadata.items():
        try:
            json.dumps(value)
        except TypeError:
            safe[key] = repr(value)
        else:
            safe[key] = value
    return safe
