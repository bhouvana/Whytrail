# ADR 0001: whytrail architecture

**Status:** Accepted, implemented through the v3.0 buildable slice (see `CHANGELOG.md`).

## Context

The pitch was `why(anything)`: call one function on any Python object and
get back a causal explanation of how it came to be. Before writing any
code, this ADR worked out whether that's actually possible, and if not,
what the largest honest version of it looks like.

## Decision: reject the literal pitch, ship the reframed version

`why(anything)` with zero setup is not achievable. CPython does not retain
provenance for a value once it has been computed -- there is no shadow
ledger of "how did this become 47." The one place causal history *is*
free is exceptions (`__traceback__`, `__cause__`, `__context__`), which no
existing tool fully exploits.

What's built instead is a two-tier model, both answering through one
function:

- **Tier 1 -- zero configuration.** `why(some_exception)` reassembles a
  causal chain from data CPython already retains. Implemented in
  [`whytrail/explainers/builtin.py`](../../src/whytrail/explainers/builtin.py).
- **Tier 2 -- opt-in, scoped.** `why(some_tracked_value)` walks a small
  provenance graph built only for values a developer deliberately watched
  with `track()`, `@tracked`, or `trace()`. Implemented in
  [`whytrail/core/graph.py`](../../src/whytrail/core/graph.py) and
  [`whytrail/runtime/`](../../src/whytrail/runtime/).

Something that was never tracked gets an honest "unknown," never a
fabricated chain. This is enforced structurally: `Explanation` with no
steps says so in its own `.text` (`whytrail/core/explanation.py`), and
`why()` never raises -- a failure anywhere in resolution degrades to
"unknown" rather than propagating into caller code.

`whytrail` also does not claim to do causal inference (Pearl-style
counterfactual reasoning). It answers "what produced this" -- lineage --
not "what would have happened if." Conflating the two was identified as
the single biggest way this project could over-promise.

## Decision: capture mechanism

Compared `sys.settrace`, `sys.monitoring` (PEP 669), AST import-hook
transforms, raw bytecode instrumentation, descriptors, decorators, and
`contextvars` propagation. Chose a hybrid, layered by version:

- **v1 default:** explicit opt-in capture (`track()`, `@tracked`) plus
  `contextvars`-based scope propagation
  ([`whytrail/runtime/context.py`](../../src/whytrail/runtime/context.py),
  [`whytrail/runtime/capture.py`](../../src/whytrail/runtime/capture.py)).
  `contextvars` was required, not optional -- it is the only primitive
  that correctly follows a coroutine across `await` points without
  cross-talk between concurrent tasks.
- **v2 opt-in "deep mode":** `sys.monitoring` (Python 3.12+), gated and
  isolated in [`whytrail/runtime/monitoring.py`](../../src/whytrail/runtime/monitoring.py).
  Auto-instruments calls inside `trace(deep=True)` without requiring
  `@tracked` on every function. Documented, not hidden: PEP 669 events are
  process-wide once enabled, so a deep scope active on one thread also
  fires callbacks for unrelated code on other threads during that window.
- **Rejected outright:** `sys.settrace` (10-100x overhead, incompatible
  with "off by default in production"); raw bytecode instrumentation
  (not a stable interface across Python minors).
- **Deferred, not built:** AST import-hook transforms (a compile-time
  capture mode for modules that opt in) -- real engineering value, but
  lower priority than what shipped, and genuinely a v3+ investment.

## Decision: object explainability protocol

A `__why__(self)` dunder, the same shape as `__repr__` -- opt-in,
duck-typed, no metaclass required. Implemented in
[`whytrail/protocols.py`](../../src/whytrail/protocols.py). Rejected: a
universal transparent proxy to make `__why__` "just work" everywhere --
wrapping changes identity and type, breaking `isinstance` checks and fast
paths in C-optimized libraries (NumPy ufuncs in particular).

## Decision: plugin architecture

Two mechanisms
([`whytrail/registry.py`](../../src/whytrail/registry.py)):

- `register(type, explainer)` -- manual, user-facing, always wins.
- `register_from_plugin(type, explainer)` -- called from a function an entry
  point in the `whytrail.explainers` group points to. Never overrides a
  user's manual registration for the same type.

Validated end to end with a real installable plugin,
[`src/whytrail/integrations/requests.py`](../../src/whytrail/integrations/requests.py)
(bundled as an extra since ADR 0006; this same entry-point mechanism is
still how an *external*, separately-published plugin registers), covered
by
[`tests/plugin_contract/test_requests_plugin.py`](../../tests/plugin_contract/test_requests_plugin.py)
-- these tests exercise the actual `importlib.metadata` entry-point
discovery path, not a mock of the registry.

One correction made during implementation, not anticipated in the
original design pass: exceptions must **not** short-circuit straight to
the tier-1 explainer before the registry gets a look, or a plugin (like
`whytrail-requests`, explaining `RequestException` with method/URL/response
detail) could never run. Resolution order is: `__why__` protocol →
registered explainer (MRO walk) → tier-1 exception explainer as the
built-in fallback for exceptions nothing more specific claims → provenance
graph lookup → honest "unknown."

## Decision: API surface

Public names: `why`, `track`, `tracked`, `trace`, `register`,
`register_from_plugin`, `snapshot`, `restore`. Rejected `why(file)`,
`why(request)`, `why(query)` as separate verbs -- these are different
*types* flowing through the one function, resolved by the plugin
registry, not new top-level names. `why(variable)` (introspecting a
caller's variable by name) was rejected specifically: it requires fragile
frame-hacking and invites exactly the "why(anything) should just work"
expectation §1 above rules out.

## Decision: single dominant path vs. full DAG in output

`Explanation.text`/`.steps` renders one highest-confidence causal path,
not the full captured graph -- discovered as a real design fork during
testing (`trace(deep=True)` on a diamond-shaped call graph). `.graph()`,
`.nodes`, `.edges` carry the complete DAG for anyone who needs it. This is
intentional, not silently lossy: the terse summary optimizes for the
common (linear) case; the full picture is one method call away.

## Decision: what v3.0 actually is

Distributed provenance and a web visualization UI were the stated v3.0
scope. Neither is a library feature -- they need a network service and a
storage backend, i.e. infrastructure, not code that ships in a `pip
install`. What's real and shipped:

- [`whytrail/propagation.py`](../../src/whytrail/propagation.py) --
  `inject()`/`extract()`, shaped like an OTel context propagator, to carry
  "which local causal chain led to this outbound call" across a process
  boundary. There is no transport and no remote graph merge -- the
  receiving side records an honestly-labeled external node
  (`continue_trace()`), not a reconstructed upstream graph.
- [`whytrail/otel.py`](../../src/whytrail/otel.py) -- attaches an
  `Explanation` to the current OpenTelemetry span as an event, so
  existing OTel tooling sees whytrail's causal chain inline with a trace a
  team is already looking at.

Row-level pandas/dask/Spark lineage remains a natural next *plugin*
(following the pattern `whytrail-requests` validates), not core work, and
was not built here.

## Consequences

- Core (`whytrail`) has zero required dependencies. `rich`, `cli`, and
  `otel` are extras; `requests` lives only in the separate
  `whytrail-requests` plugin distribution.
- The public API is small enough to review in one sitting: five core
  verbs plus two persistence helpers.
- `why()` is guaranteed to never raise (`whytrail/__init__.py:_why_impl`
  wrapped in a catch-all in `why()` itself) -- verified in
  `tests/integration/test_why_exceptions.py::test_why_never_raises_even_on_hostile_object`
  and `test_protocol_and_registry.py`'s hostile-`__why__`/broken-explainer
  cases.
- Confidence is tracked on every edge (`EXPLICIT` / `INFERRED` /
  `HEURISTIC` / `UNKNOWN`) and surfaced in `.text`; nothing is presented
  with more certainty than it was captured with.
