"""LangChain integration (ADR 0002 §7 -- the highest-leverage new
ecosystem wedge identified in the category strategy review, not one
that was in the original integration brainstorm).

"Why did this chain produce this output" is close to exactly whytrail's
model applied to LLM application debugging: a chain's answer is the
end of a causal path through prompts, retrieved documents, and tool
calls, and LangChain already exposes exactly the lifecycle events
needed to capture it -- on_chain_start/end/error, on_llm_start/end/
error, on_tool_start/end/error, on_retriever_start/end/error -- via
its callback system.

Architecturally this mirrors runtime/monitoring.py's sys.monitoring
deep-trace backend almost exactly, just driven by LangChain's callback
events instead of PEP 669 events: a start event opens a Call node, an
end event links it to its output, an error links it to an Exception
node, and nested runs link to their parent via OCCURRED_DURING. It
builds on whytrail's public ProvenanceGraph/Node/Edge primitives, so a
chain's provenance is queryable through the exact same why() a plain
Python value would use -- no separate query language, no separate
viewer.
"""

from __future__ import annotations

import typing as t
import uuid

from langchain_core.callbacks.base import BaseCallbackHandler

from whytrail._repr import safe_repr
from whytrail.core.explanation import Explanation
from whytrail.core.node import Confidence, EdgeKind, Node, NodeKind
from whytrail.runtime.context import active_graph


class WhytrailCallbackHandler(BaseCallbackHandler):
    """Pass to any LangChain invocation:

        handler = WhytrailCallbackHandler()
        with whytrail.trace():
            result = chain.invoke({"question": "..."}, config={"callbacks": [handler]})
        print(handler.why())

    `handler.why()` is the reliable way to get the explanation: it
    doesn't depend on object identity surviving whatever LangChain does
    to a run's output between on_*_end and what .invoke() ultimately
    hands back to the caller (it often doesn't -- e.g. a chain that
    extracts a single output key returns a different object than the
    dict on_chain_end saw). whytrail.why(result) is also attempted
    best-effort via identity tracking and works for simpler chains
    where the returned object is unchanged, but handler.why() is not
    dependent on that.
    """

    def __init__(self) -> None:
        super().__init__()
        self._nodes: dict[uuid.UUID, Node] = {}
        self._top_level_runs: set[uuid.UUID] = set()
        self.last_run: object | None = None

    # -- shared plumbing --------------------------------------------------

    def _start(self, run_id: uuid.UUID, parent_run_id: uuid.UUID | None, label: str) -> None:
        graph = active_graph()
        node = graph.add_node(NodeKind.CALL, label)
        self._nodes[run_id] = node
        if parent_run_id is None:
            self._top_level_runs.add(run_id)
        else:
            parent_node = self._nodes.get(parent_run_id)
            if parent_node is not None:
                # source=this (child) run, target=its parent: ancestors()
                # walking backward from a leaf value discovers the call
                # that produced it, then -- via this edge -- the call's
                # own children (its sub-steps), giving the full subtree
                # rather than stopping at the immediate call. See
                # runtime/monitoring.py's deep-trace backend for the
                # same pattern driven by sys.monitoring instead.
                graph.add_edge(node, parent_node, EdgeKind.OCCURRED_DURING, confidence=Confidence.EXPLICIT.value)

    def _end(self, run_id: uuid.UUID, result: t.Any, result_label: str) -> None:
        graph = active_graph()
        node = self._nodes.get(run_id)
        if node is None:
            return
        result_obj = result if result is not None else object()
        result_node = graph.node_for(result_obj)
        if result_node is None:
            result_node = graph.add_node(NodeKind.VALUE, result_label, obj=result_obj)
        graph.add_edge(node, result_node, EdgeKind.DERIVED_FROM, confidence=Confidence.EXPLICIT.value)
        if run_id in self._top_level_runs:
            # anchor at the *result*, not the call node itself -- ancestors()
            # walks backward from here (result <- derived_from <- call
            # <- occurred_during <- each sub-step), which is why this
            # has to be the result, not the call: starting at the call
            # node itself would only ever discover its children, never
            # its own output.
            self.last_run = result_obj

    def _error(self, run_id: uuid.UUID, error: BaseException) -> None:
        graph = active_graph()
        node = self._nodes.get(run_id)
        if node is None:
            return
        exc_node = graph.add_node(NodeKind.EXCEPTION, f"{type(error).__name__}: {error}", obj=error)
        graph.add_edge(node, exc_node, EdgeKind.RAISED_FROM, confidence=Confidence.EXPLICIT.value)
        if run_id in self._top_level_runs:
            # Deliberately *not* self.last_run = error: why() resolves
            # any BaseException through tier 1 (ADR 0001 §6) before it
            # ever looks at the provenance graph, which would silently
            # discard the surrounding chain/tool/retriever context this
            # handler just built. A dedicated marker node, linked the
            # same way a normal result would be, keeps handler.why() on
            # the graph path so failed runs still show their chain.
            marker = object()
            marker_node = graph.add_node(
                NodeKind.VALUE, f"failed: {type(error).__name__}: {error}", obj=marker
            )
            graph.add_edge(node, marker_node, EdgeKind.DERIVED_FROM, confidence=Confidence.EXPLICIT.value)
            self.last_run = marker

    def why(self) -> Explanation:
        """Explain the most recently completed top-level run this
        handler observed. Built entirely from whytrail's public why(),
        not a duplicate of its internals -- see the class docstring
        for why this exists alongside plain whytrail.why(result)."""
        import whytrail

        return whytrail.why(self.last_run if self.last_run is not None else object())

    # -- chain --------------------------------------------------------

    def on_chain_start(
        self,
        serialized: dict[str, t.Any],
        inputs: dict[str, t.Any],
        *,
        run_id: uuid.UUID,
        parent_run_id: uuid.UUID | None = None,
        **kwargs: t.Any,
    ) -> None:
        name = _name(serialized, kwargs, "chain")
        self._start(run_id, parent_run_id, f"chain:{name}({safe_repr(inputs)})")

    def on_chain_end(
        self, outputs: dict[str, t.Any], *, run_id: uuid.UUID, parent_run_id: uuid.UUID | None = None, **kwargs: t.Any
    ) -> None:
        self._end(run_id, outputs, safe_repr(outputs))

    def on_chain_error(
        self, error: BaseException, *, run_id: uuid.UUID, parent_run_id: uuid.UUID | None = None, **kwargs: t.Any
    ) -> None:
        self._error(run_id, error)

    # -- llm ------------------------------------------------------------

    def on_llm_start(
        self,
        serialized: dict[str, t.Any],
        prompts: list[str],
        *,
        run_id: uuid.UUID,
        parent_run_id: uuid.UUID | None = None,
        **kwargs: t.Any,
    ) -> None:
        name = _name(serialized, kwargs, "llm")
        self._start(run_id, parent_run_id, f"llm:{name}({safe_repr(prompts)})")

    def on_llm_end(
        self, response: t.Any, *, run_id: uuid.UUID, parent_run_id: uuid.UUID | None = None, **kwargs: t.Any
    ) -> None:
        self._end(run_id, response, safe_repr(response))

    def on_llm_error(
        self, error: BaseException, *, run_id: uuid.UUID, parent_run_id: uuid.UUID | None = None, **kwargs: t.Any
    ) -> None:
        self._error(run_id, error)

    # -- tool -------------------------------------------------------------

    def on_tool_start(
        self,
        serialized: dict[str, t.Any],
        input_str: str,
        *,
        run_id: uuid.UUID,
        parent_run_id: uuid.UUID | None = None,
        **kwargs: t.Any,
    ) -> None:
        name = _name(serialized, kwargs, "tool")
        self._start(run_id, parent_run_id, f"tool:{name}({safe_repr(input_str)})")

    def on_tool_end(
        self, output: t.Any, *, run_id: uuid.UUID, parent_run_id: uuid.UUID | None = None, **kwargs: t.Any
    ) -> None:
        self._end(run_id, output, safe_repr(output))

    def on_tool_error(
        self, error: BaseException, *, run_id: uuid.UUID, parent_run_id: uuid.UUID | None = None, **kwargs: t.Any
    ) -> None:
        self._error(run_id, error)

    # -- retriever (RAG: which documents fed the answer) ------------------

    def on_retriever_start(
        self,
        serialized: dict[str, t.Any],
        query: str,
        *,
        run_id: uuid.UUID,
        parent_run_id: uuid.UUID | None = None,
        **kwargs: t.Any,
    ) -> None:
        self._start(run_id, parent_run_id, f"retriever({safe_repr(query)})")

    def on_retriever_end(
        self, documents: t.Sequence[t.Any], *, run_id: uuid.UUID, parent_run_id: uuid.UUID | None = None, **kwargs: t.Any
    ) -> None:
        self._end(run_id, documents, f"{len(documents)} document(s) retrieved")

    def on_retriever_error(
        self, error: BaseException, *, run_id: uuid.UUID, parent_run_id: uuid.UUID | None = None, **kwargs: t.Any
    ) -> None:
        self._error(run_id, error)


def _name(serialized: dict[str, t.Any] | None, kwargs: dict[str, t.Any], default: str) -> str:
    # A run's human-assigned name (.with_config(run_name=...)) arrives
    # via kwargs["name"], not `serialized` -- `serialized` is often
    # None entirely for RunnableLambda-style components that have
    # nothing to serialize. Check both rather than assuming one.
    if kwargs.get("name"):
        return str(kwargs["name"])
    if not serialized:
        return default
    if serialized.get("name"):
        return str(serialized["name"])
    ident = serialized.get("id")
    if isinstance(ident, list) and ident:
        return str(ident[-1])
    return default
