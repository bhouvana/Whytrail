"""Architecture tests, not feature tests (ADR 0008).

These verify properties of the Explanation Engine itself -- that
traversal, capture, and honesty hold for *any* producer of Node/Edge
data, not just the ones that happen to exist today (exceptions,
tracked values, whytrail.config). A new producer module should never
need a change here to keep passing.
"""

from __future__ import annotations

import whytrail
import whytrail.config
from whytrail.core.graph import ProvenanceGraph
from whytrail.core.node import EdgeKind, NodeKind


def test_a_new_producer_needs_no_engine_change():
    """Simulates a producer the engine has never seen -- a "workflow"
    domain -- using only ProvenanceGraph's public add_node()/add_edge()
    API, the same one whytrail.config and whytrail.propagation already
    use. If this test needed a change to core/graph.py or __init__.py
    to pass, the engine would not actually be producer-agnostic."""
    graph = ProvenanceGraph()
    result = ["report sent"]  # any identity-bearing object works
    trigger = graph.add_node(NodeKind.EXTERNAL, "workflow trigger: nightly cron")
    step = graph.add_node(NodeKind.VALUE, "step 'send_report' result", obj=result)
    graph.add_edge(trigger, step, EdgeKind.CAUSED_BY)

    with whytrail.trace(graph=graph):
        explanation = whytrail.why(result)

    assert explanation.known
    descriptions = " ".join(s.description for s in explanation.steps)
    assert "workflow trigger" in descriptions
    assert "send_report" in descriptions


def test_mixed_chain_across_two_real_producers(monkeypatch):
    """config (an EXTERNAL producer) feeding a value that whytrail.track()
    (the generic VALUE producer) then derives from -- two independently
    written modules, neither aware of the other, meeting only through
    the shared graph API."""
    monkeypatch.setenv("WHYTRAIL_TEST_KEY", "10")
    with whytrail.trace():
        raw = whytrail.config.env("WHYTRAIL_TEST_KEY", cast=int)
        doubled = whytrail.track(raw * 2, derived_from=raw, label="doubled")

    explanation = whytrail.why(doubled)
    descriptions = [s.description for s in explanation.steps]
    joined = " ".join(descriptions)
    assert "environment variable 'WHYTRAIL_TEST_KEY'" in joined
    assert "doubled" in joined
    env_index = next(i for i, d in enumerate(descriptions) if "environment variable" in d)
    doubled_index = next(i for i, d in enumerate(descriptions) if "doubled" in d)
    assert env_index < doubled_index  # root cause (the env var) comes first


def test_cycle_in_the_graph_does_not_hang_or_duplicate_nodes():
    graph = ProvenanceGraph()
    a = graph.add_node(NodeKind.VALUE, "a")
    b = graph.add_node(NodeKind.VALUE, "b")
    c = graph.add_node(NodeKind.VALUE, "c")
    graph.add_edge(a, b, EdgeKind.DERIVED_FROM)
    graph.add_edge(b, c, EdgeKind.DERIVED_FROM)
    graph.add_edge(c, a, EdgeKind.DERIVED_FROM)  # cycle: a -> b -> c -> a

    nodes, _ = graph.ancestors(c.id, max_depth=50)
    ids = [n.id for n in nodes]
    assert len(ids) == len(set(ids))  # no node visited twice
    assert {a.id, b.id, c.id} == set(ids)


def test_traversal_is_deterministic_for_a_fixed_graph():
    graph = ProvenanceGraph()
    a = graph.add_node(NodeKind.VALUE, "a")
    b = graph.add_node(NodeKind.VALUE, "b")
    graph.add_edge(a, b, EdgeKind.DERIVED_FROM)

    first_nodes, first_edges = graph.ancestors(b.id)
    second_nodes, second_edges = graph.ancestors(b.id)
    assert [n.id for n in first_nodes] == [n.id for n in second_nodes]
    assert [(e.source, e.target) for e in first_edges] == [
        (e.source, e.target) for e in second_edges
    ]


def test_unknown_stays_honest_for_a_never_tracked_producer_shaped_object():
    """Not just "an untracked int is unknown" (already covered
    elsewhere) -- a user-defined type shaped like a plausible future
    producer's payload gets the same honest answer, with no special
    casing by type anywhere in the resolution path."""

    class WorkflowRun:
        pass

    explanation = whytrail.why(WorkflowRun())
    assert explanation.known is False
    assert explanation.tracked is False


def test_tier1_does_not_consult_the_graph_even_for_a_graph_tracked_exception():
    """A real boundary found during the Phase F audit (ADR 0008):
    why() on a BaseException always resolves through Tier 1 (the
    traceback walk) and never reaches the provenance graph, even if
    that same exception object was separately given graph provenance.
    This is not a bug -- it's ADR 0001's two-tier design -- but it must
    stay true on purpose, not by accident, so it gets a regression
    test of its own rather than being an unstated assumption."""
    with whytrail.trace():
        exc = ValueError("boom")
        whytrail.track(exc, label="a graph-tracked exception object")
        try:
            raise exc
        except ValueError as caught:
            error = caught

    explanation = whytrail.why(error)
    assert "boom" in explanation.text
    assert "a graph-tracked exception object" not in explanation.text
