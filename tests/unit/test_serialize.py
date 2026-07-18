from __future__ import annotations

import json

import pytest

from whytrail.core import serialize
from whytrail.core.graph import ProvenanceGraph
from whytrail.core.node import Confidence, EdgeKind, NodeKind


def _small_graph() -> ProvenanceGraph:
    graph = ProvenanceGraph()
    parent = graph.add_node(NodeKind.VALUE, "raw", metadata={"source": "csv"})
    child = graph.add_node(NodeKind.VALUE, "parsed")
    graph.add_edge(parent, child, EdgeKind.DERIVED_FROM, confidence=Confidence.EXPLICIT.value)
    return graph


def test_round_trip_preserves_nodes_and_edges():
    graph = _small_graph()
    restored = serialize.loads(serialize.dumps(graph))

    original_labels = sorted(n.label for n in graph._nodes.values())  # noqa: SLF001
    restored_labels = sorted(n.label for n in restored._nodes.values())  # noqa: SLF001
    assert original_labels == restored_labels

    original_edges = sorted((e.source, e.target, e.kind.value) for e in graph._edges)  # noqa: SLF001
    restored_edges = sorted((e.source, e.target, e.kind.value) for e in restored._edges)  # noqa: SLF001
    assert original_edges == restored_edges


def test_round_trip_preserves_every_node_and_edge_field():
    """Mutation-testing finding: the test above only checks node labels
    and (source, target, kind) edge tuples -- it never noticed several
    real mutants that swapped a payload.get("field") lookup for
    payload.get(None) in _restore_node()/_restore_edge() (which always
    returns the default, silently dropping that field on every restore).
    Every field gets checked here specifically because of that."""
    graph = ProvenanceGraph()
    node = graph.add_node(
        NodeKind.EXTERNAL,
        "labeled",
        location="file.py:12, in func",
        thread="Thread-7",
        metadata={"key": "value"},
    )
    other = graph.add_node(NodeKind.VALUE, "other")
    graph.add_edge(node, other, EdgeKind.CAUSED_BY, confidence=Confidence.INFERRED.value, note="a real note")

    restored = serialize.loads(serialize.dumps(graph))

    restored_node = restored.get(node.id)
    assert restored_node is not None
    assert restored_node.kind == NodeKind.EXTERNAL
    assert restored_node.label == "labeled"
    assert restored_node.location == "file.py:12, in func"
    assert restored_node.thread == "Thread-7"
    assert restored_node.metadata == {"key": "value"}

    restored_edge = next(e for e in restored.all_edges() if e.source == node.id)
    assert restored_edge.target == other.id
    assert restored_edge.kind == EdgeKind.CAUSED_BY
    assert restored_edge.confidence == Confidence.INFERRED.value
    assert restored_edge.note == "a real note"
    assert restored_node.timestamp == node.timestamp


def test_restore_edge_defaults_confidence_when_the_key_is_absent():
    """Mutation-testing finding: the field-by-field test above always
    supplies a confidence value, so it never exercises _restore_edge()'s
    *default* -- payload.get("confidence", 1.0) -- specifically. A
    mutant changing that default to None survived every other test."""
    payload = {"type": "edge", "source": 1, "target": 2, "kind": "derived_from"}
    data = _MANIFEST + "\n" + json.dumps(payload)
    restored = serialize.loads(data)
    edge = restored.all_edges()[0]
    assert edge.confidence == 1.0


def test_json_safe_actually_falls_back_to_repr_for_unserializable_metadata():
    """Mutation-testing finding: a mutant replacing the value being
    probed (json.dumps(value)) with a constant that's always
    serializable (json.dumps(None)) survived -- because no existing
    test ever put a genuinely non-JSON-serializable object in a node's
    metadata to prove the repr() fallback path is actually reachable."""
    graph = ProvenanceGraph()
    graph.add_node(NodeKind.VALUE, "n", metadata={"unserializable": object()})
    data = serialize.dumps(graph)  # must not raise
    restored = serialize.loads(data)
    node = restored.all_nodes()[0]
    assert node.metadata["unserializable"].startswith("<object object at")


_MANIFEST = json.dumps({"type": "whytrail_snapshot", "version": serialize.SNAPSHOT_FORMAT_VERSION})


def test_restored_nodes_are_tombstoned():
    graph = _small_graph()
    restored = serialize.loads(serialize.dumps(graph))
    assert all(n.tombstoned for n in restored._nodes.values())  # noqa: SLF001


def test_dumps_writes_a_version_manifest_line_first():
    graph = _small_graph()
    first_line = serialize.dumps(graph).splitlines()[0]
    manifest = json.loads(first_line)
    assert manifest == {"type": "whytrail_snapshot", "version": serialize.SNAPSHOT_FORMAT_VERSION}


def test_a_pre_versioning_snapshot_with_no_manifest_line_still_loads():
    """Every snapshot taken with whytrail before this change has no
    manifest line at all -- this is the actual backward-compatibility
    contract, not just "the new format loads.\""""
    graph = _small_graph()
    legacy_data = "\n".join(
        line
        for line in serialize.dumps(graph).splitlines()
        if '"type": "node"' in line or '"type": "edge"' in line
    )
    restored = serialize.loads(legacy_data)
    assert len(restored) == 2


def test_a_snapshot_from_a_newer_format_version_raises_a_clear_error():
    payload = json.dumps({"type": "whytrail_snapshot", "version": serialize.SNAPSHOT_FORMAT_VERSION + 1})
    with pytest.raises(serialize.SnapshotVersionError, match="upgrade whytrail"):
        serialize.loads(payload)


def test_a_snapshot_at_the_current_version_loads_fine():
    graph = _small_graph()
    # dumps() already writes the current version -- this just makes the
    # "not >, so no raise" branch explicit as its own test.
    restored = serialize.loads(serialize.dumps(graph))
    assert len(restored) == 2


def test_snapshot_version_error_is_reachable_from_top_level_whytrail():
    """Co-located with snapshot()/restore() (0.3, a pre-1.0 consistency
    fix): whytrail.config.ConfigError already lived next to the
    function that raises it, but this didn't -- a user catching a
    version mismatch had to know it lived two levels deep in
    whytrail.core.serialize. whytrail.SnapshotVersionError must be the
    exact same class, not a copy, so `except whytrail.SnapshotVersionError`
    and `except serialize.SnapshotVersionError` both actually catch the
    same real exception."""
    import whytrail

    assert whytrail.SnapshotVersionError is serialize.SnapshotVersionError
    payload = json.dumps({"type": "whytrail_snapshot", "version": serialize.SNAPSHOT_FORMAT_VERSION + 1})
    with pytest.raises(whytrail.SnapshotVersionError):
        whytrail.restore(payload)
