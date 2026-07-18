"""Long-running soak test for graph eviction and internal-structure
cleanup at scale (docs/roadmap.md Phase G: `core/graph.py`'s FIFO
eviction at `DEFAULT_MAX_NODES` is named tech debt with "zero evidence
anyone has hit it" -- this is that evidence, gathered directly).

Bounded to what's real and CI-reasonable: tens of thousands of
`track()` calls (not literally millions), enough to force eviction many
times over within a few seconds, not a multi-hour run. The property
that matters is "does bounded retention actually stay bounded," which
tens of thousands of iterations already answers -- more iterations
would find the same answer slower, not a different one.

This is also the test that found a real bug: `_object_to_node` and
`_finalizers` were never cleaned up on eviction (only on the tracked
object's own garbage collection), so either dict grew unboundedly
whenever an evicted node's object was still alive -- exactly the
"caller keeps old tracked objects around" shape a long-running process
naturally has. Fixed in `core/graph.py`'s `_evict_if_needed()`.
"""

from __future__ import annotations

import gc

from whytrail.core.graph import ProvenanceGraph
from whytrail.core.node import NodeKind

N_TRACKED = 50_000
MAX_NODES = 1_000


class _Payload:
    """Weakref-friendly, minimal footprint. Real gotcha found writing
    this test, not anticipated: `__slots__ = ("n",)` alone makes an
    object *not* weakly-referenceable at all (Python only adds a
    `__weakref__` slot automatically for a class with no `__slots__`)
    -- `weakref.finalize()` would silently raise `TypeError` for every
    instance, caught by `core/graph.py`'s own `except TypeError: pass`,
    so nothing would ever get tombstoned no matter how much `gc.collect()`
    ran, defeating the very test this class exists for. `__weakref__`
    must be listed explicitly to keep both the memory-efficiency intent
    and weakref support."""

    __slots__ = ("n", "__weakref__")

    def __init__(self, n: int) -> None:
        self.n = n


def test_eviction_bounds_the_node_count_at_scale():
    graph = ProvenanceGraph(max_nodes=MAX_NODES)
    for i in range(N_TRACKED):
        graph.add_node(NodeKind.VALUE, f"v{i}", obj=_Payload(i))
        # Not kept alive here -- this pass exercises eviction combined
        # with real garbage collection happening concurrently, the more
        # common real-world shape (most tracked values go out of scope
        # naturally rather than being kept forever).
    assert len(graph) <= MAX_NODES


def test_eviction_bounds_object_to_node_and_finalizers_when_objects_stay_alive():
    """The actual bug this soak test found: when evicted objects are
    still alive (kept by the caller, e.g. in a cache or a long-lived
    list), `_object_to_node`/`_finalizers` must still stay bounded --
    eviction, not garbage collection, is what's supposed to cap them."""
    graph = ProvenanceGraph(max_nodes=MAX_NODES)
    kept_alive = []
    for i in range(N_TRACKED):
        obj = _Payload(i)
        kept_alive.append(obj)
        graph.add_node(NodeKind.VALUE, f"v{i}", obj=obj)

    assert len(graph) == MAX_NODES
    assert len(graph._object_to_node) == MAX_NODES, (
        f"_object_to_node grew to {len(graph._object_to_node)}, expected {MAX_NODES} -- "
        "eviction should remove the reverse-mapping entry for an evicted node, "
        "not just the node itself"
    )
    assert len(graph._node_to_object_key) == MAX_NODES
    assert len(graph._finalizers) == MAX_NODES


def test_weakref_cleanup_still_tombstones_after_real_garbage_collection():
    graph = ProvenanceGraph(max_nodes=MAX_NODES)
    node_ids = []
    for i in range(200):
        obj = _Payload(i)
        node = graph.add_node(NodeKind.VALUE, f"v{i}", obj=obj)
        node_ids.append(node.id)
        del obj  # no strong reference survives this iteration

    gc.collect()

    tombstoned_count = sum(1 for nid in node_ids if graph.get(nid) is not None and graph.get(nid).tombstoned)
    # Every one of the 200 should have been garbage collected and
    # tombstoned -- none were evicted (200 < MAX_NODES=1000) and none
    # were kept alive.
    assert tombstoned_count == 200


def test_repeated_track_snapshot_cycles_do_not_leak_across_thousands_of_rounds():
    """A bounded proxy for "millions of iterations": repeatedly
    track+snapshot+discard and confirm the graph itself never exceeds
    its cap across many rounds, not just within one."""
    from whytrail.core import serialize

    graph = ProvenanceGraph(max_nodes=MAX_NODES)
    for round_ in range(500):
        for i in range(20):
            graph.add_node(NodeKind.VALUE, f"round{round_}-v{i}", obj=_Payload(i))
        _ = serialize.dumps(graph)  # exercise the real snapshot path each round
        assert len(graph) <= MAX_NODES
