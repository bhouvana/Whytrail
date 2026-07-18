"""sys.excepthook / threading.excepthook installer -- "install once,
see it everywhere," the same mechanic `rich.traceback.install()` uses
for Rich's own defining feature. Builds entirely on Tier 1 (ADR 0001):
no new capture mechanism, no opt-in tracking required, works on any
exception whytrail has never seen before -- the same zero-config
guarantee `why()` itself already makes, just surfaced automatically
instead of requiring a manual `why(exc)` call.

Two separate hooks, not one, found by testing rather than assumed:
`sys.excepthook` fires for both script-mode and interactive `python
-i` REPL exceptions (confirmed directly), but *never* for an uncaught
exception in a worker thread -- `threading.excepthook` (Python 3.8+)
is the separate hook Python itself added specifically because of that
gap. Installing only `sys.excepthook` would silently miss every
background-thread crash in any threaded server or worker, exactly the
kind of undocumented gap this project's culture is built to avoid.

Not hooked: IPython/Jupyter, which replaces its own exception display
entirely and never calls `sys.excepthook` -- covered instead by
`Explanation._repr_html_` for explicit `why(x)` calls in a notebook,
a different mechanism for a different environment, not a gap in this
one.
"""

from __future__ import annotations

import sys
import threading
import typing as t

_original_sys_excepthook: t.Any = None
_original_threading_excepthook: t.Any = None


def install(*, log_locals: bool = False, plain: bool = False) -> None:
    """Replace sys.excepthook and threading.excepthook so every
    uncaught exception in this process -- main thread, worker thread,
    or the interactive REPL -- prints why() first, then the original
    traceback (preserved, not replaced: the full frame-by-frame call
    stack a normal traceback shows is real information Tier 1's
    single-dominant-path summary doesn't repeat, so nothing is lost by
    installing this, only added).

        import whytrail
        whytrail.install()

        1 / 0  # ZeroDivisionError -- why() now prints automatically

    `log_locals` defaults to False: this hook's output often ends up
    somewhere whytrail doesn't control (journald, a container's stdout
    capture, a CI log) -- the same "redacted unless asked for" posture
    every other integration in this package uses. Worth naming
    directly: stock Python's own traceback shows no local variable
    values at all, so even with `log_locals=False` this is strictly
    more detail than the status quo (file/line/root-cause chain across
    __cause__/__context__), not just a formatting change.

    `plain=True` renders via `.plain_text` (prose) instead of `.text`
    (the bracketed-marker format) -- for a terminal a non-technical
    person might be watching.

    Safe to call more than once (only the first call's hooks are
    treated as "the real original" to restore later) and safe in a
    process where nothing ever raises (installing costs one dict
    lookup's worth of overhead per hook, paid only when an exception
    actually propagates uncaught).
    """
    global _original_sys_excepthook, _original_threading_excepthook
    if _original_sys_excepthook is None:
        _original_sys_excepthook = sys.excepthook
        _original_threading_excepthook = threading.excepthook

    def _sys_hook(exc_type: type[BaseException], exc_value: BaseException, exc_tb: t.Any) -> None:
        _report(exc_value, log_locals=log_locals, plain=plain)
        _original_sys_excepthook(exc_type, exc_value, exc_tb)

    def _threading_hook(args: t.Any) -> None:
        if args.exc_value is not None:
            _report(args.exc_value, log_locals=log_locals, plain=plain, thread_name=args.thread.name)
        _original_threading_excepthook(args)

    sys.excepthook = _sys_hook
    threading.excepthook = _threading_hook


def uninstall() -> None:
    """Restore whatever sys.excepthook/threading.excepthook were
    active before install() was first called. A no-op if install()
    was never called."""
    global _original_sys_excepthook, _original_threading_excepthook
    if _original_sys_excepthook is not None:
        sys.excepthook = _original_sys_excepthook
        threading.excepthook = _original_threading_excepthook
        _original_sys_excepthook = None
        _original_threading_excepthook = None


def _report(exc: BaseException, *, log_locals: bool, plain: bool, thread_name: str | None = None) -> None:
    from . import why  # lazy: why() lives in whytrail/__init__.py, which imports this module

    explanation = why(exc)
    if not log_locals:
        explanation = explanation.redacted()
    text = explanation.plain_text if plain else explanation.text
    if thread_name is not None:
        print(f"Exception in thread {thread_name!r} (explained by whytrail):", file=sys.stderr)
    print(text, file=sys.stderr)
    print(file=sys.stderr)
