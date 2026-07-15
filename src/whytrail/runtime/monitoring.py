"""Deep-trace backend built on sys.monitoring / PEP 669 (ADR §04, §14
-- v2.0).

Auto-instruments Python calls inside an active `trace(deep=True)`
scope without requiring @tracked on every function. Gated to Python
3.12+, where sys.monitoring exists, and low-overhead by PEP 669's own
design compared to the old sys.settrace (ADR §04's reasoning for why
settrace was rejected but this wasn't).

Honest limitation, not hidden: PEP 669 events are process-wide once
enabled. A deep scope active on one thread also fires these callbacks
for unrelated code running concurrently on other threads during that
window -- each callback checks the active TraceScope via contextvars
and no-ops immediately if the call isn't inside an active deep scope,
but it still *fires* for every Python call happening anywhere in the
process while enabled. That's a real cost, not something the "scoped"
framing used elsewhere in this library should be allowed to paper
over.
"""

from __future__ import annotations

import inspect
import sys
import threading
import typing as t

from .._repr import safe_repr
from ..core.node import EdgeKind, NodeKind

MONITORING_AVAILABLE = hasattr(sys, "monitoring")

_TOOL_NAME = "whytrail"
_tool_id: int | None = None
_activation_count = 0
_lock = threading.Lock()
_seen_exceptions: set[int] = set()


def deep_trace_supported() -> bool:
    return MONITORING_AVAILABLE


def activate() -> None:
    """Reference-counted so nested/concurrent deep-trace scopes share
    one underlying sys.monitoring registration."""
    global _tool_id, _activation_count
    if not MONITORING_AVAILABLE:
        raise RuntimeError(
            "deep tracing needs sys.monitoring (PEP 669), which requires Python 3.12+; "
            f"this interpreter is {sys.version_info.major}.{sys.version_info.minor}."
        )
    with _lock:
        _activation_count += 1
        if _tool_id is not None:
            return
        _tool_id = _acquire_tool_id()
        events = sys.monitoring.events
        sys.monitoring.register_callback(_tool_id, events.PY_START, _on_start)
        sys.monitoring.register_callback(_tool_id, events.PY_RETURN, _on_return)
        sys.monitoring.register_callback(_tool_id, events.RAISE, _on_raise)
        sys.monitoring.set_events(_tool_id, events.PY_START | events.PY_RETURN | events.RAISE)


def deactivate() -> None:
    global _tool_id, _activation_count
    with _lock:
        if _activation_count == 0:
            return
        _activation_count -= 1
        if _activation_count > 0:
            return
        if _tool_id is not None:
            sys.monitoring.set_events(_tool_id, 0)
            sys.monitoring.free_tool_id(_tool_id)
            _tool_id = None
        _seen_exceptions.clear()


def _acquire_tool_id() -> int:
    for candidate in range(6):
        try:
            sys.monitoring.use_tool_id(candidate, _TOOL_NAME)
            return candidate
        except ValueError:
            continue
    raise RuntimeError("no free sys.monitoring tool id -- all 6 are already claimed by other tools")


def _active_deep_scope() -> t.Any:
    from .context import current_scope  # deferred: avoids a context.py <-> monitoring.py import cycle

    scope = current_scope()
    if scope is not None and getattr(scope, "deep", False):
        return scope
    return None


def _on_start(code: t.Any, offset: int) -> None:
    scope = _active_deep_scope()
    if scope is None:
        return
    frame = inspect.currentframe()
    caller = frame.f_back if frame is not None else None
    del frame
    lineno = caller.f_lineno if caller is not None else code.co_firstlineno
    del caller
    name = getattr(code, "co_qualname", code.co_name)
    call_node = scope.graph.add_node(
        NodeKind.CALL,
        f"{name}(...)",
        location=f"{code.co_filename}:{lineno}",
        thread=threading.current_thread().name,
    )
    stack = scope._deep_stack.setdefault(threading.get_ident(), [])
    if stack:
        # structural link only (no argument-level data flow, unlike
        # @tracked, which knows the callee's signature) -- still lets
        # why() traversal walk into nested calls instead of stopping
        # at the outermost frame.
        scope.graph.add_edge(call_node, stack[-1], EdgeKind.OCCURRED_DURING, confidence=0.7)
    stack.append(call_node)


def _on_return(code: t.Any, offset: int, retval: t.Any) -> None:
    scope = _active_deep_scope()
    if scope is None:
        return
    stack = scope._deep_stack.get(threading.get_ident())
    if not stack:
        return
    call_node = stack.pop()
    if retval is not None:
        graph = scope.graph
        result_node = graph.node_for(retval)
        if result_node is None:
            result_node = graph.add_node(NodeKind.VALUE, safe_repr(retval), obj=retval)
        graph.add_edge(call_node, result_node, EdgeKind.DERIVED_FROM, confidence=0.7)


def _on_raise(code: t.Any, offset: int, exc: BaseException) -> None:
    scope = _active_deep_scope()
    if scope is None:
        return
    if id(exc) in _seen_exceptions:
        return  # RAISE fires again at each unwound ancestor frame; record once
    _seen_exceptions.add(id(exc))
    stack = scope._deep_stack.get(threading.get_ident())
    call_node = stack[-1] if stack else None
    if call_node is None:
        return
    graph = scope.graph
    exc_node = graph.add_node(NodeKind.EXCEPTION, f"{type(exc).__name__}: {exc}", obj=exc)
    graph.add_edge(call_node, exc_node, EdgeKind.RAISED_FROM, confidence=0.7)
