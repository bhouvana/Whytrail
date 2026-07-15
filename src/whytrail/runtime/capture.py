"""Explicit, opt-in capture primitives: track() and @tracked (ADR §04,
§05). This -- not global tracing -- is the default v1 capture
mechanism: cost is paid only where a developer deliberately asks for
it.
"""

from __future__ import annotations

import functools
import inspect
import threading
import typing as t

from .._repr import safe_repr
from ..core.node import Confidence, EdgeKind, Node, NodeKind
from .context import active_graph, current_scope

_T = t.TypeVar("_T")


def _location(frame: t.Any) -> str | None:
    if frame is None:
        return None
    code = frame.f_code
    return f"{code.co_filename}:{frame.f_lineno}, in {code.co_name}"


def _call_site(skip: int = 2) -> str | None:
    """Location `skip` frames up from the function that calls this
    helper. skip=2 is "the code that called my caller" -- i.e. the
    user's call site when invoked directly from track()/tracked()."""
    frame = inspect.currentframe()
    try:
        for _ in range(skip):
            if frame is None:
                break
            frame = frame.f_back
        return _location(frame)
    finally:
        del frame


def _thread_name() -> str:
    return threading.current_thread().name


def track(
    obj: _T,
    *,
    label: str | None = None,
    derived_from: t.Any = None,
    confidence: float = Confidence.EXPLICIT.value,
    **metadata: t.Any,
) -> _T:
    """Tag `obj` for provenance capture. Returns `obj` unchanged --
    identity and type are preserved, no proxying (ADR §07): wrapping
    would break isinstance checks and fast paths in C-optimized
    libraries, so tracking is done by an out-of-band graph node, not by
    substituting the object.
    """
    scope = current_scope()
    if scope is None or not scope.should_capture():
        return obj

    graph = active_graph()
    node = graph.add_node(
        NodeKind.VALUE,
        label if label is not None else safe_repr(obj),
        obj=obj,
        location=_call_site(),
        thread=_thread_name(),
        metadata=metadata,
    )

    if derived_from is not None:
        parents = derived_from if isinstance(derived_from, (list, tuple)) else [derived_from]
        for parent in parents:
            parent_node = graph.node_for(parent)
            if parent_node is None:
                parent_node = graph.add_node(
                    NodeKind.VALUE, safe_repr(parent), obj=parent, location=_call_site()
                )
            graph.add_edge(parent_node, node, EdgeKind.DERIVED_FROM, confidence=confidence)

    return obj


def tracked(func: t.Callable[..., t.Any] | None = None, *, capture_args: bool = True) -> t.Callable[..., t.Any]:
    """Decorator recording a function boundary as causal edges: each
    argument -> a Call node -> the return value or the raised
    exception (ADR §05).

        @whytrail.tracked
        def apply_discount(price, code):
            ...
    """

    def decorator(fn: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
        try:
            signature = inspect.signature(fn)
        except (TypeError, ValueError):
            signature = None

        @functools.wraps(fn)
        def wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
            scope = current_scope()
            if scope is None or not scope.should_capture():
                return fn(*args, **kwargs)

            graph = active_graph()
            frame = inspect.currentframe()
            call_site = _location(frame.f_back) if frame is not None else None
            del frame
            call_node = graph.add_node(
                NodeKind.CALL,
                f"{fn.__qualname__}(...)",
                location=call_site,
                thread=_thread_name(),
            )

            if capture_args and signature is not None:
                _link_arguments(graph, signature, args, kwargs, call_node)

            try:
                result = fn(*args, **kwargs)
            except BaseException as exc:
                exc_node = graph.add_node(
                    NodeKind.EXCEPTION,
                    f"{type(exc).__name__}: {exc}",
                    obj=exc,
                    location=call_site,
                )
                graph.add_edge(call_node, exc_node, EdgeKind.RAISED_FROM)
                raise
            else:
                if result is not None:
                    result_node = graph.node_for(result)
                    if result_node is None:
                        result_node = graph.add_node(NodeKind.VALUE, safe_repr(result), obj=result)
                    graph.add_edge(call_node, result_node, EdgeKind.DERIVED_FROM)
                return result

        wrapper.__whytrail_wrapped__ = fn  # type: ignore[attr-defined]
        return wrapper

    if func is not None:
        return decorator(func)
    return decorator


def _link_arguments(
    graph: t.Any, signature: inspect.Signature, args: tuple[t.Any, ...], kwargs: dict[str, t.Any], call_node: Node
) -> None:
    try:
        bound = signature.bind_partial(*args, **kwargs)
    except TypeError:
        return
    for name, value in bound.arguments.items():
        arg_node = graph.node_for(value)
        if arg_node is None:
            arg_node = graph.add_node(NodeKind.VALUE, f"{name}={safe_repr(value)}", obj=value)
        graph.add_edge(arg_node, call_node, EdgeKind.PASSED_TO)
