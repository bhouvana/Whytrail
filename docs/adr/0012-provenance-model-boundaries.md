# ADR 0012: What provenance is and isn't -- confirmed via a counterexample sweep

## Status

Accepted. New: `ProvenanceGraph.descendants()` (`src/whytrail/core/graph.py`,
mirrors `ancestors()`), `tests/integration/test_provenance_boundaries.py`
(9 tests, across two passes), 6 new tests in `tests/unit/test_graph.py`
for `descendants()`.

## Context

ADR 0011 asked whether the graph's vocabulary was missing primitives
and found four of six candidates already worked. This ADR asks the
sharper, more falsifiable follow-up: not "could the model express this
more elegantly" but *"is there a real Python debugging scenario the
current graph model (`Node`/`Edge`, `NodeKind`/`EdgeKind`, arbitrary
fan-in/fan-out, confidence) fundamentally cannot represent without
changing the model itself?"* A first pass covered nine scenarios,
chosen for genuine diversity of failure mode (memoization,
async/concurrency boundaries, descriptor protocol, dataclass
composition, ORM identity, process boundaries); a second, more
thorough pass filled in the rest of the originally-proposed list
(generator `.send()`/`.throw()` pinned down with a real test instead
of only cited, plus Pydantic computed fields, Click parameter-source
resolution, Jinja2 template context, and an independent
`weakref.ref()`-based cross-check of whytrail's own tombstoning).
Every scenario was executed for real -- not reasoned about from the
architecture -- before being written down as a finding. `id()` reuse
for non-weakref-capable objects is cited rather than re-tested, since
it was already found, tested, and documented as an accepted limitation
earlier in this project's history (`core/graph.py`'s `_track_identity`
comment).

This is a representative sweep, not an exhaustive one -- fourteen real
tests across two passes is evidence, not proof of completeness. The
finding is reported at that strength, not inflated to "we tested
everything."

## Findings: zero graph-model gaps, two real producer-level nuances

**Representable with no caveat**, verified directly:

1. **Circular references** -- `ancestors()`'s visited-node set already
   makes traversal cycle-safe (ADR 0008 invariant 6); confirmed again
   here for `descendants()` specifically, a separate traversal, not
   assumed to inherit the property.
2. **User-defined `ContextVar` propagation across an async task
   boundary** -- works once explicitly `track()`ed, the same as
   anything else; `trace()`'s own contextvars-based scope propagation
   (`runtime/context.py`) already relies on and proves the same
   Python-level guarantee.
3. **A custom descriptor's `__set__` transforming a value on
   assignment** -- ordinary Python code calling `track()`/
   `derived_from=` explicitly; no descriptor-specific mechanism needed
   or missing.
4. **`dataclasses.__post_init__` deriving one field from several
   others** -- reconfirms ADR 0011's composition finding in a fourth
   shape (multi-parent join from within a dataclass, not just a
   function call).
5. **`asyncio.TaskGroup` running several `@tracked` calls concurrently**
   -- no cross-contamination between tasks' own provenance, confirmed
   directly (not merely inferred from the existing web-framework
   concurrency tests, which don't exercise `@tracked` specifically).
6. **SQLAlchemy's identity map** (`session.get()` twice for the same
   primary key returns the *same* object, not a new query) -- `why()`
   on the second call correctly resolves to the one real tracked node.
   This is the honest answer, not a gap: fabricating a second,
   distinct "identity map hit" event nothing actually recorded would
   be exactly the kind of invented detail ADR §11 exists to prevent.
7. **Crossing a process boundary** -- a *live* `ProvenanceGraph` is
   deliberately not picklable (it holds a real `threading.RLock`);
   `snapshot()`/`restore()` is the sanctioned crossing mechanism and
   already works, confirmed by round-tripping a snapshot string
   through `pickle` the way `multiprocessing.Queue`/`Pipe` actually
   transport data.
8. **Pydantic `@computed_field`** deriving from two independently
   tracked inputs, and **Jinja2 template rendering** combining a
   value passed at render time with one from the template's own
   context -- both reconfirm the composition pattern ADR 0011 already
   established, in two more real, common shapes. No new finding; named
   here because "checked and found nothing new" is still a real result
   worth recording, not silently omitted for being unexciting.
9. **A `weakref.ref()` created independently of whytrail's own
   tracking**, checked against the tracked node's `tombstoned` flag
   after the real object is garbage collected -- confirms whytrail's
   tombstoning isn't just internally self-consistent, but matches an
   independent, external signal that the object is really gone.
10. **Click's `ctx.get_parameter_source()`** (did a CLI option's value
    come from the command line, an environment variable, or its
    default) -- a stronger, independent real-world confirmation of the
    override-semantics pattern ADR 0011 found in `whytrail.config.env()`,
    since Click's own API does the source-tracking here, not
    whytrail's. Both `DEFAULT` and `COMMANDLINE` sources verified
    directly, not just one.
11. **Generator `.send()`/`.throw()`** -- `@tracked`'s own docstring
    already stated these aren't forwarded into the wrapped generator
    body, but nothing had ever pinned that down as a regression test.
    Confirmed directly: sending `10` into a running generator does
    *not* advance its internal state by 10 the way calling the
    undecorated generator would -- the wrapper records the sent value
    as the call's own outcome instead of resuming the body with it,
    exactly as documented. Not a new finding; closes a real gap
    between "documented in prose" and "protected by a test."

**Representable, but with a real, named nuance -- not fundamental, not
built speculatively without evidence anyone's been confused by it:**

12. **Framework-mediated call-site attribution.** `functools.cached_property`
   wrapping `@tracked`, and a `@tracked async def` run inside an
   `asyncio.TaskGroup`, both produce a *causally correct* chain -- but
   the recorded location is the immediate calling frame
   (`_call_site()`'s frame-walking), which in both cases is framework
   dispatch code (`functools.py`'s `__get__`, `asyncio/events.py`'s
   `_run`) rather than the conceptual call site a user would
   recognize. This is ground truth, not a bug -- that genuinely is
   where the call happened -- just not always the most *useful* frame
   to show. Fixing it well would mean heuristically skipping
   known-framework frames, which is fragile and hard to generalize;
   not attempted without a real report that it's confusing anyone.
13. **`functools.lru_cache` cache hits are indistinguishable from real
   computation.** `@tracked` wrapping outside `@lru_cache` records an
   identical-looking `Call` node (same label, same arguments) whether
   the wrapped function's body actually ran or the cache short-circuited
   it -- confirmed directly by counting real invocations against
   `why()`'s output for both calls. Both explanations are true (the
   *call* really happened either way), just not maximally informative.
   `Node.metadata`/`Edge.note` already have room for a `cache_hit`
   marker if a future cache-aware wrapper wanted to record one -- a
   producer-level enhancement, not a graph-model gap, and not built
   without a concrete need.

## Decision: the forward query is confirmed to be a query, not a model change

The previous round's sharper challenge -- can "what does this value
affect" exist as pure traversal, without introducing a new semantic
concept -- is answered directly: yes. `ProvenanceGraph._edges_by_source`
already existed (added for `_evict_if_needed()`'s own bookkeeping,
unrelated to this question); `descendants()` is a structural mirror of
`ancestors()` walking that index forward instead of `_edges_by_target`
backward, with the same breadth-first, max-depth-bounded, cycle-safe
shape. No new `NodeKind`/`EdgeKind`, no change to `add_node`/`add_edge`,
no change to `why()`'s resolution order. Built here, unlike ADR 0011's
deferral of the same idea, because a concrete consumer now exists: this
same sweep's own need (finding 6's sibling scenario, and ADR 0011's
branching example) to demonstrate one value affecting several
independent downstream consumers in a single call, rather than calling
`why()` on each consumer separately and asserting the shared parent
appears in each. `docs/roadmap.md` Phase F's broader "richer queries"
item stays open for anything beyond this one, symmetric case.

## What provenance is, and isn't (the foundational questions)

- **What it is**: an explicit, opt-in record of *derivation* -- which
  recorded facts (a value, an external source, a call) causally
  produced which other recorded fact, with a confidence level attached
  to each link. A typed graph, not a language: `NodeKind`/`EdgeKind`
  are inert labels (ADR 0008 invariant 2), and everything ADR 0011 and
  this ADR demonstrate is a *pattern* of using that graph, not a
  feature the engine specifically understands.
- **What it isn't**: an inference engine, a profiler, or a tracer.
  Nothing is recorded unless a developer opted in for that block of
  code (ADR §09); nothing is guessed at to fill a gap (ADR §11). It
  does not merge graphs across processes (ADR 0001) and does not unify
  Tier 1 (exceptions) and Tier 2 (tracked values) into one mechanism
  (ADR 0008 invariant 4).
- **The guarantee it makes**: every edge in the graph corresponds to a
  real `add_edge()` call a producer made because something real
  happened (a value was passed to a function, a config source was
  checked and used). `why()` never fabricates a link that wasn't
  recorded (ADR §11), and degrades to an honest "unknown" rather than
  guessing (invariant 5).
- **The guarantee it deliberately refuses to make**: that the graph is
  *complete* -- that every causally relevant fact about a value is
  present. Nothing here changes that a value never `track()`ed has no
  provenance at all, and a value tracked once but affecting many things
  only shows what was actually recorded, not everything that
  hypothetically could have been.
- **Why explicit instrumentation instead of inference**: inference
  (sampling, blanket instrumentation) can be wrong in ways a developer
  can't easily audit; an explicit `track()` call is either present or
  it isn't, and its correctness is exactly as verifiable as the rest of
  the surrounding code. This is the same trade-off ADR §09's "off by
  default" contract already made for performance; here it's made for
  trustworthiness.
- **Why confidence instead of certainty**: not every causal link is
  equally certain (an explicit `derived_from` vs. a heuristic guess at
  which of several converging parents mattered most) -- collapsing
  that distinction into one true/false "explained" bit would either
  overstate confidence in a heuristic link or understate it in an
  explicit one. `Confidence` makes the distinction visible instead of
  hiding it (`_steps_from_traversal`'s "weakest link" propagation,
  reconfirmed as real in ADR 0011).
- **Why inert labels instead of a `Producer` class hierarchy or a
  semantically-aware engine**: a hierarchy or semantic engine would
  need to anticipate every future producer's vocabulary in advance;
  inert labels let a brand-new producer (`config.py`, `propagation.py`,
  the `langchain` integration) plug into the exact same graph with zero
  engine changes, proven repeatedly rather than asserted (ADR 0008's
  own audit, ADR 0011's four patterns, this ADR's nine scenarios).
- **Why no hidden causality**: every causal claim `why()` makes traces
  to a real, inspectable `add_edge()` call site in a producer module
  under version control -- there is no runtime inference step whose
  reasoning can't be read as ordinary Python code.

## Consequences

- `ProvenanceGraph.descendants()` is now public API (not exported at
  `whytrail`'s top level, the same visibility level as `ancestors()`
  itself) and tested to the same standard as `ancestors()`.
- Two accepted, non-fundamental limitations (framework-mediated
  location attribution; `lru_cache` cache-hit indistinguishability) are
  now named in one place with regression tests protecting the current,
  correct-if-imperfect behavior from being "fixed" into something
  actually wrong.
- If a tenth scenario is proposed later and found to require an actual
  graph-model change (a new `NodeKind`/`EdgeKind`, a change to
  `why()`'s resolution order), that would be the first one -- this ADR
  is the record to check and update, the same way ADR 0005 is the
  standing answer on the VS Code question.
