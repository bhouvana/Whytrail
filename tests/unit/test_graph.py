from __future__ import annotations

import gc

from whytrail.core.graph import ProvenanceGraph
from whytrail.core.node import EdgeKind, NodeKind


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


# -- descendants(): the forward mirror of ancestors(), added after a
# Phase U counterexample sweep confirmed it's pure traversal over the
# already-existing _edges_by_source index, not a new graph concept
# (docs/adr/0012-provenance-model-boundaries.md).


def test_descendants_single_hop():
    graph = ProvenanceGraph()
    parent = graph.add_node(NodeKind.VALUE, "parent")
    child = graph.add_node(NodeKind.VALUE, "child")
    graph.add_edge(parent, child, EdgeKind.DERIVED_FROM)

    nodes, edges = graph.descendants(parent.id)
    node_ids = {n.id for n in nodes}
    assert parent.id in node_ids
    assert child.id in node_ids
    assert len(edges) == 1
    assert edges[0].source == parent.id
    assert edges[0].target == child.id


def test_descendants_fans_out_to_multiple_independent_consumers():
    """The scenario that motivated adding this: one value affecting
    several unrelated downstream consumers, answered in a single call
    instead of calling why() on each consumer separately."""
    graph = ProvenanceGraph()
    timeout = graph.add_node(NodeKind.VALUE, "config.timeout")
    http_client = graph.add_node(NodeKind.VALUE, "HTTP client config")
    retry_policy = graph.add_node(NodeKind.VALUE, "Retry policy")
    cache = graph.add_node(NodeKind.VALUE, "Cache")
    graph.add_edge(timeout, http_client, EdgeKind.DERIVED_FROM)
    graph.add_edge(timeout, retry_policy, EdgeKind.DERIVED_FROM)
    graph.add_edge(timeout, cache, EdgeKind.DERIVED_FROM)

    nodes, edges = graph.descendants(timeout.id)
    labels = {n.label for n in nodes}
    assert labels == {"config.timeout", "HTTP client config", "Retry policy", "Cache"}
    assert len(edges) == 3


def test_descendants_respects_max_depth():
    graph = ProvenanceGraph()
    a = graph.add_node(NodeKind.VALUE, "a")
    b = graph.add_node(NodeKind.VALUE, "b")
    c = graph.add_node(NodeKind.VALUE, "c")
    graph.add_edge(a, b, EdgeKind.DERIVED_FROM)
    graph.add_edge(b, c, EdgeKind.DERIVED_FROM)

    nodes, _ = graph.descendants(a.id, max_depth=1)
    node_ids = {n.id for n in nodes}
    assert a.id in node_ids
    assert b.id in node_ids
    assert c.id not in node_ids  # two hops away, beyond depth 1


def test_descendants_on_unknown_node_returns_empty():
    graph = ProvenanceGraph()
    nodes, edges = graph.descendants(999999)
    assert nodes == []
    assert edges == []


def test_descendants_is_cycle_safe():
    """Mirrors ancestors()'s cycle safety (ADR 0008 invariant 6) --
    confirmed directly here rather than assumed from ancestors()'s own
    test, since descendants() is a separate traversal, not a thin
    wrapper around it."""
    graph = ProvenanceGraph()
    a = graph.add_node(NodeKind.VALUE, "a")
    b = graph.add_node(NodeKind.VALUE, "b")
    graph.add_edge(a, b, EdgeKind.DERIVED_FROM)
    graph.add_edge(b, a, EdgeKind.DERIVED_FROM)  # cycle

    nodes, _ = graph.descendants(a.id, max_depth=50)
    assert {n.id for n in nodes} == {a.id, b.id}


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


def test_all_nodes_returns_every_node_in_insertion_order():
    graph = ProvenanceGraph()
    a = graph.add_node(NodeKind.VALUE, "a")
    b = graph.add_node(NodeKind.EXTERNAL, "b")
    assert graph.all_nodes() == [a, b]


def test_all_nodes_on_an_empty_graph_returns_empty_list():
    graph = ProvenanceGraph()
    assert graph.all_nodes() == []


def test_all_edges_returns_every_edge_in_insertion_order():
    graph = ProvenanceGraph()
    a = graph.add_node(NodeKind.VALUE, "a")
    b = graph.add_node(NodeKind.VALUE, "b")
    c = graph.add_node(NodeKind.VALUE, "c")
    e1 = graph.add_edge(a, b, EdgeKind.DERIVED_FROM)
    e2 = graph.add_edge(b, c, EdgeKind.DERIVED_FROM)
    assert graph.all_edges() == [e1, e2]


def test_all_nodes_reflects_eviction():
    graph = ProvenanceGraph(max_nodes=2)
    graph.add_node(NodeKind.VALUE, "a")
    b = graph.add_node(NodeKind.VALUE, "b")
    c = graph.add_node(NodeKind.VALUE, "c")
    assert graph.all_nodes() == [b, c]


# -- mutation-testing findings: three real gaps in eviction bookkeeping,
# none caught by the tests above, each confirmed by mutmut against a
# real mutant (see CHANGELOG.md) rather than invented speculatively.


def test_eviction_removes_index_entries_for_the_evicted_node():
    """test_eviction_drops_dangling_edges (above) only checks the
    result via ancestors(), which reads _edges_by_target -- it doesn't
    notice if _edges_by_source's entry for the evicted node was never
    actually removed (a mutation replacing the popped key with a wrong
    one survived every existing test)."""
    graph = ProvenanceGraph(max_nodes=2)
    a = graph.add_node(NodeKind.VALUE, "a")
    b = graph.add_node(NodeKind.VALUE, "b")
    graph.add_edge(a, b, EdgeKind.DERIVED_FROM)
    graph.add_node(NodeKind.VALUE, "c")
    graph.add_node(NodeKind.VALUE, "d")  # evicts a

    assert a.id not in graph._edges_by_source  # noqa: SLF001
    assert a.id not in graph._edges_by_target  # noqa: SLF001


def test_eviction_removes_dangling_edges_from_all_edges_not_just_the_index():
    """The flat self._edges list (what all_edges()/serialize.dumps()
    actually read) is maintained separately from the
    _edges_by_source/_edges_by_target indices -- ancestors()-based
    checks never notice if *this* list still contains a dangling edge,
    since ancestors() doesn't consult it at all."""
    graph = ProvenanceGraph(max_nodes=2)
    a = graph.add_node(NodeKind.VALUE, "a")
    b = graph.add_node(NodeKind.VALUE, "b")
    graph.add_edge(a, b, EdgeKind.DERIVED_FROM)
    graph.add_node(NodeKind.VALUE, "c")
    graph.add_node(NodeKind.VALUE, "d")  # evicts a

    assert all(a.id not in (e.source, e.target) for e in graph.all_edges())


def test_eviction_does_not_delete_an_object_to_node_entry_claimed_by_a_newer_node():
    """_evict_if_needed()'s cleanup must only delete _object_to_node[key]
    if it still points at the node actually being evicted -- guarding
    against the id() reuse scenario core/graph.py's own docstring
    already names (an evicted-but-still-alive object's id() could, in
    principle, be reused by a *different* object that gets its own,
    newer node before this one's finalizer fires). Simulated directly
    rather than relying on CPython's allocator to actually reuse an id()
    within a test."""
    graph = ProvenanceGraph(max_nodes=2)

    class V:
        pass

    a = V()
    graph.add_node(NodeKind.VALUE, "a", obj=a)
    # Simulate: a's id() got reused by a newer node after eviction would
    # normally have started cleaning it up.
    graph._object_to_node[id(a)] = 999999  # noqa: SLF001

    graph.add_node(NodeKind.VALUE, "b")
    graph.add_node(NodeKind.VALUE, "c")  # evicts node_a

    assert graph._object_to_node.get(id(a)) == 999999  # noqa: SLF001
