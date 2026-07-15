from __future__ import annotations

from whytrail.core.node import Confidence, Edge, EdgeKind, Node, NodeKind


def test_node_create_assigns_unique_ids():
    a = Node.create(NodeKind.VALUE, "a")
    b = Node.create(NodeKind.VALUE, "b")
    assert a.id != b.id


def test_node_defaults():
    node = Node.create(NodeKind.VALUE, "x")
    assert node.location is None
    assert node.metadata == {}
    assert node.tombstoned is False


def test_node_tombstone_drops_payload_keeps_shell():
    node = Node.create(NodeKind.VALUE, "x", metadata={"secret": "payload"})
    node.tombstone()
    assert node.tombstoned is True
    assert "secret" not in node.metadata
    assert "tombstoned_at" in node.metadata
    # identity/kind/label survive -- that's the point of a tombstone
    assert node.kind is NodeKind.VALUE
    assert node.label == "x"


def test_confidence_ordering():
    assert Confidence.EXPLICIT.value > Confidence.INFERRED.value
    assert Confidence.INFERRED.value > Confidence.HEURISTIC.value
    assert Confidence.HEURISTIC.value > Confidence.UNKNOWN.value


def test_edge_defaults_to_explicit_confidence():
    edge = Edge(source=1, target=2, kind=EdgeKind.DERIVED_FROM)
    assert edge.confidence == Confidence.EXPLICIT.value
