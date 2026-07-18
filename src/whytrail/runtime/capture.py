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
from ..core.graph import ProvenanceGraph
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

    Works the same way on an `async def` function -- awaits it and
    captures the real result/exception, rather than (a 0.3 bug, fixed)
    silently tracking the coroutine object calling it returns before
    anyone awaits it. Same for a generator or async generator function
    (`yield`/`async ... yield`) -- each yielded value gets its own
    node derived from the call, not just the generator object itself
    (the same bug, same fix, found auditing the same class of mistake
    a second place it occurred). `inspect.iscoroutinefunction` /
    `isgeneratorfunction` / `isasyncgenfunction` decide which of the
    four wrapper shapes to use once, at decoration time, not per call.

    Generator/async-generator tracking is scoped to what it can do
    correctly: `.send()`/`.throw()` are not forwarded into the wrapped
    generator the way they would be on an undecorated one -- a value
    sent in, or an exception thrown in, is recorded as this call's own
    outcome and does not resume the wrapped generator body the way
    `some_generator.send(x)` normally would. Plain iteration (`for`,
    `list(...)`, `async for`) -- the common case, and the one every
    yielded value needs a node for -- is fully supported. Forwarding
    `.send()`/`.throw()` correctly would need a materially more
    complex wrapper for a bidirectional-coroutine-style usage of
    generators that `@tracked` has no evidence anyone relies on; not
    attempted speculatively.
    """

    def decorator(fn: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
        try:
            signature = inspect.signature(fn)
        except (TypeError, ValueError):
            signature = None

        if inspect.isasyncgenfunction(fn):

            @functools.wraps(fn)
            async def async_gen_wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
                scope = current_scope()
                if scope is None or not scope.should_capture():
                    async for item in fn(*args, **kwargs):
                        yield item
                    return

                graph = active_graph()
                frame = inspect.currentframe()
                call_site = _location(frame.f_back) if frame is not None else None
                del frame
                call_node = _make_call_node(graph, fn, call_site)
                if capture_args and signature is not None:
                    _link_arguments(graph, signature, args, kwargs, call_node)

                try:
                    async for item in fn(*args, **kwargs):
                        _record_result(graph, call_node, item)
                        yield item
                except BaseException as exc:
                    _record_exception(graph, call_node, exc, call_site)
                    raise

            async_gen_wrapper.__whytrail_wrapped__ = fn  # type: ignore[attr-defined]
            return async_gen_wrapper

        if inspect.isgeneratorfunction(fn):

            @functools.wraps(fn)
            def gen_wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
                scope = current_scope()
                if scope is None or not scope.should_capture():
                    yield from fn(*args, **kwargs)
                    return

                graph = active_graph()
                frame = inspect.currentframe()
                call_site = _location(frame.f_back) if frame is not None else None
                del frame
                call_node = _make_call_node(graph, fn, call_site)
                if capture_args and signature is not None:
                    _link_arguments(graph, signature, args, kwargs, call_node)

                try:
                    for item in fn(*args, **kwargs):
                        _record_result(graph, call_node, item)
                        yield item
                except BaseException as exc:
                    _record_exception(graph, call_node, exc, call_site)
                    raise

            gen_wrapper.__whytrail_wrapped__ = fn  # type: ignore[attr-defined]
            return gen_wrapper

        if inspect.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
                scope = current_scope()
                if scope is None or not scope.should_capture():
                    return await fn(*args, **kwargs)

                graph = active_graph()
                frame = inspect.currentframe()
                call_site = _location(frame.f_back) if frame is not None else None
                del frame
                call_node = _make_call_node(graph, fn, call_site)
                if capture_args and signature is not None:
                    _link_arguments(graph, signature, args, kwargs, call_node)

                try:
                    result = await fn(*args, **kwargs)
                except BaseException as exc:
                    _record_exception(graph, call_node, exc, call_site)
                    raise
                else:
                    _record_result(graph, call_node, result)
                    return result

            async_wrapper.__whytrail_wrapped__ = fn  # type: ignore[attr-defined]
            return async_wrapper

        @functools.wraps(fn)
        def wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
            scope = current_scope()
            if scope is None or not scope.should_capture():
                return fn(*args, **kwargs)

            graph = active_graph()
            frame = inspect.currentframe()
            call_site = _location(frame.f_back) if frame is not None else None
            del frame
            call_node = _make_call_node(graph, fn, call_site)
            if capture_args and signature is not None:
                _link_arguments(graph, signature, args, kwargs, call_node)

            try:
                result = fn(*args, **kwargs)
            except BaseException as exc:
                _record_exception(graph, call_node, exc, call_site)
                raise
            else:
                _record_result(graph, call_node, result)
                return result

        wrapper.__whytrail_wrapped__ = fn  # type: ignore[attr-defined]
        return wrapper

    if func is not None:
        return decorator(func)
    return decorator


def _make_call_node(graph: ProvenanceGraph, fn: t.Callable[..., t.Any], call_site: str | None) -> Node:
    return graph.add_node(
        NodeKind.CALL,
        f"{fn.__qualname__}(...)",
        location=call_site,
        thread=_thread_name(),
    )


def _record_exception(graph: ProvenanceGraph, call_node: Node, exc: BaseException, call_site: str | None) -> None:
    exc_node = graph.add_node(
        NodeKind.EXCEPTION,
        f"{type(exc).__name__}: {exc}",
        obj=exc,
        location=call_site,
    )
    graph.add_edge(call_node, exc_node, EdgeKind.RAISED_FROM)


def _record_result(graph: ProvenanceGraph, call_node: Node, result: t.Any) -> None:
    if result is not None:
        result_node = graph.node_for(result)
        if result_node is None:
            result_node = graph.add_node(NodeKind.VALUE, safe_repr(result), obj=result)
        graph.add_edge(call_node, result_node, EdgeKind.DERIVED_FROM)


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
