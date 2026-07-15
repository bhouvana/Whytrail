from __future__ import annotations

import gc

from whytrail.core.graph import ProvenanceGraph
from whytrail.core.node import Confidence, EdgeKind, NodeKind


def test_add_node_and_node_for():
    graph = ProvenanceGraph()
    obj = object()
    node = graph.add_node(NodeKind.VALUE, "obj", obj=obj)
    assert graph.node_for(obj) is node


def test_node_for_unknown_object_returns_none():
    graph = ProvenanceGraph()
    assert graph.node_for(object()) is None


def test_add_edge_and_ancestors_single_hop():
    graph = ProvenanceGraph()
    parent = graph.add_node(NodeKind.VALUE, "parent")
    child = graph.add_node(NodeKind.VALUE, "child")
    graph.add_edge(parent, child, EdgeKind.DERIVED_FROM)

    nodes, edges = graph.ancestors(child.id)
    node_ids = {n.id for n in nodes}
    assert parent.id in node_ids
    assert child.id in node_ids
    assert len(edges) == 1
    assert edges[0].source == parent.id
    assert edges[0].target == child.id


def test_ancestors_respects_max_depth():
    graph = ProvenanceGraph()
    a = graph.add_node(NodeKind.VALUE, "a")
    b = graph.add_node(NodeKind.VALUE, "b")
    c = graph.add_node(NodeKind.VALUE, "c")
    graph.add_edge(a, b, EdgeKind.DERIVED_FROM)
    graph.add_edge(b, c, EdgeKind.DERIVED_FROM)

    nodes, _ = graph.ancestors(c.id, max_depth=1)
    node_ids = {n.id for n in nodes}
    assert c.id in node_ids
    assert b.id in node_ids
    assert a.id not in node_ids  # two hops away, beyond depth 1


def test_ancestors_on_unknown_node_returns_empty():
    graph = ProvenanceGraph()
    nodes, edges = graph.ancestors(999999)
    assert nodes == []
    assert edges == []


def test_tombstone_on_garbage_collection():
    graph = ProvenanceGraph()

    class Boxed:
        pass

    obj = Boxed()
    node = graph.add_node(NodeKind.VALUE, "boxed", obj=obj)
    assert node.tombstoned is False

    del obj
    gc.collect()

    assert node.tombstoned is True
    assert graph.node_for(object()) is None  # sanity: lookup still safe


def test_eviction_bounds_node_count():
    graph = ProvenanceGraph(max_nodes=5)
    for i in range(20):
        graph.add_node(NodeKind.VALUE, f"n{i}")
    assert len(graph) <= 5


def test_eviction_drops_dangling_edges():
    graph = ProvenanceGraph(max_nodes=2)
    a = graph.add_node(NodeKind.VALUE, "a")
    b = graph.add_node(NodeKind.VALUE, "b")
    graph.add_edge(a, b, EdgeKind.DERIVED_FROM)
    # push a out by adding more nodes than max_nodes allows
    graph.add_node(NodeKind.VALUE, "c")
    graph.add_node(NodeKind.VALUE, "d")

    nodes, edges = graph.ancestors(b.id)
    assert all(n.id != a.id for n in nodes)
    assert all(a.id not in (e.source, e.target) for e in edges)


def test_clear_resets_state():
    graph = ProvenanceGraph()
    obj = object()
    graph.add_node(NodeKind.VALUE, "obj", obj=obj)
    graph.clear()
    assert len(graph) == 0
    assert graph.node_for(obj) is None


def test_non_weakrefable_object_does_not_raise():
    graph = ProvenanceGraph()
    # plain ints don't support weakref -- tracking one must degrade
    # gracefully, not raise (ADR §08's documented limitation).
    node = graph.add_node(NodeKind.VALUE, "42", obj=42)
    assert node is not None
    assert graph.node_for(42) is node
