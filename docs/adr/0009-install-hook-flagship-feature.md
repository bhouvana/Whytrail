# ADR 0009: `whytrail.install()` -- the flagship feature, and why it's a sixth top-level name

## Status

Accepted and implemented: `src/whytrail/hook.py`, `whytrail.install`/
`whytrail.uninstall` exported from `whytrail/__init__.py`, 12 tests
(`tests/unit/test_hook.py`), README's opening section rewritten around
it, `examples/ex_install_hook.py`.

## Context

An external review, after watching several rounds of audits converge
(engine invariants, Python-semantic edge cases, debugging-workflow
gaps, pre-1.0 naming consistency) with diminishing returns, asked a
different question: not "what's missing" but "what single capability
would make an experienced engineer install this after a 30-second
demo" -- explicitly modeled on Rich's pretty tracebacks, pytest's
assertion rewriting, and Pydantic's validation-from-type-hints. The
brief: generate real candidates, critique them, reject anything that's
"just another command, renderer, plugin, or explanation domain," and
build only the one that clearly earns the "defining feature" label.

## Ten candidates, and why nine were rejected

1. **`sys.excepthook`/`threading.excepthook` installer** -- accepted,
   built. See below.
2. `why` as a pdb command -- already trivially possible today
   (`why(x)` evaluates fine at a pdb prompt); not a new capability.
3. pytest-style assertion rewriting for plain `assert` -- would need a
   real AST-rewriting import hook, a genuinely new subsystem with real
   risk of breaking other tools' stack traces if done carelessly. Does
   not build on the existing engine; builds a second one next to it.
4. Live diff during a running loop/session -- the CLI `diff` feature's
   problem space wearing a costume, not a new capability.
5. Deeper Sentry/log-aggregator ingestion -- already covered by the
   nine APM-style integrations and `whytrail explain`.
6. A context-manager version of #1, scoped to one block -- still needs
   `with whytrail.explain():` boilerplate, exactly the friction #1
   eliminates. A strictly weaker version of the same idea.
7. VS Code hover tooltips via an LSP server -- would demo well, and is
   exactly what ADR 0005 already assessed and declined ("zero users to
   serve inverts the adoption funnel"), for a reason that hasn't
   changed. Re-litigating a settled decision with no new evidence.
8. Extend Tier 1 to `warnings.warn()` -- warnings carry no
   `__cause__`/`__context__`; there's no causal chain to walk, only the
   call site `stacklevel` already reports. No real "why" to tell.
9. A process-exit aggregate error report -- a batch reporting tool for
   long-running services, not a single 30-second demo moment. Different
   product.
10. A REPL-specific pretty-error mode -- turned out, on checking rather
    than assuming, to be the *same* mechanism as #1: `sys.excepthook`
    was confirmed (not assumed) to fire for both script-mode and
    `python -i` REPL exceptions. Folded into #1 as a demo scenario, not
    a separate idea.

## Decision: `whytrail.install()`, hooking two things, not one

`sys.excepthook` replacement is the well-proven mechanic
(`rich.traceback.install()` is the direct template). What makes this
implementation correct rather than superficially similar:

- **Two hooks, confirmed necessary by testing, not assumed.**
  `sys.excepthook` never fires for an uncaught exception in a worker
  thread -- confirmed directly with a real `threading.Thread`, not
  read from documentation. `threading.excepthook` (Python 3.8+) is the
  separate hook Python itself added for exactly that gap. Installing
  only `sys.excepthook` would silently miss every background-thread
  crash in any threaded server or worker -- a real, common Python
  shape, not an edge case.
- **Adds, never removes.** The original hook still runs after
  whytrail's summary prints -- the full frame-by-frame traceback,
  real information Tier 1's single-dominant-path summary doesn't
  repeat, is never lost. Checked directly: a three-function call chain
  still shows every frame after `install()`, not just whytrail's own
  summary.
- **Redacted by default (`log_locals=False`)**, matching the
  ecosystem-wide convention ADR-adjacent consistency work already
  established (`log_locals`, not `redact` -- see `CHANGELOG.md`'s
  pre-1.0 consistency-audit entry) for exactly the same reason
  `fastapi`/`flask`/`django`/`celery` all default to it: this hook's
  output routinely ends up somewhere whytrail doesn't control
  (journald, a container's stdout capture, a CI log).
- **No new engine work.** `hook.py` calls `why()` and
  `.redacted()`/`.text`/`.plain_text` -- every one of them already
  existed. This is a new *entry point* into Tier 1, not a new
  capability inside it.

## Decision: a sixth top-level name, deliberately

`whytrail/__init__.py`'s own comment has said "deliberately small: five
verbs, two persistence helpers" since ADR 0001. `install`/`uninstall`
break that count on purpose: the entire point of this feature is the
`import whytrail; whytrail.install()` two-liner being the *first*
thing a newcomer sees and types, the same role `rich.traceback.install()`
plays for Rich -- Rich doesn't bury it either (it's a submodule import
there, `from rich.traceback import install`, not `rich.install()`
directly, and that hasn't cost it any of its own fame). Burying this
one behind `from whytrail.hook import install` would undercut the
exact "install it and it just works" experience the feature exists to
deliver. Every other addition this project has made stayed in a
submodule specifically to keep this top-level surface small; this is
the first, deliberate exception, made once, for the one feature this
review explicitly asked to be "the first thing shown in the README."

## Consequences

- `README.md`'s opening section is now this feature, not the two-tier
  explanation (which follows immediately after, unchanged).
- `whytrail/__init__.py`'s `__all__` grows from ten names to twelve;
  the "deliberately small" comment now explains the one exception
  rather than silently drifting from its own claim.
- Nothing existing changes behavior: `install()`/`uninstall()` are
  additive, opt-in, and undone by `uninstall()` if a caller doesn't
  want them active for the rest of a process's life.
- Not hooked: IPython/Jupyter, which replaces its own exception display
  entirely and never calls `sys.excepthook`. Named directly rather than
  silently unclaimed -- `Explanation._repr_html_` already covers
  explicit `why(x)` calls in a notebook, a different mechanism for a
  different environment, not a gap in this one.
