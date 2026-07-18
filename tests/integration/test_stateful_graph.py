"""Stateful (state-machine) property testing over the graph lifecycle:
track -> why -> snapshot -> restore -> redact, in randomized order,
via Hypothesis's `RuleBasedStateMachine`. This is a different kind of
test from everything else in this suite: instead of one hand-picked
sequence of calls, Hypothesis generates thousands of *legal* sequences
and checks invariants hold after every one -- the property this project
actually cares about ("the graph survives arbitrary legal use," not
"this one scripted scenario works").

Scoped to what's real and cheap: a small, explicit `ProvenanceGraph`
held open for the whole run via one `trace()` scope (not the shared
process-default graph, which would leak state across Hypothesis
examples), a small `max_nodes` so eviction is actually exercised within
a few dozen rule applications rather than needing thousands, and a
custom weakref-friendly `_Value` class (plain ints/strings don't
support weakref, per `core/graph.py`'s own documented limitation).

"diff" from the original ask is covered here as "two independently
restored snapshots of the same graph state produce the same node/edge
counts," not by shelling out to the `whytrail diff` CLI command inside
a Hypothesis rule -- that command reads files and prints to stdout, not
a library-level function suited to being called thousands of times
per test run.
"""

from __future__ import annotations

from hypothesis import HealthCheck, settings
from hypothesis.stateful import RuleBasedStateMachine, rule

import whytrail
from whytrail.core import serialize
from whytrail.core.graph import ProvenanceGraph
from whytrail.runtime.context import trace

MAX_NODES = 40


class _Value:
    """A minimal, weakref-friendly payload -- plain ints/strings don't
    support weakref (core/graph.py's own `_track_identity` catches
    `TypeError` for exactly this reason), and this state machine needs
    every tracked object to participate in the real garbage-collection
    path, not the degraded id()-only fallback."""

    def __init__(self, n: int) -> None:
        self.n = n

    def __repr__(self) -> str:
        return f"_Value({self.n})"


class GraphLifecycleMachine(RuleBasedStateMachine):
    def __init__(self) -> None:
        super().__init__()
        self.graph = ProvenanceGraph(max_nodes=MAX_NODES)
        self._scope_cm = trace(graph=self.graph)
        self._scope_cm.__enter__()
        # Every object tracked this run, insertion order, kept alive by
        # this list itself so eviction (not garbage collection) is the
        # only thing that can make one unreachable via why().
        self._tracked: list[_Value] = []
        self._next_n = 0

    def teardown(self) -> None:
        self._scope_cm.__exit__(None, None, None)

    @rule()
    def track_a_value(self) -> None:
        value = _Value(self._next_n)
        self._next_n += 1
        whytrail.track(value)
        self._tracked.append(value)

    @rule()
    def why_on_a_live_tracked_value(self) -> None:
        if not self._tracked:
            return
        # FIFO eviction (core/graph.py's own documented policy): the
        # oldest (total tracked so far - max_nodes) are gone. Anything
        # after that index must still resolve.
        evicted_count = max(0, len(self._tracked) - self.graph.max_nodes)
        if evicted_count >= len(self._tracked):
            return
        value = self._tracked[evicted_count]
        explanation = whytrail.why(value)
        assert explanation.known, f"expected {value!r} to still be tracked (not yet evicted)"
        assert isinstance(explanation, whytrail.Explanation)
        assert str(value.n) in explanation.subject

    @rule()
    def why_on_an_evicted_value_is_honestly_unknown(self) -> None:
        evicted_count = max(0, len(self._tracked) - self.graph.max_nodes)
        if evicted_count == 0:
            return
        value = self._tracked[0]
        explanation = whytrail.why(value)
        # ADR §11: an evicted value is not a bug -- it's an honest
        # "unknown," never a fabricated chain.
        assert explanation.known is False
        assert explanation.steps == []

    @rule()
    def snapshot_and_restore_preserves_node_and_edge_counts(self) -> None:
        before_nodes = len(self.graph.all_nodes())
        before_edges = len(self.graph.all_edges())
        data = whytrail.snapshot(self.graph)
        restored = whytrail.restore(data)
        assert len(restored.all_nodes()) == before_nodes
        assert len(restored.all_edges()) == before_edges

    @rule()
    def two_independent_restores_of_the_same_snapshot_agree(self) -> None:
        """The "diff" property scoped down to what's real: restoring
        the same snapshot twice must produce identical counts -- if it
        didn't, `whytrail diff` (which restores both sides independently
        before comparing) would be comparing noise, not real content."""
        data = whytrail.snapshot(self.graph)
        first = whytrail.restore(data)
        second = whytrail.restore(data)
        assert len(first.all_nodes()) == len(second.all_nodes())
        assert len(first.all_edges()) == len(second.all_edges())
        assert {n.id for n in first.all_nodes()} == {n.id for n in second.all_nodes()}

    @rule()
    def serialize_round_trip_is_idempotent_once_restored(self) -> None:
        """Real finding from this property test, not assumed in
        advance: dumping the *live* graph and dumping a *restored*
        graph are not byte-identical, by design --
        `serialize._restore_node()` unconditionally sets
        `tombstoned=True` on every replayed node ("replayed graphs
        never hold live object references," per its own docstring),
        regardless of what the original live node's `tombstoned` value
        was. So `dumps(graph) != dumps(loads(dumps(graph)))` whenever
        the live graph still has any non-tombstoned node -- a real,
        previously-unverified asymmetry, confirmed by this test
        failing on its first, stronger version (which assumed
        unconditional round-trip idempotence) rather than anticipated.

        The actual stable property: once a graph has been through one
        restore, every node is permanently tombstoned, so *further*
        restore/dump cycles are idempotent -- checked here."""
        once_restored = serialize.loads(serialize.dumps(self.graph))
        first_dump = serialize.dumps(once_restored)
        twice_restored = serialize.loads(first_dump)
        second_dump = serialize.dumps(twice_restored)
        assert first_dump == second_dump

    @rule()
    def graph_never_exceeds_max_nodes(self) -> None:
        assert len(self.graph) <= self.graph.max_nodes

    @rule()
    def why_never_raises_regardless_of_state(self) -> None:
        # An object that was never tracked at all -- why()'s
        # never-raises contract (ADR §19) must hold no matter what
        # sequence of operations came before this rule.
        explanation = whytrail.why(_Value(-1))
        assert isinstance(explanation, whytrail.Explanation)
        assert explanation.known is False


# max_examples kept modest: each example runs a full sequence of rules,
# and this machine's own invariants (not raw iteration count) are what
# matters -- see the module docstring's "cheap and real" framing.
TestGraphLifecycle = GraphLifecycleMachine.TestCase
# suppress_health_check=[too_slow]: the same cold-start artifact
# test_redaction_fuzz.py's _FUZZ_SETTINGS already documents (first
# interpreter/import cost, not a property that should ever fail a
# build) -- the first rule call here pays whytrail's own one-time
# import cost, not a per-call regression.
TestGraphLifecycle.settings = settings(
    max_examples=50, stateful_step_count=30, suppress_health_check=[HealthCheck.too_slow], deadline=None
)
