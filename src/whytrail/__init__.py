"""Python tells you where. whytrail tells you why.

Two tiers, one entry point (ADR §02, §05):

  Tier 1 -- zero configuration. why(some_exception) reassembles a
  causal chain from data CPython already retains: __traceback__,
  __cause__, __context__, and live frame locals.

  Tier 2 -- opt-in and scoped. why(some_tracked_value) walks a small
  provenance graph built only for values a developer deliberately
  watched with track(), @tracked, or trace().

Both answer through why(). Something that was never tracked gets an
honest "unknown," never a fabricated answer -- see ADR §11.
"""

from __future__ import annotations

import typing as t

from ._repr import safe_repr
from .core import serialize as _serialize
from .core.explanation import Explanation, ExplanationStep
from .core.graph import ProvenanceGraph
from .core.node import Confidence, Edge, Node
from .explainers.builtin import explain_exception
from .protocols import call_why_protocol
from .registry import coerce, register, register_from_plugin, resolve_explainer
from .runtime.capture import track, tracked
from .runtime.context import current_scope, default_graph, trace

__version__ = "0.2.1"

# Deliberately small: five verbs, two persistence helpers, and the two
# names every explainer author touches (Explanation, ExplanationStep,
# Confidence). Everything else a plugin author or advanced user needs
# -- ProvenanceGraph, TraceScope, SupportsWhy, NodeKind, EdgeKind, the
# raw Node/Edge types -- is one submodule import away
# (whytrail.core.graph, whytrail.runtime.context, whytrail.protocols,
# whytrail.core.node) rather than crowding `import whytrail; whytrail.<tab>`
# for the median user who only ever calls why(). See the strategy
# review's namespace audit.
__all__ = [
    "why",
    "track",
    "tracked",
    "trace",
    "register",
    "register_from_plugin",
    "snapshot",
    "restore",
    "Explanation",
    "ExplanationStep",
    "Confidence",
    "__version__",
]


def why(obj: t.Any, *, max_depth: int = 8) -> Explanation:
    """The one public entry point (ADR §05, §10).

    Tier 1: obj is an exception -- reconstructs its causal chain from
    data CPython already retains. No setup required.

    Tier 2: obj is anything else -- looks for a __why__ method, then a
    registered explainer, then a provenance-graph node captured by
    track()/@tracked/trace(). If none of those know anything about
    obj, returns an Explanation that says so plainly.

    Never raises: a failure anywhere in resolution degrades to an
    "unknown" Explanation rather than propagating into caller code
    (ADR §19).
    """
    try:
        return _why_impl(obj, max_depth=max_depth)
    except Exception:  # noqa: BLE001 - why() must never raise, see ADR §19
        return Explanation(subject=safe_repr(obj), steps=[], tracked=False)


def _why_impl(obj: t.Any, *, max_depth: int) -> Explanation:
    # Protocol and registry get first look even for exceptions -- a
    # plugin explaining e.g. requests.RequestException with domain
    # detail (method, URL, response body) should win over the generic
    # traceback walk. Tier 1's exception explainer is the built-in,
    # always-available *fallback* for exceptions nothing more specific
    # claims, not a shortcut that preempts plugins (ADR §02, §06).
    protocol_result = call_why_protocol(obj)
    if protocol_result is not None:
        return protocol_result

    explainer = resolve_explainer(type(obj))
    if explainer is not None:
        try:
            raw = explainer(obj)
        except Exception:  # noqa: BLE001 - a broken plugin must not crash why()
            raw = None
        coerced = coerce(obj, raw)
        if coerced is not None:
            return coerced

    if isinstance(obj, BaseException):
        return explain_exception(obj, max_depth=max_depth)

    return _explain_from_graph(obj, max_depth=max_depth)


def _explain_from_graph(obj: t.Any, *, max_depth: int) -> Explanation:
    candidates: list[ProvenanceGraph] = []
    scope = current_scope()
    if scope is not None:
        candidates.append(scope.graph)
    default = default_graph()
    if default not in candidates:
        candidates.append(default)

    for graph in candidates:
        node = graph.node_for(obj)
        if node is not None:
            nodes, edges = graph.ancestors(node.id, max_depth=max_depth)
            steps = _steps_from_traversal(node, nodes, edges)
            return Explanation(subject=safe_repr(obj), steps=steps, tracked=True, nodes=nodes, edges=edges)

    return Explanation(subject=safe_repr(obj), steps=[], tracked=False)


def _steps_from_traversal(
    target: Node, nodes: list[Node], edges: list[Edge]
) -> list[ExplanationStep]:
    """Turn the ancestor subgraph into an ordered, human-readable
    *single dominant path* -- root cause first, ending at the node the
    caller asked about. When a node has more than one real parent (a
    diamond: two calls converging on the same value, common under
    trace(deep=True)), this picks the highest-confidence one and does
    not narrate the rest -- .text/.steps is a readable summary, not
    the full picture. Explanation.graph()/.nodes/.edges carry the
    complete captured DAG for anyone who needs it; that distinction is
    deliberate, not a bug (see ADR §11: honest partial answers are
    fine, silently-lossy ones presented as complete are not).

    At each step, follows the highest-confidence parent; ties are
    broken by which edge was recorded first."""
    nodes_by_id = {n.id: n for n in nodes}
    incoming: dict[int, list[Edge]] = {}
    for edge in edges:
        incoming.setdefault(edge.target, []).append(edge)

    chain: list[Node] = []
    branch_counts: dict[int, int] = {}  # node.id -> how many real parents it had
    seen: set[int] = set()
    current: Node | None = target
    while current is not None and current.id not in seen:
        seen.add(current.id)
        chain.append(current)
        parents = incoming.get(current.id, [])
        branch_counts[current.id] = len(parents)
        if not parents:
            break
        best_edge = max(parents, key=lambda e: e.confidence)
        current = nodes_by_id.get(best_edge.source)
    chain.reverse()

    steps: list[ExplanationStep] = []
    for i, node in enumerate(chain):
        confidence = Confidence.EXPLICIT.value
        if i > 0:
            # named distinctly from the `edge` loop variable above --
            # Python has no block scoping, and mypy --strict correctly
            # flags reusing a name for a differently-typed (Optional)
            # value in the same function scope.
            matching_edge = next(
                (e for e in incoming.get(chain[i].id, []) if e.source == chain[i - 1].id),
                None,
            )
            confidence = matching_edge.confidence if matching_edge is not None else Confidence.INFERRED.value
        description = f"{node.kind.value}: {node.label}"
        if node.tombstoned:
            description += " (garbage collected)"
        # Surface, don't hide, when this step's summary skipped real
        # branches (ADR 0002 §3 item 3): this function documents that it
        # follows one dominant path through a DAG, which is only honest
        # if a reader can tell *from the output itself* that there was
        # more to see, not just from reading this function's docstring.
        other_parents = branch_counts.get(node.id, 0) - 1
        if other_parents > 0:
            plural = "path" if other_parents == 1 else "paths"
            description += f"  (+{other_parents} other {plural} converge here, see .graph())"
        steps.append(
            ExplanationStep(
                description=description,
                confidence=confidence,
                location=node.location,
                kind=node.kind.value,
            )
        )
    return steps


def snapshot(graph: ProvenanceGraph | None = None) -> str:
    """Persist a graph as JSON-lines (ADR §05, §12). Defaults to the
    shared process graph. Explicit and opt-in -- capture itself never
    writes to disk on its own."""
    return _serialize.dumps(graph if graph is not None else default_graph())


def restore(data: str) -> ProvenanceGraph:
    """Rebuild a read-only replay graph from a snapshot() (ADR §14).
    Replayed nodes carry their original metadata but, having outlived
    the process that captured them, behave as tombstones -- there is
    no live object left to hold a weakref to."""
    return _serialize.loads(data)
