"""Graph serialization and replay (ADR §12, §14 -- v2.0).

A JSON-lines event log: one line per node, one line per edge, in the
order they were recorded. Deliberately simple -- this is meant for
snapshot()/replay() and offline inspection, not a wire protocol (that
question is deferred to v3.0's cross-process propagation work, which
is a different problem: propagating a *live* trace context, not
persisting a *finished* graph).

Format-versioned since whytrail 0.3 (a real gap found auditing this
file, not a speculative feature): snapshot()/restore() were already
public API with no way to detect a future, incompatible format change
at load time -- a renamed or removed Node/Edge field would have
produced a confusing KeyError deep in _restore_node()/_restore_edge()
(or worse, silently wrong data) instead of a clear "this snapshot is
from a newer whytrail" error. A leading manifest line carries the
version; snapshots written before this change have no such line and
still load exactly as before -- this is forward insurance, not a
breaking change to the existing format.
"""

from __future__ import annotations

import json
import typing as t

from .graph import ProvenanceGraph
from .node import Edge, EdgeKind, Node, NodeKind

SNAPSHOT_FORMAT_VERSION = 1


class SnapshotVersionError(ValueError):
    """Raised by loads()/load() when a snapshot's format version is
    newer than this whytrail version knows how to read. Not raised for
    snapshots with no version line at all -- those predate this check
    and are still the one format every whytrail version to date
    actually writes."""


def dumps(graph: ProvenanceGraph) -> str:
    lines = [json.dumps({"type": "whytrail_snapshot", "version": SNAPSHOT_FORMAT_VERSION})]
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
    metadata intact.

    Raises SnapshotVersionError if the snapshot declares a format
    version newer than this whytrail understands, rather than failing
    partway through with a confusing KeyError or silently dropping
    data it doesn't recognize.
    """
    graph = ProvenanceGraph()
    for line in data.splitlines():
        line = line.strip()
        if not line:
            continue
        payload = json.loads(line)
        payload_type = payload["type"]
        if payload_type == "whytrail_snapshot":
            version = payload.get("version", 1)
            if version > SNAPSHOT_FORMAT_VERSION:
                raise SnapshotVersionError(
                    f"this snapshot was written in format version {version}, but this "
                    f"version of whytrail only understands up to version "
                    f"{SNAPSHOT_FORMAT_VERSION} -- upgrade whytrail to read it"
                )
            continue
        if payload_type == "node":
            _restore_node(graph, payload)
        elif payload_type == "edge":
            _restore_edge(graph, payload)
        else:
            # Real bug, found by a negative test: this docstring already
            # claimed loads() doesn't "silently drop data it doesn't
            # recognize," but until this fix, any line whose "type"
            # wasn't exactly "whytrail_snapshot"/"node"/"edge" fell
            # through every branch and was dropped without a trace --
            # the opposite of what's documented, and the opposite of
            # the version-manifest check just above, which raises
            # loudly rather than ignoring what it doesn't understand.
            raise ValueError(f"unrecognized snapshot line type {payload_type!r} -- this snapshot may be corrupted")
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
    # tombstoned=True unconditionally, regardless of payload["tombstoned"]:
    # a replayed graph never holds live object references either way, so
    # every restored node is honestly a tombstone. Real, confirmed
    # consequence (found by a stateful property test, not anticipated):
    # dumps(live_graph) and dumps(loads(dumps(live_graph))) are not
    # byte-identical whenever the live graph still has a non-tombstoned
    # node -- serialize/deserialize round-tripping is only idempotent
    # starting from the *second* restore onward, once every node is
    # already tombstoned either way. Not a bug to fix: the alternative
    # (trusting payload["tombstoned"] as-is) would let a restored graph
    # claim a live reference it doesn't have.
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
