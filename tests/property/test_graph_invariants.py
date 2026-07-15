from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from whytrail.core.graph import ProvenanceGraph
from whytrail.core.node import EdgeKind, NodeKind

_MAX_NODES = 25


@given(count=st.integers(min_value=0, max_value=200))
@settings(max_examples=25)
def test_node_count_never_exceeds_max_nodes(count: int):
    graph = ProvenanceGraph(max_nodes=_MAX_NODES)
    for i in range(count):
        graph.add_node(NodeKind.VALUE, f"n{i}")
    assert len(graph) <= _MAX_NODES


@given(
    edge_pairs=st.lists(
        st.tuples(st.integers(min_value=0, max_value=9), st.integers(min_value=0, max_value=9)),
        max_size=60,
    )
)
@settings(max_examples=25)
def test_ancestors_terminates_even_with_cycles(edge_pairs: list[tuple[int, int]]):
    """A provenance graph is meant to be acyclic, but ancestors() must
    never hang even if something upstream manages to introduce a
    cycle -- correctness here shouldn't depend on the invariant always
    holding."""
    graph = ProvenanceGraph(max_nodes=1000)
    nodes = [graph.add_node(NodeKind.VALUE, str(i)) for i in range(10)]
    for src, dst in edge_pairs:
        graph.add_edge(nodes[src], nodes[dst], EdgeKind.DERIVED_FROM)

    # must return, not hang, regardless of cycles in edge_pairs
    result_nodes, result_edges = graph.ancestors(nodes[0].id, max_depth=50)
    assert isinstance(result_nodes, list)
    assert isinstance(result_edges, list)
    assert len(result_nodes) <= 10  # can't discover more nodes than exist


@given(st.lists(st.integers(), max_size=50, unique=True))
@settings(max_examples=25)
def test_every_added_node_is_findable_by_identity_until_evicted(values: list[int]):
    graph = ProvenanceGraph(max_nodes=1000)
    boxed = [[v] for v in values]  # lists are weak-referenceable, unlike plain ints
    tracked_nodes = {}
    for obj in boxed:
        node = graph.add_node(NodeKind.VALUE, repr(obj), obj=obj)
        tracked_nodes[id(obj)] = node

    for obj in boxed:
        found = graph.node_for(obj)
        assert found is tracked_nodes[id(obj)]
