"""Chaos/negative testing for malformed input and partial-failure
recovery: corrupted snapshots, an interrupted serialization, a plugin
whose own `register()` raises, and a missing optional dependency.
Scoped to concrete, real code paths (`core/serialize.py`'s loader,
`registry.py`'s lazy-load try/except) rather than a generic fault-
injection framework -- each test targets a specific line already in
the code, not a hypothetical one.
"""

from __future__ import annotations

import json

import pytest

import whytrail
from whytrail import registry
from whytrail.core import serialize
from whytrail.core.graph import ProvenanceGraph
from whytrail.core.node import EdgeKind, NodeKind

_MANIFEST = json.dumps({"type": "whytrail_snapshot", "version": serialize.SNAPSHOT_FORMAT_VERSION})


# -- corrupted / malformed snapshots --------------------------------------


def test_truncated_json_line_raises_a_clear_error_not_silent_corruption():
    data = _MANIFEST + "\nnot json at all {{{"
    with pytest.raises(json.JSONDecodeError):
        serialize.loads(data)


def test_node_payload_missing_required_field_raises_a_clear_error():
    data = _MANIFEST + '\n{"type": "node", "kind": "value", "label": "x"}'  # no "id"
    with pytest.raises(KeyError):
        serialize.loads(data)


def test_unrecognized_line_type_raises_rather_than_silently_dropping_data():
    """Real bug, found by this test: loads()'s own docstring already
    claimed it doesn't "silently drop data it doesn't recognize," but
    until this fix, any line whose "type" wasn't exactly
    "whytrail_snapshot"/"node"/"edge" fell through every branch
    untouched -- confirmed by constructing exactly that input and
    finding no exception and a graph missing the data, before the fix
    in core/serialize.py's loads()."""
    data = _MANIFEST + '\n{"type": "something_this_version_has_never_heard_of", "id": 1}'
    with pytest.raises(ValueError, match="unrecognized snapshot line type"):
        serialize.loads(data)


def test_empty_snapshot_loads_to_an_empty_graph():
    restored = serialize.loads("")
    assert len(restored) == 0


def test_snapshot_with_only_whitespace_lines_loads_to_an_empty_graph():
    restored = serialize.loads("\n\n   \n\t\n")
    assert len(restored) == 0


# -- cross-version snapshot harness ---------------------------------------
#
# There is exactly one snapshot format version that has ever existed
# (added this same session that introduced SNAPSHOT_FORMAT_VERSION) --
# there is no historical corpus of real old-version snapshots to
# restore against yet. This is the harness ready for that once a second
# format version ships, populated today with what's actually real: the
# current version round-trips, a legacy (pre-versioning) snapshot with
# no manifest line still loads (already covered in test_serialize.py),
# and a fabricated future version is rejected rather than
# misinterpreted.


def test_current_version_snapshot_restores_correctly():
    graph = ProvenanceGraph()
    node = graph.add_node(NodeKind.VALUE, "v")
    graph.add_edge(node, node, EdgeKind.DERIVED_FROM)
    restored = serialize.loads(serialize.dumps(graph))
    assert len(restored) == 1


def test_a_fabricated_far_future_version_is_rejected_not_silently_accepted():
    payload = json.dumps({"type": "whytrail_snapshot", "version": serialize.SNAPSHOT_FORMAT_VERSION + 100})
    with pytest.raises(serialize.SnapshotVersionError):
        serialize.loads(payload)


def test_a_snapshot_missing_the_version_key_entirely_defaults_to_version_1():
    # payload.get("version", 1) -- a manifest line present but with no
    # "version" key at all (distinct from no manifest line at all,
    # already covered) should default to 1, not raise or misbehave.
    data = json.dumps({"type": "whytrail_snapshot"}) + '\n{"type": "node", "id": 1, "kind": "value", "label": "x"}'
    restored = serialize.loads(data)
    assert len(restored) == 1


# -- interrupted serialization ---------------------------------------------


def test_dumps_failing_partway_through_does_not_mutate_the_graph(monkeypatch):
    """dumps() never mutates the graph it's serializing -- confirmed
    directly by forcing a failure partway through (the 2nd json.dumps
    call) rather than assumed from "it's a read-only function.\""""
    graph = ProvenanceGraph()
    graph.add_node(NodeKind.VALUE, "a")
    graph.add_node(NodeKind.VALUE, "b")
    before_node_count = len(graph)
    before_labels = sorted(n.label for n in graph.all_nodes())

    real_dumps = json.dumps
    call_count = {"n": 0}

    def _flaky_dumps(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 2:
            raise RuntimeError("simulated interruption mid-serialization")
        return real_dumps(*args, **kwargs)

    monkeypatch.setattr(serialize.json, "dumps", _flaky_dumps)
    with pytest.raises(RuntimeError, match="simulated interruption"):
        serialize.dumps(graph)

    assert len(graph) == before_node_count
    assert sorted(n.label for n in graph.all_nodes()) == before_labels


# -- a plugin whose register() raises must not break the rest -------------


def test_a_builtin_explainer_whose_register_raises_does_not_break_others(monkeypatch):
    """_load_builtin_explainers()'s own broad except is exactly what a
    0.3 audit found silently swallowing a real NameError bug earlier
    this project's history (see CHANGELOG.md) -- confirmed here as a
    deliberate, working safety net for a genuinely broken plugin,
    not re-litigating whether the except should be there."""
    registry.reset()
    real_import_module = registry.importlib.import_module
    calls: list[str] = []

    class _BrokenModule:
        def register(self) -> None:
            calls.append("broken register() called")
            raise RuntimeError("this plugin's register() is broken")

    def _fake_import_module(name: str):
        if name == "whytrail.integrations.requests":
            return _BrokenModule()
        return real_import_module(name)

    monkeypatch.setattr(registry.importlib, "import_module", _fake_import_module)
    try:
        # Triggers _load_builtin_explainers() for every builtin,
        # including the faked-broken "requests" one.
        explanation = whytrail.why(ValueError("boom"))
        assert calls, "expected the faked broken register() to actually run"
        assert isinstance(explanation, whytrail.Explanation)
    finally:
        registry.reset()


def test_missing_optional_dependency_is_reported_not_confusing(monkeypatch):
    """An integration module whose underlying library isn't installed
    must fail with a clear ImportError at import time, and whytrail's
    own lazy-loader must swallow that cleanly (already exercised
    naturally in CI, since no single job installs every extra) --
    confirmed directly here by simulating one specific missing library
    rather than relying on whichever extras happen to be absent in
    whatever environment runs this test."""
    import builtins

    real_import = builtins.__import__

    def _blocking_import(name, *args, **kwargs):
        if name == "pydantic" or name.startswith("pydantic."):
            raise ImportError("simulated: pydantic is not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _blocking_import)
    registry.reset()
    try:
        # Must not raise: a missing optional dependency for one
        # integration must not break resolution for anything else.
        explanation = whytrail.why(ValueError("boom"))
        assert isinstance(explanation, whytrail.Explanation)
    finally:
        registry.reset()
