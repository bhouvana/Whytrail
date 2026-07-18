# Changelog

All notable changes to this project are documented here. Format loosely
follows [Keep a Changelog](https://keepachangelog.com/).

**Note on the `[0.2.0]` heading below:** every entry between the initial
0.1.0 release and the "unified all 30 plugins into extras" commit was
originally filed under `[Unreleased]`, even after 0.2.0 actually shipped
to PyPI -- the version bump was never paired with converting the
changelog section. Reconstructed retroactively from `git log` (the
commit that bumped `pyproject.toml`'s version is the same one that did
the plugin unification), not from memory of what was released when.

## [0.3.0] - 2026-07-18

### Release-readiness hardening pass

A pre-release audit run specifically to find real gaps rather than
assume there weren't any -- each item below is something the audit
actually caught, not a preemptive rewrite.

- **`ruff` added** (`[tool.ruff]`, `pyproject.toml`) -- this project had
  no linter at all before this pass. Running it cold found a real bug:
  `tests/unit/test_negative_inputs.py` used `BaseExceptionGroup`
  (Python 3.11+, PEP 654) with no version guard, contradicting this
  project's own `requires-python = ">=3.10"` and the CI matrix that
  tests 3.10-3.13 -- a genuine `NameError` on 3.10, never caught
  because no CI job has ever actually run on real infrastructure. Fixed
  with the same `@pytest.mark.skipif` pattern already established in
  `tests/integration/test_why_exceptions.py`. Three more findings were
  real but harmless (dead local variables in
  `explainers/builtin.py`/`tests/unit/test_graph.py`, an ambiguous `l`
  loop variable in `tests/unit/test_explanation.py`); all fixed. A new
  `lint` CI job runs `ruff check` once (Python 3.12 only -- lint
  findings don't vary by OS or interpreter version, unlike the test
  matrix).
- **`mypy --strict` gap closed**: `pyproject.toml`'s mypy `exclude`
  comment claimed `src/whytrail/integrations/` was "checked
  individually in CI instead" -- untrue; no such CI step existed
  anywhere. Added one (`plugin-contract-tests` job, per-extra
  `mypy --strict` on that integration's own module) and fixed the 7 real
  strict-mode errors it surfaced: an unsafe `bytes`-vs-`str` assumption
  in `requests.py` (requests' own stubs type `PreparedRequest.method`/
  `.url` as possibly `bytes`), four bare-generic `dict`/`Callable`
  annotations (`sentry.py`, `prefect.py`, `django.py`) plus an
  `Optional`-shadowing assignment bug in `sentry.py`'s `combined()`, an
  unsafe `exc.param` access in `stripe.py` that only some
  `StripeError` subclasses actually declare, and two third-party-stub
  `untyped-decorator` false positives (`flask.py`, `celery.py`) silenced
  with a targeted `# type: ignore`.
- **Packaging verified for real**: built the actual sdist/wheel,
  `twine check` passed, installed into a genuinely empty venv (nothing
  but `pip` and this wheel) and smoke-tested `--help`, `whytrail demo`,
  and `install()` + `why()` end to end.
- **A real accuracy bug in `whytrail doctor`/`whytrail plugins`**,
  found during that clean-venv smoke test: it reported 12 of 20
  hook-based integrations "importable" with *zero* of their third-party
  dependencies installed. Cause: 11 of the 20 (`bugsnag`, `ddtrace`,
  `elastic_apm`, `flask`, `honeybadger`, `newrelic`, `rollbar`, `rq`,
  `scrapy`, `sentry`, plus `prefect`, which never imports the real
  library at all and relies purely on duck typing) import their real
  dependency lazily inside a function body rather than at module top
  level, so `whytrail.integrations.X` imports cleanly whether or not
  the underlying library is installed -- `list_hook_based_plugins()`
  was checking the wrong thing. Fixed with a new
  `_HOOK_BASED_UNDERLYING_IMPORT` mapping (`registry.py`) from each
  integration to the real top-level package it wraps, checked directly
  instead of trusting the wrapper module's own import. Verified against
  both directions in the clean venv (reports unavailable with the
  dependency absent, flips to available once installed); 2 new
  regression tests in `tests/integration/test_protocol_and_registry.py`.
- **A flaky false positive in `test_redaction_fuzz.py`'s own
  methodology**, found running the full suite after the fix above:
  `test_google_genai_redaction`'s fuzz strategy occasionally generates a
  "secret" that's a contiguous substring of `ClientError` (the
  exception's own class name, always present in the description by
  design) -- e.g. `secret='ClientEr'` -- which trips the "secret must
  never appear in description" assertion for a reason that has nothing
  to do with redaction, the same class of false positive
  `_RESERVED_WORDS` already exists in that file to filter out for
  confidence-marker words. Filtered the same way: excluded from the
  strategy rather than asserted around.

### A counterexample sweep, and `ProvenanceGraph.descendants()` (ADR 0012)

A sharper follow-up to ADR 0011 asked the falsifiable version of the
same question: not "could the model express this more elegantly" but
"is there a real Python debugging scenario the current graph model
fundamentally cannot represent without changing itself?" Nine
scenarios, chosen for genuine diversity of failure mode, each executed
for real before being written down as a finding -- `functools.cached_property`
composed with `@tracked`, `functools.lru_cache` cache hits vs. real
computation, a user-defined `ContextVar` across an async task boundary,
a custom descriptor's `__set__`, a `dataclasses.__post_init__` derived
field, `asyncio.TaskGroup` running concurrent `@tracked` calls,
SQLAlchemy's identity map, and crossing a process boundary (both that a
live graph is deliberately unpicklable, and that `snapshot()` already
solves it). Two more (generator `.send()`/`.throw()`, `id()` reuse for
non-weakref-capable objects) were cited rather than re-tested, since
they were already found and documented earlier in this project's
history.

**Zero scenarios found a real graph-model gap.** Two found a real,
narrow, non-fundamental nuance worth naming and pinning with a
regression test rather than silently leaving undocumented:
framework-mediated calls (a descriptor's `__get__`, `asyncio`'s task
runner) are causally correct but their recorded *location* is the
immediate calling frame, which can be framework internals rather than
the conceptual call site; and `@tracked` wrapping `@functools.lru_cache`
can't currently distinguish a cache hit from a real computation in the
graph (both are true, neither is fabricated, just not maximally
informative). Neither is fixed here -- both are producer-level
questions with no evidence yet that they've confused anyone, not
graph-model limitations.

**A second, more thorough pass filled in the rest of the originally-proposed
list**: Pydantic `@computed_field` and Jinja2 template rendering both
reconfirmed the composition pattern in two more real shapes (no new
finding, recorded anyway -- "checked and found nothing new" is still a
real result); an independent `weakref.ref()` cross-check confirmed
whytrail's own tombstoning matches an external signal, not just its own
internal bookkeeping; Click's `ctx.get_parameter_source()` turned out
to be a stronger, independent real-world confirmation of the
override-semantics pattern than the `config.env()` example alone,
since Click's own API does the source-tracking; and generator
`.send()`/`.throw()`'s already-documented "not forwarded" behavior
(`@tracked`'s own docstring) finally got a permanent regression test,
closing a real gap between "documented in prose" and "protected by a
test." 14 real, executed scenarios total across both passes.

**`ProvenanceGraph.descendants()` added** -- the forward mirror of
`ancestors()` ("what does this value affect," not just "why does this
value exist"), resolving a sharper question from the previous round
directly: confirmed to be pure traversal over an index
(`_edges_by_source`) that already existed, introducing no new
`NodeKind`/`EdgeKind`. `docs/roadmap.md` Phase F had deferred exactly
this twice for lack of a concrete consumer; built now because this same
sweep supplied one (cleanly demonstrating branching in one call instead
of calling `why()` on each downstream consumer separately). Not exposed
at whytrail's top level -- same visibility as `ancestors()` itself.

New: `docs/adr/0012-provenance-model-boundaries.md` (the full sweep,
plus the foundational "what is provenance, what isn't, what guarantees
does it make and refuse to make" reasoning the last two rounds worked
toward), `tests/integration/test_provenance_boundaries.py` (9 tests
across both passes), 6 new tests in `tests/unit/test_graph.py` for
`descendants()`. `click`/`jinja2` added to the `dev` extra as test-only
tools (not whytrail integrations) so these tests actually run in CI's
core `test` job instead of silently skipping. Full test suite and
`mypy --strict` re-run clean (527 passed, 13 skipped, 0 failed; same
pre-existing `otel.py` gap).

### Phase U: the provenance vocabulary is already sufficient (ADR 0011)

A follow-up review pushed the positioning question one level deeper:
not what to *call* the engine, but whether its vocabulary (`Node`/
`Edge`, `NodeKind`/`EdgeKind`) is actually rich enough to describe
causality in general, proposing six candidate "missing primitives"
(transformation, confidence propagation, branching, merging, override,
composition/"provenance algebra") -- explicitly caveated: only keep one
if it's driven by real, already-visible use cases, not invented for
richness's own sake.

Checked each candidate against real, executed code before writing
anything, rather than assuming the review's own (hypothetical) examples
meant something was missing. **Four of six already work today, with
zero new engine code**, each verified by actually running the scenario
and reading the output, not by inspection:

- **Transformation sequences** ("validated, then normalized, then
  clamped") -- `@tracked` on each step already narrates this; the call
  node's label is the function's own name.
- **Confidence propagation** -- already shipped (`Explanation.confidence`
  is the minimum across all steps); confirmed across a three-hop chain
  with three different confidence levels, not just the two already
  covered by `tests/unit/test_explanation.py`.
- **Merge/override semantics** ("why did the final value win, not just
  where it came from") -- `whytrail.config.env()` already does this for
  all three priority levels (environment > `.env` > default), and
  already states *why* the losing sources didn't apply.
- **Composition ("provenance algebra")** -- the review's own most
  exciting example (`Policy(timeout, retry)`, `why(policy)` explaining
  a value "combined from independent provenances") turned out to
  already work exactly as described: `@tracked`'s argument-linking
  already produces this shape, `.text` already flags it ("+N other
  paths converge here, see `.graph()`" -- built for an unrelated
  diamond case, ADR 0002 finding 3), and `.graph()` already shows the
  full two-branch join.

**One candidate (branching, specifically a forward "what does this
value affect" query) is a genuine gap** -- but not a new discovery:
`docs/roadmap.md` Phase F already named this exact idea and marked it
"not started, deliberately," pending a real consumer that still
doesn't exist. Re-affirmed, not built, with the roadmap entry
cross-referencing this round as the second time it's been raised and
deferred for the same reason.

Why none of this needed new `NodeKind`/`EdgeKind` values: ADR 0008's
own invariant 2 already explains it -- the engine treats these as inert
labels it stores and returns without interpreting, so new *patterns* of
using the existing vocabulary (arbitrary fan-out, arbitrary fan-in,
free-text labels) don't require new vocabulary.

New: `docs/adr/0011-provenance-vocabulary-is-already-sufficient.md`
(the full per-primitive analysis), `tests/integration/test_provenance_patterns.py`
(5 tests, each proving one pattern against real output),
`examples/ex_provenance_patterns.py` (runnable demonstration of all
four), a new section in `docs/explanation-engine.md`. Full test suite
and `mypy --strict` re-run clean (513 passed, 13 skipped, 0 failed;
same pre-existing `otel.py` gap).

### Positioning refinement: "why," not "where" (ADR 0010)

A "Phase T" follow-up asked a narrower, harder version of the previous
round's product question: ignoring marketing language, what single
sentence describes whytrail such that it would still be true if every
mention of "exceptions" disappeared, fully supported by what's already
shipped (`why()`, Tier 2 tracked provenance, `whytrail.config`,
snapshots, `Explanation`, `install()`, the integrations) -- not
broadened beyond it? Twenty candidate sentences generated and critiqued
for truthfulness, specificity, uniqueness, credibility, and immediate
understandability; three survived (see `docs/adr/0010-positioning-why-not-where.md`
for all twenty and the critique).

This turned out to refine a decision already on record, not invent a
new one: ADR 0002 ("category strategy") already landed on *"I use
whytrail to find out where a value came from"* as the elevator
sentence. "Where" undersells the actual capability -- it's exactly the
question a traceback, `pdb`, and a log line already answer for free.
The refined framing keeps the same category (provenance, unchanged
since ADR 0002) but sharpens the claim to what's actually distinguishing:
causal derivation of a specific value ("why does this have this
value"), checkable by running `whytrail demo` and comparing the output
to the claim, not a broader promise nothing backs yet.

Applied: `README.md`'s tagline, `pyproject.toml`'s `description`,
`mkdocs.yml`'s `site_description`, the CLI's `--help` text, and
`whytrail/__init__.py`'s module docstring, all previously identical to
the old tagline. `README.md` also gained a short paragraph establishing
this identity before the exception-specific demo, and a one-line
summary ("provenance-first debugging: explicit capture, honest
confidence, never fabricates") placed where the "never fabricate"
guarantee was already discussed.

**`.share()` (a hosted `whytrail.app`), `.coach()`, and `.timeline()`**,
proposed alongside the positioning question, evaluated and declined
(not silently dropped -- see the ADR for the full reasoning): `.share()`
is a different product (a live web service) that ADR 0002 already
named the coherent-but-multi-years-away shape for; `.coach()` mostly
restyles what `Explanation.plain_text`'s existing gloss/fix-suggestion
output already does (shipped 0.2.1); `.timeline()` is more grounded
(`Node.timestamp` already exists) but is a new top-level verb decision
against the same "five verbs, deliberately small" bar `install()` had
to clear, not cleared here without a concrete gap.

No code changes; `whytrail --version`/behavior are unaffected. Full
test suite and `mypy --strict` re-run clean after these edits (508
passed, 13 skipped, 0 failed; same pre-existing `otel.py` gap).

### `whytrail demo`: the zero-code, 30-second first impression

A review pushed for a "Phase S" product-design pass: stop optimizing
engineering rigor, optimize for the first 30-60 seconds after `pip
install whytrail` -- the "oh wow" moment that makes libraries like
Rich/FastAPI/Typer spread, illustrated with several concrete proposed
capabilities (`.coach()`, `.timeline()`, `.share()` to a hosted
`whytrail.app`, a "whytrail demo" CLI command).

Checked against the repo before building anything: the flagship
"oh wow" moment already exists and is already documented as the
project's deliberate answer to exactly this question --
`whytrail.install()` (ADR 0009), explicitly modeled on
`rich.traceback.install()`, already leads `README.md` with real
captured output. The gap wasn't the moment itself; it was that
experiencing it still required writing and running a script
(`examples/ex_install_hook.py`) -- nothing let a brand-new user see it
with zero code of their own, the actual bar this round's own framing
set ("What is the very first thing a user should type... that creates
maximum delight?").

**Built: `whytrail demo`**, a seventh CLI subcommand. Really raises a
two-level exception chain (the same scenario `ex_install_hook.py`
already used) and really calls `why()` on it -- not a canned string.
Renders via `.rich()` (panel) when the `rich` extra is installed,
falling back to plain `.text` otherwise or with `--plain`. `README.md`
and `docs/quickstart.md` both now lead with it, before the two-line
`install()` example that used to be the very first thing shown.

Two real bugs found running this before it shipped, not by reading the
code: the exception's location line pointed into whytrail's own
installed `cli/__main__.py` (`frame.f_code.co_filename` reflects where
a function is *defined*; the demo's scenario functions were nested
inside `_demo()` itself) -- confusing for a user with no idea what that
file is. Fixed by `compile()`/`exec()`-ing the scenario against a
synthetic `<whytrail demo>` filename instead. Separately, printing the
plain-text explanation to stdout while every surrounding line went to
stderr let the two interleave out of order once a caller merged both
streams (`whytrail demo 2>&1`, or certain terminals) -- stdout/stderr
buffer independently. Fixed by putting the whole command's output on
one stream (stderr), matching `_report()`'s existing convention for
`whytrail run`.

**Declined, with reasoning, not silently dropped:**
- **`.share()` (a hosted `whytrail.app` web service)** -- this is a
  different product, not a library feature: standing up and
  maintaining a live web service (hosting, a database, uptime,
  security surface, cost) for a solo-maintained, currently
  zero-required-dependency library. Directly contradicts ADR 0001's
  "zero required dependencies" posture and the same reasoning Phase O
  of `docs/roadmap.md` already used to reject inventing "Enterprise"
  features with no signal behind them.
- **`.coach()`** -- checked against the code first: `Explanation.plain_text`
  already renders a confidence-labeled gloss plus a "How to avoid
  this" line per exception type (`_EXCEPTION_GLOSS`/`_EXCEPTION_FIXES`,
  shipped 0.2.1). A new `.coach()` method would mostly restyle output
  that already exists under a new name, and `whytrail/__init__.py`'s
  own "five verbs, deliberately small" comment (held since ADR 0001,
  broken exactly once so far for `install()`/`uninstall()`, each time
  reasoned through in its own ADR) is the bar a genuinely new verb
  needs to clear -- not cleared here without a concrete gap
  `.plain_text()` doesn't already close.
- **`.timeline()`** -- more grounded than `.coach()` (`Node.timestamp`
  already captures wall-clock time per step, so the data exists), but
  still a new top-level method decision on the same "five verbs" bar.
  Not built speculatively; a real candidate if a specific gap in
  `.graph()`/`.rich()` shows up that timestamps would actually close.

### "Phase R," round two: ten items, explicitly instructed to build all of them

A follow-up review agreed the "engineering weight" reading of the
first Phase R pitch (below) was right to push back on, but reframed
toward depth over volume -- ten categories (chaos engineering, fault
injection, long-running simulations, differential testing, contract
testing, negative testing, performance stability, API invariants,
randomized operation sequences, cross-version compatibility), several
still shaped like generic infrastructure with no target ("a chaos
framework," "a fault-injection framework") rather than concrete tests.
Pushed back again, item by item, against what the code actually shows:
five of ten already exist in some form (contract testing: all 63
integrations + every CLI command + every renderer method, confirmed by
audit, not assumed); a hard performance threshold was flagged as likely
flaky on shared CI runners; "test every function failing" was flagged
as weight, not depth, without a named target. Instructed to build all
ten anyway -- built all ten, but where a specific risk was named, the
concrete/scoped version was built instead of the literal worst case
(a generously-tolerant, history-based performance gate instead of a
fixed microsecond threshold; targeted fault injection at real call
sites instead of a generic framework), each said plainly rather than
silently substituted.

**Every "build" here means real code exercised, not just written** --
this round found and fixed **five real bugs in the library**, not just
in the new tests:

- **`core/graph.py`'s eviction never cleaned up `_object_to_node` or
  `_finalizers`.** `max_nodes` correctly bounded `_nodes` itself, but
  an evicted node whose object was still alive (kept by the caller --
  the normal shape for a long-running process with a cache or a long-
  lived list) left both of these internal dicts growing forever,
  defeating the entire point of bounded retention for exactly the
  scenario it exists for. Found by a soak test tracking 50,000 objects
  into a 1,000-node graph while keeping them all alive: `_nodes` stayed
  at 1,000, `_object_to_node` and `_finalizers` grew to 1,000... after
  the fix; before it, both grew to the full 50,000. Fixed by adding a
  `node_id -> id(obj)` reverse index so eviction can clean up the
  forward mapping in O(1), and canceling (not just discarding) the
  evicted node's `weakref.finalize` registration.
- **`core/serialize.py`'s `loads()` silently dropped any line whose
  `"type"` wasn't exactly `"whytrail_snapshot"`/`"node"`/`"edge"`** --
  directly contradicting its own docstring, which already claimed it
  doesn't "silently drop data it doesn't recognize." Found by a
  negative test constructing exactly that input and getting no error
  and a graph missing the data. Fixed: an unrecognized line type now
  raises `ValueError` naming the snapshot as possibly corrupted,
  consistent with the version-manifest check just above it (which
  already raises loudly on a newer format version rather than
  guessing).
- **Three real bugs in this round's own tests, not in whytrail** --
  named here because each is the kind of Python-semantics mistake
  worth remembering: (1) `requests.Response.text` fell back to
  `charset_normalizer`'s best-guess decoding without an explicit
  `.encoding`, occasionally mangling a Hypothesis-generated secret
  before the redaction check ever ran; (2) a test class used
  `__slots__ = ("n",)` without `"__weakref__"`, silently making every
  instance *not* weakly-referenceable at all -- `weakref.finalize`
  raised `TypeError` for all fifty thousand of them, caught by
  `core/graph.py`'s own `except TypeError: pass`, so the soak test's
  weakref-cleanup assertions were checking nothing; (3) three
  fault-injection tests patched `whytrail.registry.resolve_explainer`
  and expected that to affect `_why_impl`'s behavior -- but `_why_impl`
  (defined in `whytrail/__init__.py`) calls the name `resolve_explainer`
  as bound in *that module's own* namespace via `from .registry import
  ... resolve_explainer`, a separate reference copied at import time,
  not a live alias back to `whytrail.registry`. Two of those three
  tests were `pytest.raises(...)` checks that failed loudly once
  written that way ("DID NOT RAISE"), which is what caught the mistake;
  the third (a truthiness check) had been passing vacuously the whole
  time. All three fixed.

**What was built, item by item:**

1. **Stateful property testing** (`tests/integration/test_stateful_graph.py`):
   a Hypothesis `RuleBasedStateMachine` running randomized
   track/why/snapshot/restore sequences against a real `ProvenanceGraph`,
   checking eviction, tombstoning, and round-trip invariants hold after
   every one. Found a genuine, previously-unverified asymmetry along
   the way (see differential testing, next).
2. **Differential testing**: serialize/deserialize round-trip
   idempotence, folded into the same state machine. The property
   actually is *not* "dump == dump(load(dump))" unconditionally --
   `_restore_node()` unconditionally tombstones every replayed node
   (correctly; a replayed graph never holds live references), so a
   *live* graph's dump legitimately differs from its *restored* dump.
   The true, checked property: once restored, further restore/dump
   cycles are idempotent. Documented directly in `core/serialize.py`.
3. **Negative testing** (`tests/unit/test_negative_inputs.py`): a
   raising/infinitely-recursive `__repr__`, an object with a broken
   `__eq__`/`__hash__`, self-referential exception `__cause__` chains
   (a 1-cycle and a 2-cycle), and a legitimately-deep nested
   `ExceptionGroup` (true self-reference turned out to be
   unconstructable -- `BaseExceptionGroup.exceptions` is read-only).
   Also found, and documented in `_repr.py`: `reprlib.Repr` already has
   its *own* fallback for a raising `__repr__`, one layer below
   `safe_repr`'s -- both are safe, but a test asserting the wrong one's
   output would have been asserting something false about which layer
   actually does the work.
4. **A long-running soak test** (`tests/integration/test_graph_soak.py`):
   50,000 `track()` calls against a 1,000-node graph -- see the bug
   above. Also confirms real garbage collection still tombstones nodes
   correctly at scale, and that 500 rounds of track+snapshot never let
   the graph exceed its cap.
5. **Contract-testing audit**: cross-checked all 63 integrations against
   `tests/plugin_contract/`, every CLI command (`run`/`plugins`/
   `inspect`/`explain`/`diff`/`doctor`) against `tests/integration/test_cli.py`,
   and every `Explanation` renderer (`.text`/`.plain_text`/`.json`/
   `.from_json`/`.redacted`/`.rich`/`._repr_html_`/`.graph`) against
   `tests/unit/test_explanation.py`. All covered already -- nothing
   fabricated to look like new work where the audit found real
   coverage.
6. **Chaos/negative testing for malformed input**
   (`tests/unit/test_chaos_and_recovery.py`): truncated JSON, a node
   payload missing a required field, an unrecognized snapshot line type
   (the bug above), a snapshot missing its version key, `dumps()`
   failing partway through leaving the graph unmutated, a builtin
   explainer whose `register()` raises not breaking the rest, and a
   missing optional dependency not breaking resolution for anything
   else.
7. **Targeted fault injection** (`tests/unit/test_fault_injection.py`):
   `MemoryError`/`RecursionError`/`OSError`/`PermissionError`/
   `ImportError` injected at the real call sites inside `why()`'s own
   implementation (`resolve_explainer`, `explain_exception`,
   `_explain_from_graph`, a plugin's own explainer), confirming ADR
   §19's "never raises" promise holds under each -- and confirming its
   *boundary* just as deliberately: `KeyboardInterrupt`/`SystemExit`
   must still propagate, not get silently swallowed because they fired
   mid-resolution.
8. **API invariants**: `why(obj)` always returns an `Explanation`
   (never raises, `.text`/`.json()`/`.redacted()`/`.graph()` all stay
   callable) across 15 pathological inputs -- `None`, a generator, a
   self-referential object graph (distinct from a self-referential
   *list*, which CPython's own repr already guards), invalid-UTF-8
   bytes, `nan`/`inf`, `NotImplemented`, a bare class object, and the
   negative-testing objects above.
9. **A real performance regression gate** (`ci.yml`'s `benchmarks` job):
   no fixed threshold ("`track()` must stay under 3us forever" was
   rejected the same way `docs/roadmap.md` Phase G already rejected it)
   -- instead, `.benchmarks/` history cached across runs on the same
   OS/Python combination via `actions/cache`, compared via
   `pytest-benchmark`'s own `--benchmark-compare-fail=min:400%` (fails
   only past a 5x slowdown, comfortably below the ~100x regression this
   suite's own history already caught once, comfortably above normal
   runner-to-run noise). No baseline committed to the repo: one
   generated in this (Windows) sandbox would sit under a different
   machine-info bucket than `ubuntu-latest` and never be matched.
10. **A cross-version snapshot harness**, folded into
    `tests/unit/test_chaos_and_recovery.py`: there's exactly one
    snapshot format version that has ever existed, so there's no
    historical corpus to restore yet -- the harness checks what's
    real today (current version round-trips, a legacy pre-versioning
    snapshot still loads, a fabricated future version is rejected, a
    manifest missing its version key defaults correctly) and is ready
    for a real second version whenever one ships.
11. **Mutation testing**: `mutmut` (no native Windows support --
    confirmed directly, not assumed -- run via WSL this session, added
    to `ci.yml` as a weekly, informational job on `ubuntu-latest`
    instead). Scoped to `src/whytrail/core` via `pyproject.toml`'s new
    `[tool.mutmut]` section (`also_copy` lists the rest of the
    top-level package so `import whytrail` still resolves in mutmut's
    isolated sandbox, without mutating the 63 integrations or the CLI).
    **450 mutants generated against `core/`; 128 initially survived.**
    Investigated the highest-value ones first -- `core/graph.py`'s
    eviction bookkeeping (the same function just fixed above) and
    `core/serialize.py`'s field-by-field round-trip -- and fixed eight
    real gaps, each verified by re-running that specific mutant against
    the new test and confirming it now dies:
    - Three in `_evict_if_needed()`: a wrong dict key in an
      `_edges_by_source.pop(...)` call, an inverted `in`/`not in`
      condition that would keep exactly the wrong edges in `self._edges`
      after eviction, and an `and`/`or` swap that would let eviction
      delete an `_object_to_node` entry a *newer* node had since claimed
      (the id()-reuse safety case the surrounding code's own comment
      already named).
    - Five in `core/serialize.py`: `_restore_node()`/`_restore_edge()`
      silently defaulting `timestamp`/`confidence` instead of reading
      them from the payload, and `_json_safe()`'s try/except never
      actually being exercised by any test with a genuinely
      non-JSON-serializable metadata value -- the existing round-trip
      test only checked node labels and (source, target, kind) edge
      tuples, not every field.
    One investigated mutant (`OrderedDict.popitem(last=None)` in place
    of `last=False`) is a confirmed *equivalent* mutant, not a gap --
    `None` and `False` are both falsy, so `popitem` behaves identically
    either way; documented as such rather than chased with a pointless
    test. The remaining ~119 survivors, sampled rather than exhaustively
    triaged given the volume, are concentrated in `core/explanation.py`'s
    rendering helpers (`_confidence_style`, `_locals_table`,
    `_location_link`, `_plain_location`, and similar) -- existing tests
    verify rendered *behavior* (tree structure, which labels appear) but
    not every exact-value mapping or string-formatting decision inside
    them, and at least one sampled survivor there
    (`_plain_location`'s `rsplit("\\", 1)` vs. `rsplit("\\")`) is also
    confirmed equivalent (`[-1]` after either call returns the same
    element). Left as a real, named, uninvestigated remainder rather
    than mechanically writing ~119 more tests to force a 0-survivor
    count -- the weekly CI job keeps this checked going forward, the
    same "informational, not exhaustively resolved in one pass" standard
    `docs/testing-maturity.md` already applies to the plugin-version
    matrix's first CI run.

Full test suite: 505 passed, 13 skipped, 0 failed. `mypy --strict`
clean except the pre-existing, unrelated `otel.py` gap.

### "Phase R" pushback, then four evidence-gated testing-rigor items actually shipped

A review pushed for "industrial-grade engineering": stop adding
features, spend the next phase on mutation testing, memory-leak
instrumentation, concurrency torture tests, fuzzing every renderer,
stateful state-machine testing of the full track/snapshot/restore/diff
lifecycle, hundreds of new tests as a target in itself -- explicitly
modeled on httpx/SQLAlchemy/Rich/pytest's engineering culture. Checked
against this project's own `docs/testing-maturity.md` and
`docs/roadmap.md` first, the same way every prior "chief architect"
style pitch has been: most of what was asked for already existed,
scoped and evidence-gated (Hypothesis property-fuzzing since the 0.3
redaction-fuzz work, concurrency load tests for the web frameworks,
a real version-compatibility matrix that already found 20 bugs, a
benchmarks job, a full API-stability audit). What the pitch added
beyond that -- mutation testing, memory-leak profiling, fuzzing across
every renderer, stateful lifecycle testing -- traced to no actual bug,
named gap, or user report; `docs/roadmap.md`'s own opening line already
rejects "padding out with speculative work to look complete" as a
standard, and building all of it now would apply a lower evidence bar
to this project's own testing effort than it holds every plugin and
feature to.

Offered instead: pick from the gaps `docs/testing-maturity.md` and
`docs/roadmap.md` already name. Given "get all of these done, not just
one" -- all four shipped, same quality bar as everything else in this
document (real verification, bugs found fixed inline, nothing padded):

- **Redaction property-fuzzing widened from 11 targets to 22**
  (`tests/plugin_contract/test_redaction_fuzz.py`): `anthropic`,
  `psycopg`, `pymysql`, `pymssql`, `clickhouse`, `snowflake`,
  `influxdb`, `graphql-core`, `google-genai`, `requests`, `httpx`.
  Checked each candidate against its plugin's own source before writing
  a test, per this project's standing practice -- `boto3`, `aiohttp`,
  and `marshmallow` turned out to have no redaction-critical field to
  fuzz at all (each plugin's own docstring already says so: `boto3`'s
  `.response` never carries request params, `aiohttp`'s response body
  isn't accessible by the time it raises, `marshmallow`'s messages
  never embed the actual bad value), and `oracledb` is excluded for the
  same reason `grpcio`/Prefect already were in this file (its exception
  can only be constructed via a real per-example connection attempt,
  not a free-standing object). Two real bugs found running the new
  tests, both in the tests, not in whytrail: `requests.Response.text`
  fell back to `charset_normalizer`'s best-guess decoding without an
  explicit encoding, occasionally mangling the generated secret before
  the redaction check ever ran; and a `google-genai` test referenced
  `except ... as exc` outside the `except` block, hitting Python's
  implicit `del exc` at block-exit (`UnboundLocalError`) -- fixed by
  returning from inside the block, the same pattern the corresponding
  single-value test already used.
- **Concurrency testing extended to the task-queue and observability
  integrations** (`tests/plugin_contract/test_task_queue_concurrency.py`,
  `test_observability_concurrency.py`): Celery, dramatiq, RQ, Sentry,
  ddtrace, and OTel, using the same "N concurrent calls, each carrying
  a unique secret, assert no cross-contamination" pattern
  `test_web_concurrency.py` already established, with `log_locals=True`/
  `include_locals=True` throughout -- the default `log_locals=False`
  redacts every secret away entirely, which would make a
  cross-contamination check vacuously pass regardless of whether
  isolation actually held. dramatiq's real `Worker` thread pool gives
  genuine concurrency; RQ's `SimpleWorker` is deliberately
  single-threaded (by design, for test safety -- same reasoning
  `test_rq_plugin.py` already documents), so what's tested there is
  whytrail's own installed exception-handler function called
  concurrently via a stub worker, the actual whytrail-owned code with
  any shared-state risk. Prefect is deliberately not included:
  `whytrail.integrations.prefect`'s own module docstring already states
  it doesn't capture task arguments the way the other three do, so
  there's no locals-bearing state for a cross-contamination test to
  meaningfully exercise.
- **Plugin-version-matrix's Python coverage extended from 3.13-only to
  3.10-3.13** (`plugin-version-matrix-py-range` in `ci.yml`): every
  extra's *original* `pyproject.toml`-stated floor (not the
  3.13-corrected floor the existing job pins) against Python
  3.10/3.11/3.12 -- 186 jobs (62 extras x 3 versions). Deliberately
  gated to the same weekly `schedule` trigger `plugin-version-matrix`
  already runs on, not every push: `docs/roadmap.md` Phase H already
  names the cost tradeoff directly ("every additional Python version
  roughly multiplies plugin-version-matrix's job count"), and a
  dependency's stated floor changes rarely enough that weekly detection
  is the right call. Floor-only, not floor+latest -- "latest" isn't a
  per-Python-version claim `pyproject.toml` makes, so there's no stated
  claim to verify that way. As of this writing the job has been added
  but never actually run on real CI; per this project's own standard
  (see `docs/testing-maturity.md`'s "confirmed working" vs. "works in
  any condition" distinction), that means the mechanism exists, not
  that 3.10-3.12 are confirmed -- update the docs once it has actually
  run.
- **`CONTRIBUTING.md` added**, ahead of Phase K's stated trigger for a
  fuller governance process (a second maintainer), scoped to what's
  actually true today: the "write the regression test that fails
  before writing the fix" rule this project already followed for every
  bug in this changelog, written down explicitly for the first time,
  plus pointers to the existing plugin-guide/ADR conventions. Says
  directly that it isn't a complete governance process.

Full test suite: 453 passed, 13 skipped (extras not installed in this
environment), 0 failed. `mypy --strict` clean except the pre-existing,
unrelated `otel.py` gap.

### `whytrail.install()`: the flagship feature (ADR 0009)

A review asked for something categorically different from the last
several rounds of audits: not "what's missing," but "the single
capability that makes an experienced engineer install this after a
30-second demo" -- explicitly modeled on Rich's pretty tracebacks,
pytest's assertion rewriting, Pydantic's validation-from-type-hints.
Ten candidates generated and critiqued; nine rejected (full reasoning
in `docs/adr/0009-install-hook-flagship-feature.md`, including why an
LSP/VS Code idea was declined again for the same reason ADR 0005
already gave, and why AST-based assertion rewriting was rejected as a
second subsystem rather than a use of the existing one). One built.

**`whytrail.install()`** replaces `sys.excepthook` *and*
`threading.excepthook` so every uncaught exception in a process --
main thread, background thread, or the interactive REPL -- prints
`why()` first, then the original traceback, unchanged. Two lines,
zero new engine work: Tier 1 already reconstructs the causal chain
from `__traceback__`/`__cause__`/`__context__`; this is a new
*entry point* into it, not a new capability inside it.

Two real gaps checked directly, not assumed, before shipping:

- **`threading.excepthook` is a separate hook from `sys.excepthook`**,
  confirmed with a real `threading.Thread` -- an uncaught exception in
  a worker thread never reaches `sys.excepthook` at all. Installing
  only the main-thread hook would silently miss every background-
  thread crash in any threaded server or worker, a real, common Python
  shape. Both are hooked.
- **`sys.excepthook` fires for the interactive REPL too**, confirmed
  with a real `python -i` session, not assumed from documentation --
  the demo works identically whether the exception came from a script
  or someone experimenting at a prompt.

Locals redacted by default (`log_locals=False`) -- naming and polarity
match the ecosystem-wide convention the previous round's consistency
audit just established, for the same reason `fastapi`/`flask`/
`django`/`celery` all default to it: this hook's output routinely ends
up somewhere off-box (journald, a container's stdout capture, a CI
log) whytrail doesn't control. `plain=True` renders via `.plain_text`
instead of `.text`. `uninstall()` restores whatever hooks were active
before, verified safe to call even if `install()` was never called.

`install`/`uninstall` are a deliberate sixth and seventh top-level
name -- `whytrail/__init__.py`'s own "deliberately small: five verbs,
two persistence helpers" comment has held since ADR 0001. Not
accidental scope creep: the whole point of this feature is
`import whytrail; whytrail.install()` being the first thing a
newcomer types, the same role `rich.traceback.install()` plays for
Rich (itself a submodule import, not `rich.install()` -- burying this
one behind a submodule import would undercut exactly the experience it
exists to deliver).

Not hooked: IPython/Jupyter, which replaces its own exception display
and never calls `sys.excepthook` -- named directly rather than left
silently unclaimed. `Explanation._repr_html_` already covers explicit
`why(x)` calls in a notebook; that's a different mechanism for a
different environment, not a gap here.

`README.md`'s opening section is now this feature (with real, verified
output -- captured by actually running the demo script, not
hand-typed), followed immediately by the existing two-tier
explanation. `docs/quickstart.md` gained a new "see it immediately"
step 2, everything after it renumbered. New example:
`examples/ex_install_hook.py`. 12 new tests
(`tests/unit/test_hook.py`), including one proving the full
multi-frame traceback still prints in full after `install()` -- adds,
never removes. 404 tests total, `mypy --strict` clean.

### Pre-1.0 consistency audit: three real naming inconsistencies, all fixed

Asked to review every public API, integration, CLI command, renderer,
and plugin as though changing any of it later would be expensive --
"pretend Whytrail has 10,000 active users" -- and fix the highest-
impact simplification. Three real findings; the first two fixed
immediately, the third initially deferred as lower-impact and then
fixed on explicit follow-up request.

- **`redact` vs `log_locals`.** Every integration written before this
  session (`celery`, `dramatiq`, `rq`, and the `log_locals` half of
  `fastapi`/`flask`/`django`'s two-opt-in design) uses
  `log_locals: bool = False` -- locals redacted unless explicitly
  opted in. The three logging integrations added this session
  (`logging`, `structlog`, `loguru`) instead used `redact: bool =
  True` for the exact same concept -- a different name *and* inverted
  polarity, introduced because each module was written and verified in
  isolation without cross-checking the rest of the ecosystem's own
  convention. A user moving from `whytrail-celery` to
  `whytrail-logging` would have hit a parameter that means the same
  thing but reads backwards. Renamed to `log_locals: bool = False` in
  all three, tests updated to match, verified against real objects
  again after the rename (not just mypy-checked).

- **`"hook"` vs `"integration"`.** `docs/plugin-guide.md`'s own
  "Shape" column, and `pyproject.toml`'s own "Integration-shaped"
  extras comment, already established `explainer`/`integration` as the
  two-shape vocabulary for this ecosystem. `registry.PluginStatus.kind`
  and the `whytrail plugins --json` output instead used `"hook"` -- a
  third term for the same taxonomy, introduced the same way as the
  finding above (written fresh this session, not cross-checked). This
  one is a public, machine-readable contract (`whytrail plugins
  --json`'s `"hook"` key, and the `PluginStatus.kind` field anyone
  calling `registry.list_hook_based_plugins()` directly would see) --
  exactly the kind of thing genuinely expensive to rename once a real
  script depends on it, which is why it's fixed now rather than left
  for after 1.0. Renamed to `"integration"` throughout: the JSON key,
  the `kind` field's value, the CLI's human-readable "Hook-based" label
  (now "Integration-shaped"), and every test asserting the old string.
  `list_hook_based_plugins()`'s function name is intentionally
  unchanged -- "hook-based" remains accurate, established prose for
  *how* these integrations work (the same phrase `docs/plugin-guide.md`
  itself uses in prose); only the terse category label needed to match
  the table's own vocabulary.

- **Found, initially deferred, then fixed on request**: `whytrail.config.ConfigError`
  lived in the same module as the function that raises it
  (`whytrail.config.env()`), but `SnapshotVersionError` didn't -- it
  was two levels deeper than the top-level `whytrail.snapshot()`/
  `restore()` functions that can raise it, in `whytrail.core.serialize`.
  Left out of the first pass as lower-impact than the two above (one
  exception type, one catch site, not a JSON contract or a
  cross-ecosystem naming pattern) -- asked for explicitly afterward,
  so fixed the same way: `SnapshotVersionError` is now importable
  directly as `whytrail.SnapshotVersionError`, the exact same class
  object as `whytrail.core.serialize.SnapshotVersionError` (re-exported,
  not duplicated, so both spellings catch the same exception).
  `restore()`'s docstring now says so. One new test
  (`tests/unit/test_serialize.py`) pins that the two names refer to
  the same class, not just that both happen to work.

392 tests now passing, `mypy --strict` clean. No behavior change for
existing callers either way: the first two fixes only affect code that
explicitly passed the old parameter name or read the old string value;
the third is purely additive (a new import path to the same class,
nothing removed or renamed).

### The rest of "Phase I": logging integrations, richer rendering, Jupyter, and four new CLI commands

Follow-on to the pytest-only round below: asked to implement every
item from the reviewed "Phase I" list, not just the highest-value one.
Six areas shipped, each reusing existing public API (`Explanation`'s
own fields, `registry.list_*`, `core.graph`/`core.serialize`) rather
than adding new engine concepts -- 391 tests total (up from 342),
`mypy --strict` clean.

- **Three new logging integrations**, all real, all hook-based (ADR
  0006 shape), none touching the engine:
  - `whytrail.integrations.logging` -- a `logging.Filter` appending an
    explanation to any record with `exc_info`. No extra needed
    (stdlib only).
  - `whytrail.integrations.structlog` -- a processor adding a
    structured `why` key to the event dict, must run before
    `format_exc_info` in the chain.
  - `whytrail.integrations.loguru` -- `logger.patch()`-based, appends
    to the message so it reaches whatever sink(s) are already
    configured rather than requiring a new one.
  - All three: locals redacted by default (`redact=True`), verified
    against a real logger/real exception in each case, not mocked.
    9 extra 3rd-party packages (`structlog`, `loguru`, `IPython`)
    installed in the dev environment specifically to test these and
    the Jupyter work below against real objects, per ADR 0003's own
    bar.

- **`Explanation.rich()` got real upgrades, kept its return type.**
  Locals now render as a `rich.table.Table` (name/value columns)
  instead of one flat string; a step's `file:line` location renders as
  a best-effort clickable `file://` link (degrades to identical plain
  text where a terminal doesn't support it). New `panel=True` kwarg
  wraps the result in a `rich.panel.Panel` -- opt-in, so the *default*
  return type is still exactly `rich.tree.Tree`, unchanged from before
  0.3 (checked deliberately: `.rich()`'s return type is documented in
  README/quickstart as `rich.tree.Tree`, and changing it by default
  would have been a real breaking change to already-public API).

- **`WhytrailMiddleware`** added to `whytrail.integrations.fastapi`,
  alongside (not replacing) `install()` -- `app.add_middleware(WhytrailMiddleware)`
  for apps that standardize on that Starlette convention over
  `add_exception_handler`. Both share one `_explain_and_respond()`
  helper now, pinned by a test asserting they produce identical
  response bodies, not just independently-passing tests.

- **Jupyter/IPython**: `Explanation._repr_html_()`, pure stdlib (no
  `rich`/`IPython` import in the implementation -- core's
  zero-required-dependencies contract holds). Confirmed against real
  `IPython.core.formatters.HTMLFormatter`, not just called directly.
  `Explanation.from_json()` added alongside it -- the reverse of
  `.json()`, needed by `whytrail explain` below, and reused there
  rather than duplicated.

- **Four new CLI commands** (`inspect`, `explain`, `diff`, `doctor`),
  on top of `run`/`plugins`. `ProvenanceGraph.all_nodes()`/
  `all_edges()` added to `core/graph.py` first -- nothing public could
  enumerate a whole graph before (`node_for`/`get`/`ancestors` all
  start from one known node or object), and ADR 0008 named
  `core/serialize.py` as the *one* deliberate exception to "consumers
  use only the public API"; a second private-access workaround for the
  CLI would have quietly eroded that invariant instead of extending it
  properly.
  - `whytrail inspect snapshot.json` -- node/edge counts by kind.
  - `whytrail explain explanation.json` -- re-renders a
    `whytrail run --json` output via `Explanation.from_json()`; never
    fabricates `nodes`/`edges` that `.json()` never serialized in the
    first place.
  - `whytrail diff before.json after.json` -- compares two snapshots
    by `(kind, label)` (node IDs aren't stable across independent
    captures); reports added/removed, not a guessed-at "changed"
    category, since whytrail has no stable identity to match two
    differently-labeled nodes across captures without fabricating one.
    **Caught by its own test, not written speculatively**: the first
    version of the test wrote "before" and "after" to the same
    long-lived shared default graph without clearing it between
    phases, so "after" was a superset of "before" within one process
    and nothing showed as removed -- correct behavior, wrong test.
    Fixed the test, and added a `description` to `diff --help`
    clarifying that it compares *independent* captures, not two
    snapshot() calls seconds apart in the same live process.
  - `whytrail doctor` -- Python/whytrail version, `rich` extra
    presence, plugin counts, via `registry.list_*` -- all read-only
    introspection over what already existed.

- **A real, narrow bug found writing `inspect`, not shipped**: the
  first version showed a "tombstoned node count" for a snapshot.
  `core/serialize.py`'s own docstring already says every replayed node
  is unconditionally tombstoned (no live object references survive
  serialization) -- so that count would always read 100%, in every
  snapshot, forever, looking like a signal when it's actually a
  constant. Removed before it shipped, not after.

Docs updated to match: `docs/plugin-guide.md`'s integration table (63,
not 60), `docs/testing-maturity.md`'s test/plugin counts (391/63) and
fuzz-coverage count (11 plugins, not 9 -- `track()`/`config.env()`
added to `test_redaction_fuzz.py` alongside the pytest-round's fixes),
README's ecosystem count and `whytrail plugins` example output, three
new runnable examples (`examples/ex_logging.py`, `ex_structlog.py`,
`ex_loguru.py`, each executed and verified before being committed).

### whytrail-pytest now surfaces track()ed values, not just the bare exception

A review proposed a "Phase I -- Production-Grade Integrations" list
(logging/structlog/loguru, Rich rendering, pytest, FastAPI middleware,
Jupyter, a richer CLI), naming `whytrail-pytest` as the single
highest-priority build. Checked the premise against the actual
package first, since three of the six were already shipped, not
missing:

- **pytest**: `whytrail/integrations/pytest_plugin.py` already existed
  (ADR 0002 §7), auto-registers via the `pytest11` entry point, and
  already attaches a zero-boilerplate "whytrail" section to every
  failure report -- exactly the "no manual calls, no boilerplate"
  experience proposed, already true before this round.
- **FastAPI**: `whytrail/integrations/fastapi.py` already existed,
  already a one-call `install(app)` (via `add_exception_handler`,
  arguably more idiomatic than the proposed `add_middleware` for
  catching app-level exceptions), already safe-by-default with the
  two-opt-in response/log design `SECURITY.md` names directly.
- **Rich rendering**: `Explanation.rich()` already existed, returning
  a `rich.tree.Tree` since early in this project.

Genuinely missing, confirmed by grep: a `logging`/`structlog`/
`loguru` integration, and Jupyter/IPython display hooks
(`_repr_html_`/`_repr_mimebundle_` -- none exist anywhere in the
package). Not built this round -- named, not silently dropped.

**The real gap, found by testing the existing pytest plugin against
the review's own phrasing ("include whytrail output *for tracked
values*")**: Tier 1 (the exception explanation `pytest_plugin.py`
already attached) never consults the provenance graph, by design (ADR
0008's invariant 4) -- so a value that failed an assertion and was
*also* `track()`ed only ever explained "AssertionError at this line,"
never where that value actually came from. Fixed by having
`pytest_exception_interact` additionally check whether any local at
the failing assertion's frame was separately tracked and, if so,
append that local's own `why()` -- not a new plugin, four lines and a
loop added to the existing hook. Confirmed real, not speculative, by
running it: a test asserting on a `track()`ed, `derived_from`-chained
value now shows the value's full derivation (`raw CSV row -> 12.5`)
alongside the bare `assert 12.5 == 999` a plain traceback (or the
pre-0.3 whytrail section) would have shown instead. 3 new tests
(`tests/plugin_contract/test_pytest_plugin.py`), a new runnable
example (`examples/ex_pytest_tracked_values.py`).

No redaction change needed for this: pytest failure reports already
showed Tier 1's locals unredacted (a local developer-facing artifact,
same convention pytest's own assertion rewriting already follows) --
this extends the same existing convention to Tier 2 locals, not a new
one.

### Debugging-experience audit: `--json`/`--graph` were silently no-ops in the natural word order

Follow-on to the semantic-completeness audit below: rather than more
engine/language-edge-case work, audited 25 realistic production
debugging questions against real whytrail behavior ("why is this
None," "where did this config come from," "can I share this without
leaking secrets," "did this get retried," ...) and found most already
answered elegantly by what's already shipped (`why()`, `.redacted()`,
`whytrail.config`, `whytrail plugins`, `whytrail-tenacity`'s
`RetryError` explainer). One finding stood out as a real, severe bug
rather than a missing nice-to-have.

**`whytrail run script.py --json` (and `--graph`) silently did
nothing** -- confirmed, not hypothetical. `script_args` uses
`nargs=argparse.REMAINDER` so a script's own flags reach it unmolested
(`whytrail run script.py --verbose` must pass `--verbose` through, not
swallow it) -- but that same mechanism swallows `--json`/`--graph`
too when they're placed *after* the script path, which is both the
natural order and the one this project's own README prose implied. No
error, no different exit code, no different-looking output: the
explanation just prints as plain text instead of JSON. For a CI script
piping the output into a JSON parser, that's a silent failure with no
clue why. The CLI's own `--help` usage string already hints at the one
order that works (`whytrail run [-h] [--json] [--graph] script ...`)
but never explains why the other one fails.

Fixed by making the silence visible, not by guessing what the user
meant: `_warn_about_swallowed_flags()` prints a stderr note (with the
corrected command) whenever `--json`/`--graph` shows up in the
REMAINDER-captured `script_args` -- and does *not* reinterpret or
block it, since a script might genuinely want a literal `--json`
argument of its own. `README.md`'s CLI section now shows the correct,
verified-working order as a copy-pasteable example instead of
ambiguous prose. 7 new tests in `tests/integration/test_cli.py`,
including one proving the warning doesn't change behavior for a script
that wants its own `--json` argument.

Everything else from the 25-question audit either already works
elegantly (not re-described here, see the full table in this round's
report) or maps to gaps already named in `docs/roadmap.md` Phase F
(snapshot diffing, nested-container provenance) -- nothing new added
to that list.

### Python semantic completeness audit: generators/async generators fixed, ~20 other areas verified

Follow-on to the async `@tracked` fix below: audit whether the same
bug class (calling a coroutine function returns a coroutine, not a
result) recurs anywhere else in `runtime/capture.py`, then verify
`@tracked`/`track()`/Tier 1 against a wide swath of Python's runtime
semantics -- exceptions, async, generators, context managers,
dataclasses/attrs/copy, functools, descriptors, containers,
serialization, threading, memory -- each checked by running real code,
not by inspection alone.

**Confirmed and fixed: the exact same bug, for generator and async
generator functions.** `@tracked` on a `def ...: yield` or `async def
...: yield` function tracked the *generator object* (created
immediately, before any code runs), never the values it actually
yields -- `why()` on a real yielded value came back "unknown," same as
the coroutine bug. Fixed with two more wrapper variants
(`inspect.isgeneratorfunction`/`isasyncgenfunction`), each tracking
every yielded value as its own node derived from the call, and
correctly linking an exception raised partway through iteration.
Deliberately scoped: `.send()`/`.throw()` are not forwarded into the
wrapped generator (recorded as this call's own outcome instead,
documented in `tracked()`'s docstring) -- full bidirectional-generator
protocol fidelity would need a materially more complex wrapper for a
usage pattern `@tracked` has no evidence anyone relies on. Plain
iteration (`for`, `list(...)`, `async for`) -- the common case, and
the one every yielded value needs a node for -- is fully supported,
including correct `.close()` propagation into the wrapped generator
(verified: CPython's own refcounting cleanup handles this without any
extra code). 4 new tests in `tests/integration/test_why_tracking.py`.

**Verified correct, not gaps:** `Explanation`/`Node`/`Edge` pickle
correctly (plain dataclasses, no special-casing needed); Tier 1
explains `SystemExit`/`KeyboardInterrupt`/`CancelledError` correctly
(typed as `BaseException` throughout, no `Exception`-only assumption
anywhere); `@tracked` stacked with `functools.lru_cache` works
(`inspect.signature` sees through `functools.wraps`); a `trace()`
scope correctly propagates into `asyncio.gather`/`create_task`'d tasks
(contextvars are copied per-task by asyncio itself -- confirmed the
exact mechanism ADR 0001 chose for this reason actually delivers);
`asyncio.CancelledError` during a tracked async call is recorded like
any other exception, which is the honest, correct behavior, not a
special case to add.

**Named, not fixed, both cosmetic/narrow:** an unconsumed, infinite
`@tracked` generator left open until interpreter shutdown can print an
"Exception ignored" message from `weakref.finalize` failing during
Python's own teardown (`sys.meta_path is None`) -- confirmed
shutdown-specific; explicit `.close()` during normal execution is
unaffected. Fixing it well means broadening `core/graph.py`'s
exception handling for a narrow, output-only edge case with no effect
on program behavior -- not done here, named so it isn't silently
unknown either.

**Categories checked and found not applicable** -- typing constructs
(`Generic`/`Protocol`/`TypedDict`/etc. have no runtime behavior for
`track()` to get wrong), the import system, multiprocessing (`spawn`/
`fork`, explicitly out of scope per ADR 0001's rejection of
distributed-tracing infrastructure), descriptors/properties (no
special interaction with `@tracked`, confirmed by the `functools`
check above covering the same code path) -- named directly rather than
silently skipped, so "was this checked" has a real answer.

Nested-container element-level provenance, snapshot diffing, and
source-code line context (already named in `docs/roadmap.md` Phase F
from the prior round) remain the honest list of what's still open;
nothing new was added to it by this audit.

### Core hardening: snapshot versioning, a real redaction bug, async @tracked

A pushback-and-pivot round: an external review pushed for speculative
"HTTPX-level depth" (graph forking, transactions, a query engine) with
no real user pressure behind any of it. Declined, for reasons already
on record (ADR 0001, ADR 0008, `docs/roadmap.md`'s repeated "no signal
yet" calls) -- and the review agreed once shown the reasoning, landing
on a better question instead: audit for *real* capability gaps,
justified by an existing public API, a Python language feature, or a
realistic workflow, not by hypothetical future integrations. Four
things shipped from that audit, two of them real bugs caught mid-fix,
not just features added:

- **Snapshot format versioning** (`core/serialize.py`). `snapshot()`/
  `restore()` were already public API with no way to detect an
  incompatible future format change at load time. A leading manifest
  line now carries `SNAPSHOT_FORMAT_VERSION`; a too-new snapshot
  raises `SnapshotVersionError` with a clear message instead of a
  confusing `KeyError` or silently wrong data. Snapshots written
  before this change (no manifest line at all) still load exactly as
  before -- forward insurance, not a breaking change. Also closed a
  real gap found while writing this: `snapshot()`/`restore()` had zero
  dedicated tests anywhere in the suite despite being public since
  v2.0; `tests/unit/test_serialize.py` now covers round-tripping,
  backward compatibility, and the new version check.

- **A real security bug in `Explanation.redacted()`, found auditing
  the file the review asked to audit.** `.redacted()`'s docstring
  claims "safe to share off-box," but it only ever stripped
  `ExplanationStep.locals`. `track()`'s node label defaults to the
  tracked value's own `repr()` (`runtime/capture.py`), and
  `.redacted()` never touched `NodeKind.VALUE` node labels or
  `Explanation.subject` -- so `whytrail.config.env("DB_PASSWORD",
  "hunter2")` followed by `.redacted().text` still printed `hunter2`,
  in both the step description and the `why('hunter2'):` header
  itself. Fixed, gated precisely on `.nodes` being non-empty (i.e.
  this came from `_explain_from_graph`'s graph traversal) rather than
  on `ExplanationStep.kind` alone: a first version of the fix redacted
  *every* `kind == "value"` step regardless of origin and broke
  `whytrail-pydantic`'s explainer, which reuses `kind="value"` for an
  unrelated, already-safe purpose and already does its own correct
  locals-only redaction (caught by the existing plugin-contract suite,
  not by a fresh test -- `test_pydantic_plugin.py` failed for real,
  diagnosed, and fixed properly rather than patched around). Confirmed
  no bundled plugin populates `.nodes`/`.edges` on its own
  `Explanation`, so the gate reaches only the code path that actually
  has the bug. `tests/plugin_contract/test_redaction_fuzz.py` -- whose
  own docstring already admitted it had never fuzzed the Tier 2 path
  -- gained two new property-based tests (`track()` and
  `config.env()`); `tests/unit/test_explanation.py` gained four
  focused tests including a permanent regression test for the
  pydantic-breaking overreach specifically.

- **`@tracked` silently broke on `async def` functions -- the
  highest-value real gap the audit found.** Calling an async
  `@tracked` function returned a coroutine object immediately (not the
  eventual result), so the old sync-only wrapper created a graph node
  for the *coroutine*, never the awaited value -- `why()` on the real
  result came back honestly-but-wrongly "unknown." Worse: the
  exception-linking branch was dead code for async functions
  entirely, since calling a coroutine function never runs its body,
  so the wrapper's `try/except` around `fn(*args, **kwargs)` could
  never observe an exception raised inside one. Fixed with a second,
  `async def` wrapper variant selected once at decoration time via
  `inspect.iscoroutinefunction`, sharing the argument-linking/
  result-recording/exception-recording logic with the sync path via
  three small module-level helpers. 3 new tests
  (`tests/integration/test_why_tracking.py`): captures the awaited
  result, links arguments to a raised exception, and confirms the
  existing "no-op outside `trace()`" contract holds for async too.

- **Verified, not just claimed**: `ExceptionGroup` handling was tested
  against a real `asyncio.TaskGroup` failure and found already solid
  (correct sub-exception detail, correct origins) -- not added to the
  gap list. `Explanation.json()` already existed since v2.0 -- also
  not a gap, despite being on the reviewed candidate list.

Findings not acted on this round -- nested-container element-level
provenance, snapshot diffing, source-code line context in
explanations, and `_evict_if_needed`'s naive FIFO eviction -- are
named in `docs/roadmap.md` Phase F/G rather than dropped; each is real
but lower-value or higher-risk than the four above.

### Product/adoption audit and six DX shipments, plus a real bug found and fixed twice over

Following ADR 0008's engine audit, a second audit -- product/adoption,
not code -- was run against the real repo state (README, docs, CLI,
examples, benchmarks, visual identity, trust signals), each finding
checked against actual files rather than asserted. Six items shipped,
all polish, none touching the engine, the graph, or adding a public
verb:

- **README**: PyPI/CI/license badges; a `## Performance` section with
  real measured numbers (`pytest benchmarks/ --benchmark-only` and a
  direct `-X importtime` measurement) instead of an unquoted "no
  overhead" assertion; a real `.graph()` Mermaid diagram rendered from
  the README's own existing example, verified against actual output
  before being written down.
- **`examples/ex_fastapi.py`, `ex_flask.py`, `ex_django.py`,
  `ex_pytest_fixtures.py`** -- real, executed examples for four of the
  60 bundled integrations. Previously only 2 generic (non-integration)
  examples existed. Each one actually run before being committed,
  including catching and fixing an inaccurate expected-output claim
  along the way (the FastAPI/Flask/Django ones print real captured
  JSON response bodies, not hand-typed ones).
- **`SECURITY.md`** -- points to GitHub private vulnerability
  reporting (no public issue), and names the three genuinely
  security-sensitive areas of this codebase directly: locals
  capture/`Explanation.redacted()`, the FastAPI/Flask/Django
  integrations' two-separate-opt-in response safety, and the
  provenance graph never holding a strong reference to a tracked
  object.
- **`whytrail plugins` CLI subcommand** -- lists all 60 bundled
  integrations and whether each is actually active in the current
  environment (`registry.list_builtin_plugins()`,
  `list_hook_based_plugins()`, `list_entry_point_plugins()`, all new,
  read-only introspection over existing registry state). The CLI's own
  module docstring said a second subcommand needs the same
  "demonstrated need" bar the first was held to -- the bar here: 60
  integrations existed with zero runtime introspection of which are
  actually installed, a real and checkable gap, not a speculative one.
  9 new tests (`tests/integration/test_cli.py`,
  `test_protocol_and_registry.py`).
- **`docs/quickstart.md`** -- a real onboarding path distinct from
  `docs/index.md` (previously just a README mirror). Every command and
  output block in it was executed against this codebase before being
  written down, including catching and fixing a wrong line number in
  one quoted CLI output block, and replacing a live-network example
  (`httpbin.org`, which timed out in this environment rather than
  failing deterministically) with a DNS-failure example that
  reproduces the same way every time.

**A real bug found and fixed while measuring import time honestly**:
`registry.py` imported `importlib.metadata` eagerly at module load,
even though it's only needed the first time an entry-point plugin is
actually resolved -- costing ~30ms of every `import whytrail` (measured
via `-X importtime`: ~77ms before, ~50ms after) for a path most
processes never hit. Made lazy.

**A second real bug, introduced by the first fix and caught in the
same session, not after**: making that import lazy left
`_load_builtin_explainers()` calling `importlib.import_module(...)`
with no runtime `import importlib` left anywhere at module scope --
a `NameError` on every single call, silently swallowed by that
function's own `except Exception: continue` (a deliberately broad
catch meant for *a missing extra*, not for a typo in `registry.py`
itself). Net effect: all 43 built-in explainer plugins silently
stopped registering -- `why()` on a `requests.RequestException` fell
back to Tier 1's generic message instead of the plugin's method/URL
detail, with no error surfaced anywhere. Every test run this session
up to that point had excluded `tests/plugin_contract/` (it needs
extras installed), so 106 "passing" tests never exercised the actual
regression. Caught by deliberately running the full plugin-contract
suite for real (199 passed, 21 skipped for genuinely-not-installed
libraries, 0 failed after the fix) instead of continuing to trust the
smaller, faster suite. Fixed with a plain `import importlib` at module
scope (cheap -- unlike `importlib.metadata`, the bare `importlib`
module carries none of the `zipfile`/`json` import weight, confirmed
by re-measuring: import time stayed at the fixed ~50ms). Regression
test added:
`test_a_builtin_explainer_actually_registers_and_wins_over_tier_1`
(`tests/integration/test_protocol_and_registry.py`) -- exercises the
real import-and-register path end to end against a real dev
dependency, not a mock, specifically so this class of bug fails loudly
in the always-run suite next time, not silently in an excluded one.

### `whytrail.config`: config-value provenance, and ADR 0007

An external review pitched a ten-phase "make whytrail a platform"
vision modeled on `httpx`'s growth. Its sharpest claim -- the core
should be a general Explanation Engine, exceptions just its first
consumer -- checked out against the actual code: `NodeKind`/`EdgeKind`
(`whytrail/core/node.py`) were never exception-shaped, and
`whytrail.propagation`/`whytrail.integrations.langchain` already used
`NodeKind.EXTERNAL` outside the exception path. Rather than stop at
naming that, `whytrail/config.py` ships a second real consumer of the
same graph model, built entirely on existing primitives (no new
`NodeKind`/`EdgeKind`, no change to `why()`):

- **`env(name, default=..., dotenv=..., cast=...)`** -- resolves a
  setting from the process environment, a parsed `.env` mapping, or a
  default, and records which source actually won into the same
  `ProvenanceGraph` `track()` writes to. `why()` on the returned value
  walks that chain like any other tracked value.
- **`load_dotenv(path)`** -- a deliberately minimal `.env` parser (no
  interpolation, no multiline, no `export`); pass a fuller parser's
  output as `dotenv=` if a file needs more than this covers.
- **`ConfigError`** -- raised when a key has no value and no default;
  a normal exception, so Tier 1 already explains it with no dedicated
  explainer needed.

9 new tests (`tests/integration/test_config.py`), `mypy --strict`
clean. Explicitly out of scope: cloud secret-manager / Parameter
Store / Terraform provenance -- named in ADR 0007 as declined for now,
not silently dropped. The review's platform-scale phases
(observability platform, IDE/CI tooling ecosystem) were assessed and
declined for the same reason ADR 0005 and roadmap Phase O already
gave: no user signal yet to build speculative tooling against. Full
reasoning in
[`docs/adr/0007-explanation-engine-reframe.md`](docs/adr/0007-explanation-engine-reframe.md).

### ADR 0008: audit the Explanation Engine, don't add a third consumer

The instruction after `whytrail.config` shipped was explicitly the
opposite of "build another producer": audit whether the graph is
actually general or secretly exception-shaped, then write down the
rules that keep it that way -- before the temptation to keep piling on
consumers turns "engine" into a label over ad hoc special cases.

Read every file that touches `Node`/`Edge`. Findings:

- `core/graph.py`, `core/node.py`, `core/serialize.py`, `registry.py`,
  `protocols.py` are clean -- confirmed, not assumed, that nothing there
  branches on `NodeKind.EXCEPTION` (or any producer's identity)
  differently from any other kind.
- `core/explanation.py`'s `.plain_text`/`.json()` glosses exception
  types by design -- rendering may be domain-aware without the graph
  being domain-aware; the two claims were previously conflatable and
  are now stated as independent.
- A real, previously-unstated architectural boundary: `why()` on a
  `BaseException` always resolves through Tier 1 and never consults
  graph-tracked provenance for that object, even if some was recorded.
  Deliberate per ADR 0001's two-tier split, not a gap -- now pinned by
  a regression test instead of being an implicit assumption.
- A real bug in code shipped one entry above this: `config.py`'s
  missing-key branch created a graph node with no way for anything to
  ever reach it (`why()` never consults the graph for an exception
  about to be raised, per the previous finding). **Fixed**: that node
  is no longer created; `ConfigError`'s own message already carries
  what was checked.

Shipped:

- [`docs/adr/0008-explanation-engine-invariants.md`](docs/adr/0008-explanation-engine-invariants.md) --
  six invariants (the audit's findings turned into checkable rules),
  and the reasoning for keeping "producer" a documented convention
  rather than a class hierarchy.
- [`docs/explanation-engine.md`](docs/explanation-engine.md) -- the
  internal guide: what the engine is/isn't, producers, consumers,
  traversal, rendering, extension points ranked by risk, anti-patterns.
- `tests/integration/test_engine_invariants.py` (6 tests): a
  never-seen-before "producer" needs no engine change, a config-to-value
  chain spanning two independent modules traverses correctly, a
  constructed cycle doesn't hang or duplicate nodes, traversal is
  deterministic for a fixed graph, unknown stays honest for an
  arbitrary user-defined type, and Tier 1 never merges in graph
  provenance for an exception.

No core redesign -- the audit's answer to "is the graph secretly
exception-shaped" was no. AWS Parameter Store, Secrets Manager,
Terraform, and every other new-producer idea from the original review
stay explicitly unbuilt; this phase was about the seam, not about
testing it with another real integration.

## [0.2.1] - 26 new integrations (34 -> 60, target reached), plain-English explanations, API stability policy, project roadmap

Thirteen units of work since 0.2.0, newest first. 369 tests pass
total; `mypy --strict` clean; CI green across all three matrices
(`test`, `plugin-contract-tests`, `plugin-version-matrix`) as of the
most recent push.

### Real CI confirmed 8 of the 46 batch 5-6 floor guesses were wrong -- fixed on real Linux

The first real CI run after the batch 5-6 push (60/60), same discipline
as every prior floor-correction round: never guess a fix from reading
version numbers, always confirm on real Linux (WSL2 + `uv`) before
writing it down. `pyproject.toml`'s aspirational floors are left as-is
by convention; only `ci.yml`'s CI-tested floor moves:

- **`cassandra-driver`**: `3.25.0` -> `3.30.0`. A bug in the package's
  own decades-old `ez_setup.py` bootstrap script (`TarFile.chown()`
  called without the now-required `numeric_owner` argument), present
  in every version through 3.29.0 -- only fixed in the latest line.
- **`clickhouse-connect`**: `0.6.0` -> `1.3.0`, the largest jump of this
  round and the only one requiring two separate real-CI-driven fixes:
  `pkg_resources` removal broke import below 0.7.0, but 0.7.0 through
  1.2.0 still failed this plugin's *actual contract test* --
  `ClickHouseError`'s `code=`/`name=` keyword constructor (the entire
  reason this plugin exists) doesn't exist until 1.3.0. Found by
  installing each candidate and running the real test against it, not
  by checking "does it import."
- **`confluent-kafka`**: `2.0.0` -> `2.6.0`. `2.0.0` was never
  published at all (PyPI jumps `1.9.2` -> `2.0.2` directly) -- a bad
  guess, not a version-compatibility gap. `2.0.2` through `2.5.0` fail
  to build from source needing the system `librdkafka` C library;
  `2.6.0` is the first version with a self-contained prebuilt wheel.
- **`pymssql`**: `2.2.0` -> `2.3.1`. No `cp313` wheel through every
  `2.2.x` patch and even `2.3.0`; first Python-3.13-compatible wheel at
  `2.3.1`.
- **`pyzmq`**: `24.0.0` -> `26.1.0`. No `cp313` wheel, and the source
  build fails with a real C++ compile error through `26.0.3`.
- **`snowflake-connector-python`**: `3.0.0` -> `3.10.0`. Same
  `pkg_resources` removal as `clickhouse-connect`; still broken at
  `3.5.0`, first working at `3.10.0`.
- **`zeep`**: `4.1.0` -> `4.3.0`. Zeep's own `utils.py` imports the
  stdlib `cgi` module directly (PEP 594 removal, same category as
  `azure-core`'s earlier floor fix) -- still broken at `4.2.0`/`4.2.1`,
  the fix had to land in zeep's own code.

**One false alarm, not a floor bug:** `google-genai`'s floor
(`1.0.0`) was correct -- the plugin's own field-reading logic
(`.code`/`.status`/`.message`/`.details`) works fine at that version.
The *test* was wrong: it constructed `ClientError` by passing a raw
dict directly, which only happens to work against the newest SDK
version's more lenient constructor. `1.0.0`'s real constructor expects
a genuine `requests.Response` (or a `ReplayResponse`), so the test now
builds one via `requests.models.Response()` and drives it through the
SDK's own `raise_for_response()` classmethod -- the same construction
path production code actually uses, matching this project's "real
object" testing discipline instead of a shortcut that only coincidentally
worked.

**Two confirmed already correct, no change:** `pika`/`kubernetes`'s
guessed floors (batch 2b) and `oracledb==2.0.0` (batch 6) all passed
their real Linux floor check on the first try -- not everything from a
guess turns out wrong.

### 7 new integrations (batch 6 of the 30-to-60 push, target reached): psycopg, cassandra, influxdb, pyzmq, zeep, elastic-apm, bugsnag

**60/60.** The last batch of the push this whole session was scoped
around (ADR 0003's original triage, revived as a concrete target
several sessions ago). `pymemcache` and `pysolr` were also researched
this batch and rejected (see below).

- **`psycopg`** (the v3 rewrite): a genuinely different verdict than
  `psycopg2`, which ADR 0003 already found blocked -- `.pgcode` there
  is a C-level read-only attribute, populated only by a real
  PostgreSQL connection. `psycopg`'s `.sqlstate` is a plain, settable
  Python attribute, confirmed directly by constructing one and setting
  it, not assumed from the successor relationship. (The richer `.diag`
  object's fields *are* still read-only outside a real connection --
  this plugin deliberately doesn't use them, staying more modest than
  `whytrail-asyncpg`'s async-only coverage of the same database.)
- **`cassandra`**: registers against `RequestExecutionException`
  specifically, not the driver's top-level `DriverException` --
  checked directly that the sibling `InvalidRequest` type (a different
  branch, `RequestValidationException`) carries nothing but a plain
  message, so registering any broader would have silently produced
  useless output for the most common query-error case. The types this
  *does* cover (`Unavailable`/`WriteTimeout`/`ReadTimeout`) carry real
  consistency-level detail -- and confirmed no redaction concern
  exists either, since every field is coordination metadata, never
  query content.
- **`influxdb`**: `ApiException`'s `.status`/`.reason`/`.body`, the
  same structured HTTP-API-error shape already proven for
  `boto3`/`elasticsearch`.
- **`pyzmq`**: `ZMQError`'s `.errno` -- `str(exc)` renders *only*
  `.strerror` (e.g. `"Unknown error"`), dropping the numeric errno
  code entirely, so a bare traceback doesn't even show which error
  this was. No redaction concern (OS/protocol-level codes only).
- **`zeep`**: SOAP `Fault`'s `.code`/`.message`/`.detail` -- SOAP
  faults commonly embed the raw offending XML in their detail, redacted
  accordingly.
- **`elastic-apm`**/**`bugsnag`**: two more integration-shaped
  (hook-based) plugins, the same custom-attribute-attachment pattern as
  `newrelic`/`rollbar`/`honeybadger`/`ddtrace`/`otel`.

**Rejected, with reasons:** `pymemcache` -- every exception class in
its hierarchy, checked down to the `MemcacheIllegalInputError` leaf, is
a bare `pass` with nothing beyond a message. `pysolr` -- confirmed by
reading every `raise SolrError(...)` call site in the driver's own
source, all of them pass a pre-formatted string, no structured kwargs
anywhere.

pyproject.toml gained `psycopg`/`cassandra`/`influxdb`/`pyzmq`/`zeep`/
`elastic-apm`/`bugsnag` extras -- all floors guesses, not yet bisected
against real CI.

### 9 new integrations (batch 5 of the 30-to-60 push): pymysql, pymssql, clickhouse, snowflake, graphql-core, tenacity, newrelic, rollbar, honeybadger

The largest single batch so far, past the halfway point to 60 (53/60).
`duckdb` was also researched this batch and rejected (see below).

The largest single batch so far, past the halfway point to 60 (53/60).
`duckdb` was also researched this batch and rejected (see below).

- **`pymysql`**/**`pymssql`**: both carry `(code, message)` in `.args`,
  the same shape as `pyodbc` -- MySQL's numeric errno and SQL Server's
  DB-Lib code respectively, message redacted.
- **`clickhouse`** (clickhouse-connect): `.code`/`.name` are only
  populated by the real driver's raise site (confirmed by reading
  `httpclient.py`'s `raise err_type(err_str, code=code, name=name)`
  directly, not by hand-constructing an exception and assuming the
  fields would be set the same way -- a bare construction leaves both
  `None`).
- **`snowflake`**: the richest of this batch --
  `.errno`/`.sqlstate`/`.sfqid` safe in `description`, `.raw_msg`/
  `.query` (the literal failed SQL) redacted, the same posture as
  SQLAlchemy's bound params.
- **`graphql-core`**: registers against `graphql.GraphQLError`
  directly rather than against strawberry-graphql specifically --
  strawberry, Ariadne, and graphene are all built on graphql-core's
  execution engine, so one registration covers all three. `.path` (the
  resolver path, e.g. `["user","profile","ssn"]`) safe in
  `description`; `.message` redacted.
- **`tenacity`**: structurally different from every other plugin in
  this ecosystem -- `str()` on a bare `RetryError` doesn't squash
  structured data into one line, it hides the actual failure entirely
  (`RetryError[<Future ... raised ValueError>]`). This explainer
  unwraps `.last_attempt.exception()` and delegates to `why()`
  recursively, the same "expand into the real cause" approach already
  used for `ExceptionGroup`'s sub-exceptions, rather than extracting
  fields the way every other plugin does.
- **`newrelic`**/**`rollbar`**/**`honeybadger`**: three new
  integration-shaped (hook-based) plugins, all the same shape as the
  existing `ddtrace`/`otel` span-attachment pattern -- attach a
  flattened, redacted-by-default `Explanation` as custom
  attributes/extra data on the respective service's own error-reporting
  call (`notice_error()`/`report_exc_info()`/`notify()`).

**`duckdb` rejected, with reasons:** `duckdb.Error` is `Exception`-shaped
with nothing beyond `.args` -- confirmed via `dir(exc)` on a real
`CatalogException` from an in-memory database, no separate code or
location attribute exists even though the message text itself contains
a line/column reference. Same shape and same verdict as `tomllib`.

pyproject.toml gained `pymysql`/`pymssql`/`clickhouse`/`snowflake`/
`graphql-core`/`tenacity`/`newrelic`/`rollbar`/`honeybadger` extras --
all floors guesses, not yet bisected against real CI.

### CLI: missing script file no longer leaks runpy internals

`whytrail run does_not_exist.py` previously let `runpy.run_path()`
raise its own `FileNotFoundError`, which `why()` rendered honestly but
unhelpfully -- a `<frozen runpy>` traceback frame with the
interpreter's own internal locals (a raw function repr, a memory
address), not anything about the user's actual mistake. Found by
actually dogfooding the CLI's real failure paths, not just reviewing
`--help` output. Now checked explicitly before invoking `runpy`, with
a clean `whytrail: no such file: X` error. One new test.

### Added the project roadmap, phases A through Q

`docs/roadmap.md`: the long-range plan behind this session's work,
written so "what's next and why" doesn't have to be re-derived from
git history each time. Phases C/E/G/H/I have concrete near-term work;
K/L/N/O/P are explicit decisions deferred to a real trigger (a second
contributor, real user feedback, a specific request) rather than
fabricated work items, named that way deliberately rather than padded
out to look complete. Q ties back to the still-open 1.0 question
`api-stability.md` already raised.

### 3 new integrations (batch 4 of the 30-to-60 push): google-genai, oracledb, confluent-kafka

Checked directly against real objects, not docs. `fastavro` and
`paho-mqtt` were also researched this batch and rejected (see below).

- **`google-genai`**: the *current* Gemini API SDK, not the deprecated
  `google-generativeai` (a `FutureWarning` fires on import pointing at
  this successor -- confirmed directly, not assumed from a version
  number). `google-generativeai`'s errors route through
  `google.api_core.exceptions.GoogleAPICallError`, already covered by
  the existing `whytrail-google-cloud` plugin; `google-genai` is
  architecturally separate, its own `google.genai.errors.APIError`
  hierarchy with `.code`/`.status`/`.message`/`.details`. `.message`
  redacted (echoes back the offending request detail, e.g. a
  content-safety rejection quoting the input); `.code`/`.status` safe
  in `description`.
- **`oracledb`**: `Error`'s `args[0]` is a real `_Error` object
  carrying `.full_code` (a stable `"ORA-12545"`-style taxonomy) and
  `.offset` -- confirmed via a real (thin-mode) connection attempt
  against an unreachable host, no live Oracle database needed. Unlike
  `psycopg2`, whose equivalent `.pgcode`/`.pgerror` ADR 0003 already
  found are C-level read-only attributes populated only by a real
  connection -- a different constraint, checked separately rather than
  assumed to be the same problem. `.message` redacted; `.full_code`/
  `.offset` safe in `description`.
- **`confluent-kafka`**: not the same verdict as the already-rejected
  `kafka-python` -- `KafkaException.args[0]` is a real, per-instance
  `KafkaError` object (`.name()`/`.fatal()`/`.retriable()`), unlike
  `kafka-python`'s class-level static constants. `.str()` (librdkafka's
  own message) redacted; `.name()`/`.fatal()`/`.retriable()` safe in
  `description`.

**Rejected, with reasons:** `fastavro` -- `UnknownType`'s only
attribute (`.name`) duplicates its own `str(exc)` exactly, and a
malformed-container-file read raises a plain `ValueError` with no
structured data at all. `paho-mqtt` -- `Client.connect()` returns an
`MQTTErrorCode` enum rather than raising, so there's no exception
object for `why()` to explain; the one real exception class
(`WebsocketConnectionError`) carries nothing beyond a bare message.

pyproject.toml gained `google-genai`/`oracledb`/`confluent-kafka`
extras (floors `google-genai>=1.0`, `oracledb>=2.0`,
`confluent-kafka>=2.0` -- all guesses, not yet bisected against real
CI).

### Added API stability policy doc

`docs/api-stability.md`: what's actually stable in practice pre-1.0
(the five verbs, `Explanation`/`ExplanationStep`/`Confidence`, the
frozen Explainer Protocol v1) versus what's still moving
(`ExplanationStep`'s field set, `__all__`, integration internals).
Also names a real documentation gap plainly rather than leaving it
implicit: no ADR states a checkable bar for cutting 1.0, and this
project's own 0.1.0 entry (below) cites one -- "the packaging policy
in the ADR" -- that doesn't actually exist in the ADR it points to.

### 4 new integrations (batch 3 of the 30-to-60 push): sendgrid, websockets, opensearch, pyodbc

Checked directly against real objects, not docs, per ADR 0003's bar.
`tomllib` was also researched this batch and rejected (see below).

- **`sendgrid`**: `python_http_client.exceptions.HTTPError` (the base
  SendGrid's SDK actually raises -- `BadRequestsError`,
  `UnauthorizedError`, etc.) carries `.status_code`/`.reason`/`.body`/
  `.headers`, confirmed by direct construction the same way the SDK
  builds one internally. `.body` redacted (echoes back the offending
  field/value); `.status_code`/`.reason` are safe in `description`.
- **`websockets`**: `ConnectionClosed`'s close code/reason -- but
  reads `.rcvd.code`/`.rcvd.reason`, not the `exc.code`/`exc.reason`
  properties, which turned out to be **deprecated since websockets
  13.1** (found by constructing a real `ConnectionClosedError` and
  watching a live `DeprecationWarning` fire, not by reading a
  changelog). Falls back to the deprecated accessors only when
  `.rcvd` is `None` (the peer never sent a close frame at all -- still
  produces a sensible default, confirmed directly: code 1006, empty
  reason). `.reason` redacted (echoes back the specific error that
  caused the disconnect); `.code` (a small closed RFC 6455 set) is
  safe in `description`.
- **`opensearch`**: `opensearchpy.exceptions.TransportError`'s
  `.status_code`/`.error`/`.info` -- opensearch-py is a fork of
  elasticsearch-py and shares the exact same shape as the existing
  `whytrail-elasticsearch` plugin (same `vars(exc)`-is-empty gotcha,
  confirmed directly rather than assumed from the fork relationship).
  `.info` (the full structured response) redacted; `.status_code`/
  `.error` safe in `description`.
- **`pyodbc`**: `pyodbc.Error`'s `args[0]`/`args[1]` -- a real
  ISO/ODBC SQLSTATE taxonomy code and the driver's own message,
  confirmed directly (`vars(exc)` is empty; pyodbc exposes no named
  attributes, only `.args`, unlike psycopg2's blocked C-level
  attributes noted in ADR 0003 -- a different constraint, checked
  separately rather than assumed to be the same problem). SQLSTATE
  safe in `description`; driver message redacted (routinely embeds
  the offending table/column name).

**`tomllib` rejected, with reasons:** fed seven kinds of malformed TOML
into `tomllib.loads()` and inspected the real `TOMLDecodeError` --
`vars(exc)` is empty and there is no `.lineno`/`.colno`/`.pos`
attribute analogous to PyYAML's `MarkedYAMLError.problem_mark`; the
"at line X, column Y" text is baked directly into the single message
string at raise time, not exposed separately. This is the
`configparser` shape (plain message), not the PyYAML shape (a
structured, independently-redactable `Mark` object) -- checked
directly rather than assumed from either precedent. Also confirmed no
redaction concern exists either: a secret value planted in malformed
TOML never appeared in `str(exc)` in any of the seven cases tested.

pyproject.toml gained `sendgrid`/`websockets`/`opensearch`/`pyodbc`
extras (floors `sendgrid>=6.0`, `websockets>=12.0`,
`opensearch-py>=2.0`, `pyodbc>=4.0` -- all guesses, not yet bisected
against real CI).

**Real CI confirmed `websockets`' and `opensearch`'s guessed floors on
the first try; `sendgrid` and `pyodbc` weren't as lucky:**
- `sendgrid==6.0.0`: `ModuleNotFoundError: No module named 'yaml'` --
  sendgrid's own code imports PyYAML directly, but its package
  metadata at this version doesn't declare it as a dependency
  (`Requires: python-http-client` only), so pip never installs it. A
  packaging bug in sendgrid itself, same category as
  `paramiko==2.7.0`'s missing `six` dependency. First working, by
  bisection: `6.1.0`.
- `pyodbc==4.0.0`: no cp313 wheel published, and building from source
  fails (missing unixODBC headers) -- same "no 3.13 wheel" category as
  `pydantic==2.0.3`/`pyyaml==6.0`/`grpcio==1.60.0`/`pandas==2.0.0`.
  Checked every 5.0.x/5.1.x patch release on real Linux: none publish
  one either. First version with a cp313 wheel: `5.2.0`. (pyodbc's C
  extension also needs the unixODBC *runtime* library at import time --
  confirmed already present on `ubuntu-latest`, since this same job's
  `latest`-pinned sibling entry imports pyodbc successfully today; the
  wheel gap was the only real bug.)

### 3 new integrations (batch 2b of the 30-to-60 push): pika, kubernetes, azure-core

Candidates researched by dispatching a background agent to actually
install and exercise four libraries against real exceptions before
writing any plugin code, per ADR 0003's bar -- one (`kafka-python`)
was rejected on the same evidence, the other three confirmed:

- **`pika`**: `ChannelClosed`/`ConnectionClosed`'s `reply_code`/
  `reply_text` -- the broker's own AMQP status code and reply text
  (e.g. `404, "NOT_FOUND - no exchange 'orders'"`). Both are
  `@property`s reading `self.args`, not `__dict__` entries, so
  `vars(exc)` alone would show nothing -- read via normal attribute
  access instead. `ChannelClosed` and `ConnectionClosed` are siblings
  under `AMQPError`, not one a subclass of the other, so both needed
  their own registration despite sharing the exact same shape.
  `reply_text` redacted (can echo a queue/exchange name from the
  request); `reply_code` (a small closed AMQP status-code set) is
  safe in `description`.
- **`kubernetes`**: `ApiException`'s `.status`/`.reason`/`.body` --
  note `.reason` is the *HTTP* reason phrase ("Not Found"), not the
  Kubernetes `Status` object's own `reason` field ("NotFound"), which
  only exists inside `.body`. Direct construction
  (`ApiException(status=, reason=)`) leaves `.body` as `None`, so this
  one specifically needed a real request/response round trip (a
  throwaway local HTTP server, no live cluster) to get a real object
  with `.body` actually populated -- confirmed by trying direct
  construction first and finding it insufficient. `.body` redacted (a
  cluster's error message routinely echoes back the resource name and
  namespace from the request).
- **`azure-core`**: `HttpResponseError`'s `.status_code`/`.reason`/
  `.error` (a parsed `ODataV4Format` with its own `.code`/`.message`,
  shared across every Azure SDK client built on azure-core --
  azure-storage-blob, azure-identity, azure-cosmos, etc.). `.error.code`
  is a stable taxonomy string (e.g. `"BlobNotFound"`), safe in
  `description`; `.error.message`/`.message` redacted (routinely
  echoes a request ID or resource path).

**Rejected, with reasons:** `kafka-python` (the `-ng` fork is
superseded -- `kafka-python` itself resumed releases and is now the
one to target, confirmed via PyPI, not assumed) was checked directly
against a live Kafka container and found to carry no per-instance data
on its exceptions at all: `errno`/`message`/`description` are
class-level constants from a static protocol-error-code table, not
populated per-exception, and there's no topic/partition/offset
attribute on the exception itself (only on success objects). Same
"nothing to add over tier 1" verdict as `redis-py`.

pyproject.toml gained `pika`/`kubernetes`/`azure-core` extras (floors
`pika>=1.1`, `kubernetes>=18.20`, `azure-core>=1.24` -- all guesses
from the research, not yet bisected against real CI the way the
batch-1 floors were).

**Real CI confirmed `pika`'s and `kubernetes`' guessed floors on the
first try -- no bug, breaking the streak batch 1 set.** `azure-core`
wasn't as lucky:
- `azure-core==1.24.0`: `ModuleNotFoundError: No module named 'cgi'` --
  `azure/core/rest/_helpers.py` imports the stdlib `cgi` module,
  removed in Python 3.13 (PEP 594). A genuine stdlib-removal
  incompatibility in azure-core's own code, the same category as
  `marshmallow==3.0.0`'s `distutils.version` removal below. First
  working, by bisection on real Linux: `1.27.0`.

### 1 new integration (batch 2 of the 30-to-60 push): elasticsearch

`elasticsearch.ApiError` (covering `NotFoundError`, `ConflictError`,
`AuthorizationException`, etc.) carries the HTTP status via `.meta.status`
and the full structured error body Elasticsearch itself returned via
`.body` -- both collapsed by `str(exc)` into a single line that drops
which index/resource was involved and the actual reason. Verified
against a real request/response round trip through a throwaway local
HTTP server standing in for a cluster (no live Elasticsearch needed),
the same pattern used for every other plugin's contract tests.

The full `.body` goes through `locals`, never `description`: a
`parsing_exception`'s `reason` field routinely echoes the offending
query text verbatim, so nothing inside the body is safe in a field
`.redacted()` doesn't strip. Only the HTTP status is safe in
`description`. Confirmed by planting a known query fragment in the
body and asserting it survives in `locals` but not in the redacted
text.

pyproject.toml gained an `elasticsearch` extra (floor `elasticsearch>=8.0`).
268 tests pass total; `mypy --strict` clean. Floor verified locally
against `elasticsearch==8.0.0` before push; treated as a guess until
real CI confirms it, same discipline as every prior floor.

### 3 new integrations (batch 1 of the 30-to-60 push): stripe, alembic, paramiko

First batch of growing the integration count, each checked against
ADR 0003's actual bar (structured error data a bare traceback throws
away) by inspecting real library objects before writing any code, not
assumed from popularity:

- **`stripe`**: `StripeError`'s `.code`/`.param`/`.http_status`/
  `.json_body` -- the same "why did this payment fail" structured-error
  shape already proven for openai/anthropic. Body goes through
  `locals`, redacted by default (a payment error can echo back request
  detail).
- **`alembic`**: `ResolutionError`/`MultipleHeads` -- directly motivated
  by a real bug hit debugging this project's own CI earlier
  (a stale `prefect.db` producing a confusing "no such revision" error
  with no indication of what argument or how many heads were involved).
- **`paramiko`**: `BadHostKeyException`'s `.expected_key`/`.key` --
  shown as fingerprints (the standard, safe way to identify an SSH key),
  never raw key material.

**Two candidates downgraded, not forced in:** `PyJWT` and
`cryptography` were both checked directly and found to carry no
structured fields beyond their own message -- the same "nothing to add
over tier 1" reasoning that's kept `redis-py` off the list since the
original 30. Real value without a full plugin: ~10 of their exception
types added to the plain-English gloss/fix tables instead (`.plain_text`
now glosses `ExpiredSignatureError`, `InvalidSignature`, etc.).

**Two real bugs found and fixed before this ever reached a commit,**
by the same discipline that's caught everything else this session:
- `whytrail-paramiko`'s first draft read `exc.got_key`, but the actual
  stored attribute is `exc.key` (the constructor parameter is named
  `got_key`; the stored attribute isn't) -- found because `why()`
  silently swallows an explainer's own exceptions and falls through to
  the generic tier-1 fallback, which *looked* like working output until
  a test asserted on content only the plugin could produce.
- All three new integrations were initially unreachable: added as
  modules and as `pyproject.toml` extras, but never added to
  `registry._BUILTIN_EXPLAINERS` -- the actual discovery list. Every
  `test_plugin_is_discovered()` assertion failed loudly, which is
  exactly why that assertion exists in every plugin's test file.

pyproject.toml gained `stripe`/`alembic`/`paramiko` extras. 264 tests
pass total; `mypy --strict` clean.

**All three new floors turned out wrong once real CI checked them --
the same ~1-bug-per-new-floor rate the original 30 hit, now 3 for 3**
(`pyproject.toml`'s aspirational floors are left as-is; only the
CI-tested floor moves, matching how every prior floor correction in
this project has been handled):
- `stripe==7.0.0`: `stripe.StripeError`/`stripe.CardError` didn't exist
  as top-level names yet (only under the older `stripe.error.*` path).
  First working: `8.0.0`.
- `alembic==1.7.0`: `NameError: name 'TextClause' is not defined`,
  raised inside alembic's own `operations/ops.py` -- a transitive
  SQLAlchemy-version-drift issue in alembic's own code. First working,
  by bisection: `1.8.0`.
- `paramiko==2.7.0`: `ModuleNotFoundError: No module named 'six'` --
  `ed25519key.py` imports `six` directly, but paramiko's own package
  metadata at this version doesn't declare it as a dependency, so pip
  never installs it. A packaging bug in paramiko itself. First working,
  by bisection: `2.10.0`.

### Fixed: why() was blind to ExceptionGroup's sub-exceptions

Found by actually raising one, not by reasoning about the type in the
abstract: `why()` on a Python 3.11+ `ExceptionGroup` (what
`asyncio.TaskGroup` and structured-concurrency code raise) only showed
the group's own generic wrapper message ("unhandled errors in a
TaskGroup (2 sub-exceptions)") and completely missed the actual
sub-exceptions that caused it -- exactly the information anyone
catching one of these needs.

- `explain_exception()` now walks into `.exceptions` (duck-typed via
  `getattr`, since `(Base)ExceptionGroup` doesn't exist as a name before
  3.11 -- same pattern as `MONITORING_AVAILABLE`'s `hasattr` check
  elsewhere for another version-gated feature) and adds a step per
  sub-exception, recursively for nested groups, capped at
  `MAX_GROUP_EXCEPTIONS = 5` with a "N more not shown" step beyond that.
- `ExceptionGroup`/`BaseExceptionGroup` added to the plain-English gloss
  and fix-suggestion tables.
- 3 new tests, `skipif`-guarded and verified on a real Python 3.10
  interpreter (WSL2 + `uv`) to confirm the file still collects and skips
  correctly pre-3.11, not just that the guard *looks* right.
- 251 tests pass total; `mypy --strict` clean.

### Plain-English explanations and fix suggestions

- **`Explanation.plain_text`**: a prose rendering of the exact same
  steps `.text` shows, phrased for someone without a programming
  background -- no new dependency, no LLM call, and no less honest
  than `.text`: every sentence is a direct paraphrase of a step already
  present, never new information. Common builtin exceptions (`KeyError`,
  `ValueError`, `ConnectionError`, ~25 total) get a plain-English gloss
  from a small, curated table; anything outside that table keeps its own
  name rather than getting a guessed-at description (ADR §11's "never
  fabricate" applies to prose phrasing exactly as much as it applies to
  the causal chain itself). `.text` is unchanged and stays the default --
  this is additive, not a replacement.
- **"How to avoid this" guidance**: known exception types also get a
  line of general, well-established advice (check the key exists before
  indexing, validate the input, retry with backoff, ...) -- framed
  explicitly as guidance for that *class* of error, not a diagnosis of
  this specific failure, since whytrail has no way to know a fix
  actually applies here. Surfaced in `.plain_text` and as a new
  `"suggestion"` field in `.json()` (`None` when there's no guidance for
  that type, never a guessed-at one).
- 12 new tests covering both features (glossing, fallback for unglossed
  types, non-exception steps left alone, confidence hedging, redaction
  interaction). 248 tests pass total; `mypy --strict` clean.

## [0.2.0] - unified plugin ecosystem into extras, renamed to whytrail, first real CI hardening

Nine units of work, newest first. Published to PyPI as `whytrail` 0.2.0.
This heading was missing until it was reconstructed retroactively from
git history -- see the note at the top of this file.

### Unified all 30 plugins into extras of one package (ADR 0006)

A fresh-install smoke test of the real PyPI package (not the local
build) confirmed core `whytrail` works end to end -- but also surfaced
that none of the 30 plugin distributions were ever published, only
core. The README's ecosystem table implied `pip install
whytrail-requests` worked; it didn't. Publishing all 30 separately would
have meant registering 30 PyPI pending-publishers by hand and 30 ongoing
release processes going forward -- reconsidered instead: all 30 are now
optional extras of the single `whytrail` package (`pip install
whytrail[requests]`, `whytrail[all]`), one release process, the
zero-required-dependencies promise for bare `pip install whytrail`
unchanged. Full reasoning in
`docs/adr/0006-unify-plugins-into-extras.md`.

- `plugins/whytrail-*/src/whytrail_*/__init__.py` moved to
  `src/whytrail/integrations/*.py` (30 files, `git mv`, history
  preserved). The 18 explainer-shaped ones auto-register lazily via a
  new static list (`registry._BUILTIN_EXPLAINERS`); the 12
  integration-shaped ones (hooks/middleware/signals) are imported and
  wired in explicitly, same as before.
- The `whytrail.explainers` entry-point mechanism and
  `register_from_plugin()` are unchanged and un-removed -- still the
  right answer for a third party who wants to publish their own
  integration outside this repo. `scripts/new_plugin.py` now scaffolds
  that external case specifically.
- `pyproject.toml` gained 30 extras plus a self-referencing `all` meta-extra,
  and a `[project.entry-points.pytest11]` declaration (pytest's own
  plugin discovery is independent of whytrail's registry and always was).
- `[tool.mypy]` gained `exclude = ["^src/whytrail/integrations/"]` --
  the same reason `otel.py` needed an override (third-party stubs not
  installed in the default `dev` environment), now at 30x the scale,
  where a blanket exclude is more honest than 30 near-identical
  per-module overrides. Integrations are still checked individually in
  CI.
- CI simplified along with the restructure: `plugin-version-matrix` no
  longer needs an "install the plugin package without its dependency
  pin" step, since the integration module is already on disk as soon as
  core `whytrail` installs -- it just doesn't register until the
  dependency is present. Verified on real Linux (WSL2 + `uv`-managed
  Python, since Docker Desktop wasn't running in this sandbox) before
  pushing.
- All 237 tests pass unchanged against the new layout; `mypy --strict`
  clean.

### Second CI run found eight more, real Linux this time

The three-bug fix above unblocked the `test` and `plugin-contract-tests`
jobs and expanded `plugin-version-matrix` from 2 broken jobs to 103 real
ones -- which surfaced 8 more genuine failures, all `plugin-version-matrix`
"floor" entries, none reproducible on this project's Windows sandbox for
compiled/native packages (grpcio/ddtrace-style wheel gaps are
platform-specific). Installed Docker (found not running) then WSL2 +
`uv`-managed Python 3.13 to get a real Linux environment instead of
guessing from Windows behavior -- every fix below was confirmed on actual
Linux before being written here, the same discipline as the Windows-only
findings that started this file's "found by actually testing" pattern.

- **`sentry-sdk==2.0.0`**: passed a local install-and-import check but
  crashes for real -- `copy.copy()` on frame locals breaks against
  Python 3.13's `FrameLocalsProxy` (PEP 667). Only surfaced once a real
  CI run exercised the actual capture path against a real exception, not
  when checking "does it import." First working, by bisection: 2.11.0.
- **`prefect==2.14.0` through `2.20.0`**: not fixable within the 2.x line
  at any patch version -- `GatherTaskGroup`, prefect's own
  `asyncio.TaskGroup` subclass, doesn't implement an abstract method
  Python 3.13's `asyncio` added, independent of pydantic/griffe versions.
  Moved the floor to the 3.x line entirely (3.7.8); earlier 3.x releases
  have their own pydantic-version-drift issues (`PydanticUndefinedAnnotation`
  against very new pydantic), so 3.0.0 doesn't work either -- the
  historical griffe fix from the first CI round only mitigated one of
  three unrelated compatibility issues wrapped up in the same one-line
  matrix entry.
- **`flask==2.3.0`**: `testing.py` reads `werkzeug.__version__`, which
  werkzeug 3.x removed -- transitive drift, not a Flask bug. First
  working: 2.3.3.
- **`ddtrace==2.0.0`→`2.19.0`**: the earlier fix only checked "does it
  import"; the test imports `ddtrace.trace.tracer`, a module-level
  singleton that didn't exist until 2.20.0.
- **`openai==1.0.0`, `anthropic==0.30.0`**: both plugins read
  `exception.body`, whose shape at these floor versions doesn't match
  what the code expects -- an SDK API-surface gap, not a Python-version
  issue. First working: openai 1.30.0, anthropic 0.34.0 (both by
  bisection).
- **`huggingface_hub==0.20.0`**: `huggingface_hub.errors` (the module the
  plugin imports) didn't exist at 0.20.0; even once it appeared at 0.22,
  `hf_raise_for_status()`'s response handling didn't match the test's
  constructed response until the 1.x line. First working: 1.0.0 -- a
  major-version jump, discovered the same way prefect's was.
- **`whytrail-fastapi`'s version-matrix entry was testing the wrong
  thing.** `starlette` alone isn't independently testable for this
  plugin: its test builds a real FastAPI app, so pinning `starlette` to
  an old floor while a separately-installed `fastapi` expects a newer
  one breaks on an unrelated `TestClient` API mismatch that has nothing
  to do with whytrail-fastapi's own redaction logic. Switched the pinned
  dependency to `fastapi` itself (floor 0.115.0, confirmed to both
  resolve a starlette satisfying the plugin's real `>=0.36` floor and
  pass the actual test).

Full technical detail and the "why" behind each floor choice is in
`.github/workflows/ci.yml`'s `plugin-version-matrix` job comment, not
duplicated here.

### First real CI run found three bugs no local check could

Pushed to `github.com/bhouvana/Whytrail` for the first time. Every prior
verification in this project ran in one local Windows sandbox; the first
push to real `ubuntu-latest`/`windows-latest`/`macos-latest` runners
immediately failed 45/47 CI jobs, and every failure was a genuine gap
this environment structurally could not have caught -- exactly the
reason `docs/testing-maturity.md` flagged "the CI workflow has never
executed" as the top open risk. Reproduced each locally in a from-scratch
clone + venv (not the accumulated dev `.venv` used all session, which
had masked two of these by having extra packages already installed) to
confirm root cause before fixing:

- **All 12 `test` job combinations failed on `mypy --strict`.**
  `src/whytrail/otel.py` imports `opentelemetry` behind a runtime
  try/except (correct -- it's an optional extra), but mypy still
  resolves the import statically, and `opentelemetry-api` lives behind
  the separate `otel` extra, not `dev`. A clean `pip install -e ".[dev]"`
  -- exactly what CI runs -- can't satisfy it. Local mypy runs passed
  all session because this sandbox's `.venv` had `opentelemetry-api`
  installed from earlier, unrelated otel-plugin work. Fixed with a
  `[[tool.mypy.overrides]]` for `opentelemetry.*` rather than adding the
  extra to `dev` (which would force every contributor to pull in the
  OTel SDK just to type-check, against ADR's zero-required-dependencies
  design).
- **`plugin-contract-tests (whytrail-fastapi)` and `(whytrail-rq)`
  failed with pytest exit 5 ("no tests collected").** Both test files
  use a module-level `pytest.importorskip()` for a package neither
  plugin's own `pyproject.toml` declares (correctly -- `fastapi`/`httpx`
  and `fakeredis` are test-simulation tools, not runtime dependencies of
  a Starlette-level middleware or of RQ itself). A collection-time skip
  reports as "no tests ran," not a failure, so this only surfaced as a
  loud CI failure, not a silent gap -- but it also silently ran zero
  redaction/safety assertions for two plugins every time the job showed
  green before now, including the security-sensitive
  `whytrail-fastapi`. Fixed by adding a `test` extra to each plugin's
  `pyproject.toml` and having CI request `[test]` uniformly (pip just
  warns for the ~28 plugins that don't declare one).
- **`plugin-version-matrix` ran 2 jobs instead of the intended 60.**
  `strategy.matrix.include` entries only merge into a matrix when they
  share a key with an existing axis; a bare `plugin`/`dependency`/`floor`
  include list shares no key with a separate `dependency-version:
  [floor, latest]` axis, so GitHub produced 2 jobs with no plugin
  context instead of 30 plugins x 2 versions. Not something any local
  YAML/mypy/pytest check parses or could have caught. Fixed by making
  every one of the 60 combinations an explicit `include` entry.

### VS Code extension scope assessment

Added `docs/adr/0005-vscode-extension-scope.md`: scopes the VS Code
extension idea flagged during the category-strategy review as the
highest-visibility adoption lever, which had never been examined past
that one-line claim. Finds a real MVP (drive the existing `whytrail run
--json` CLI from a webview -- no `debugpy` forking needed) and a real
prerequisite gap it would create (`ExplanationStep.location` is an
unstructured `"file:line, in func"` string; a click-to-jump command
would need to parse it back apart, and a naive colon-split breaks on
Windows paths). Decision: not now -- building an editor extension for a
library with zero published releases inverts the adoption funnel it's
meant to serve. No code changed; the assessment exists so the idea has
somewhere to land next time it comes up instead of restarting from zero.

### mkdocs documentation site

Added `mkdocs.yml` (Material theme, light/dark palette, Mermaid fence
support for `Explanation.graph()` output) plus a GitHub Pages deploy
workflow (`.github/workflows/docs.yml`) that builds on push to `main`.
`docs/index.md` and `docs/changelog.md` are thin `include-markdown`
wrappers around `README.md`/`CHANGELOG.md` rather than copies, so the
site can't drift from what a `git clone` or the PyPI page already show.
Nav covers the plugin guide, testing-maturity note, and the ADRs.
`mkdocs build --strict` passes clean; the only findings were expected
(links from the ADRs/plugin-guide into `src/`/`plugins/`/`tests/`,
written to be read on GitHub where they resolve against the whole repo
tree, correctly don't resolve inside a docs-only site -- downgraded to
informational in `mkdocs.yml` rather than either failing the build or
rewriting ~40 links to absolute GitHub blob URLs for a purely cosmetic
gain).

### Renamed to whytrail; protocol freeze; version-matrix expanded to all 30 plugins

- **Renamed `butwhy` to `whytrail`** across the entire repository (package,
  30 plugin distributions, entry-point group, docs, CI). Forced by a PyPI
  name collision: `butwhy` was already published by an unrelated project
  whose pattern-matching/confidence-percentage approach is philosophically
  the opposite of this library's "honest unknown, never fabricated" design
  (ADR §11) -- publishing under that name would have looked like an
  imitation. Full reasoning, the candidate names checked, and what changed
  mechanically are in `docs/adr/0004-rename-to-whytrail.md`.
- **`mypy --strict`** now runs in CI (`test` job) and passes clean across
  all 19 core source files. Found 8 real gaps, all fixed: missing type
  parameters on generics (`weakref.finalize`, `contextvars.Token`,
  `Callable`), one genuine typeshed gap (`weakref.finalize.atexit` is a
  real, documented, settable attribute at runtime that typeshed's stub
  doesn't declare), and one variable-scope bug mypy caught that a human
  reviewer plausibly wouldn't (a loop variable and a later `next(...,
  None)` result sharing a name with different, mypy-incompatible types in
  the same function scope, in `whytrail/__init__.py`'s traversal code).
- **Confidence markers made legible without reading the source**: `.text`
  now prints `[explicit]`/`[inferred]`/`[heuristic]` instead of the
  original `==`/`~~`/`..` glyphs (ADR 0002 §3 item 2).
- **`Explanation.text`'s single-dominant-path summary now says when it's
  hiding something**: a step with more than one real parent (a diamond in
  the provenance graph) now appends "(+N other paths, see .graph())"
  instead of silently picking the highest-confidence one and saying
  nothing about the rest (ADR 0002 §3 item 3).
- **`register_plugin` renamed to `register_from_plugin`**, disambiguating
  it from the user-facing `register()` at the call site, not just in
  the docstring.
- **Explainer Protocol frozen as v1**
  (`whytrail.registry.EXPLAINER_PROTOCOL_VERSION`), independent of
  whytrail's own package version, so a plugin's compatibility isn't tied
  to guessing which whytrail releases are safe (ADR 0002 §3 item 6). What's
  covered and what a v2 would require is documented in
  `docs/plugin-guide.md`'s "Protocol version" section.
- **Windows/Linux CI audit**: checked core and all 30 plugins for
  fork/multiprocessing/Unix-only-stdlib/hardcoded-path assumptions that
  would pass on this repo's Windows dev environment but break on the CI
  matrix's `ubuntu-latest`/`macos-latest` runners. Found nothing beyond
  the already-fixed `whytrail-rq` `os.fork()` case; the actual runners have
  still never executed, since this repository isn't pushed to GitHub yet.
- **Version-matrix CI extended from 2 plugins to all 30**, finding ten
  more real Python-3.13 dependency-floor bugs beyond the two that started
  the job (`whytrail-pydantic`, `whytrail-sqlalchemy`): missing 3.13
  wheels (`pyyaml`, `grpcio`, `ddtrace`, `pandas`), a genuine C-API
  incompatibility (`asyncpg`), a stdlib module removed by a later Python
  (`marshmallow`'s `distutils` import, PEP 632), and transitive-dependency
  drift where an old floor's own unpinned sub-dependency moved on and
  broke it (`requests`'s bundled-urllib3-six shim, `prefect`'s `griffe`
  internal import). Full list and corrected floors in
  `docs/testing-maturity.md` and `.github/workflows/ci.yml`.

### Phase 2: closing part of the testing-maturity gap

Full detail in `docs/testing-maturity.md`, updated alongside this work
rather than left describing an earlier state of the project.

- **Property-based redaction testing**
  (`tests/plugin_contract/test_redaction_fuzz.py`): 9 plugins,
  ~40 Hypothesis-generated values each (360 total) fed through the real
  redaction mechanism, replacing "one hand-picked secret per plugin"
  with a property that has to hold broadly. Two rounds of narrowing the
  generated-text strategy were themselves real findings about the test
  methodology (not the plugins): single-character secrets trivially and
  meaninglessly collide with legitimate numbers already in a
  description (an HTTP status "404" contains "0"), and some plugins
  store `repr(value)` rather than the raw value, so escaped
  representations of backslashes/non-ASCII whitespace are what appear
  in output, not the literal character -- correct behavior, just not a
  literal substring match.
- **Concurrency testing for the safety-critical web middleware**
  (`tests/plugin_contract/test_web_concurrency.py`): 30 simultaneous
  requests to FastAPI, Flask, and Django, each carrying a unique
  secret, verifying no response ever contains another request's data.
  All three passed with no code changes required -- the fix was to the
  *test's* transport choice, not whytrail: a raw `httpx.ASGITransport`
  re-raises exceptions after an `Exception`-class handler runs (documented
  Starlette behavior, for ASGI-server-level logging), which
  `TestClient`'s `raise_server_exceptions=False` exists specifically to
  suppress; switched to `TestClient` + a thread pool, matching the
  pattern already used for Flask/Django.
- **Version-matrix CI** (`.github/workflows/ci.yml`'s
  `plugin-version-matrix` job): tests each plugin's stated minimum
  dependency version against the latest, for `whytrail-pydantic` and
  `whytrail-sqlalchemy` so far. Checking this for real, locally, before
  writing the CI job found two real bugs immediately: `pydantic==2.0.3`
  (the stated `pydantic>=2.0` floor) has no prebuilt wheel for Python
  3.13 and fails to build from source against it; `sqlalchemy==2.0.0`
  (the stated `sqlalchemy>=2.0` floor) installs but crashes on import
  on Python 3.13, since its `TypingOnly` assertion doesn't account for
  two new attributes CPython 3.13 added to every class. Neither gap
  was visible from the version numbers in `pyproject.toml` alone.

### 21 more plugins (30 total), and an honest coverage note

Full reasoning in `docs/adr/0003-ecosystem-scale-triage.md`. Added:
`whytrail-httpx`, `whytrail-aiohttp`, `whytrail-huggingface-hub`,
`whytrail-openai`, `whytrail-anthropic`, `whytrail-google-cloud`,
`whytrail-asyncpg`, `whytrail-pymongo`, `whytrail-grpcio`, `whytrail-marshmallow`,
`whytrail-jsonschema`, `whytrail-pyyaml`, `whytrail-polars`, `whytrail-ddtrace`,
`whytrail-rq`, `whytrail-dramatiq`, `whytrail-prefect`, `whytrail-scrapy`,
`whytrail-flask`. Deferred with reasons, not silently skipped: `psycopg2`
(needs a real PostgreSQL server -- its error attributes are C-level
read-only outside a real connection), `Playwright`/`Selenium` (need
browser binaries unavailable in this environment), `Airflow` (heavy
transitive dependency footprint), `LlamaIndex` (architecturally
identical to `whytrail-langchain`'s already-proven pattern). Confirmed
`redis-py` needs no plugin at all (checked directly, not assumed): its
exceptions carry no structured data beyond the message string.

**A test-coverage limitation, stated plainly rather than left implicit.**
Every plugin's tests run against a real object from the real library and,
where relevant, verify the redaction default explicitly -- that caught
several real bugs (see below). That is a genuinely higher bar than "the
code looks right," but it is not the same claim as "works in any
condition." None of these 30 plugins are tested across a version matrix
(only whatever `pip` resolved during development), against the full
breadth of each library's exception hierarchy, under concurrent load, or
on any OS besides Windows (this environment). See
`docs/testing-maturity.md` for the specific gap and what closing it would
require.

**Bugs these tests caught, worth naming because they're the actual
argument for writing them:**
- `whytrail-asyncpg`, `whytrail-pymongo`, `whytrail-jsonschema`: each library's
  own message text (`str(exc)`, `exc.args[0]`, or `.message`) turned out
  to embed the exact value the plugin was supposed to redact --
  discovered by a test asserting the value's absence, not by reading the
  library's source first.
- `whytrail-scrapy`: pydispatch's default weak-reference receivers meant
  the signal handler was silently garbage-collected the instant
  `install()` returned -- in production this would have looked like the
  integration doing nothing, with no error raised anywhere.
- `whytrail-rq`: an early version of its own test used `is_async=False`,
  which executes a job synchronously at `enqueue()` time before the
  worker (and its exception handler) exists -- the test was accidentally
  asserting nothing, caught because the assertions still failed instead
  of passing vacuously.

### Pre-1.0 API fixes from the category strategy review

Applied before building further plugins on top of the public API, per
`docs/adr/0002-category-strategy.md` §3's severity ranking (items that are
costly to change after other code depends on them):

- **Removed `trace()`'s decorator form.** `@whytrail.trace(...)` and
  `@whytrail.tracked` were two similarly-spelled decorators with genuinely
  different meanings. `trace()` is context-manager-only now; mark a
  function for capture with `@tracked`, open a scope with `with trace():`.
- **Shrank the top-level namespace.** `NodeKind`, `EdgeKind`,
  `ProvenanceGraph`, `TraceScope`, `SupportsWhy` are no longer in
  `whytrail.__all__` -- still importable from their submodules
  (`whytrail.core.node`, `whytrail.core.graph`, `whytrail.runtime.context`,
  `whytrail.protocols`). `Explanation`, `ExplanationStep`, and `Confidence`
  stay at the top level despite the review's stricter suggested list,
  because they're the vocabulary of writing an explainer -- a mainstream
  activity documented in `docs/plugin-guide.md`, not an advanced one.

#### Core fix: locals moved to a dedicated, redactable field

Found while wiring up `whytrail-sentry`: locals were embedded directly in
`ExplanationStep.description` text, which meant any integration exporting
an `Explanation` off-box (Sentry, OTel) shipped raw local variable values
with no way to strip them. `ExplanationStep` now has a separate
`locals: dict[str, str] | None` field, and `Explanation.redacted()`
returns a copy with every step's locals cleared. `whytrail.otel.record()`
and `whytrail_sentry.before_send()` both redact by default now, with an
explicit `include_locals=True` opt-in. See ADR 0002 §3 item 5.

#### Nine ecosystem integrations, plus a generator and a triage for the next ~150

Documented in `docs/adr/0002-category-strategy.md` (tiering) and
`docs/adr/0003-ecosystem-scale-triage.md` (the "how far does this scale"
question, answered against ~100 real libraries rather than assumed):

- **`whytrail-pytest`** -- explanation section on failing test reports
  (`pytest11` entry point, `report.sections`).
- **`whytrail-sentry`** -- attaches explanations to captured events via
  Sentry's `before_send` hook.
- **`whytrail-pandas`** -- diagnostic for an *untracked* DataFrame/Series
  (shape, dtypes, null counts); steps aside once the object is tracked,
  since generic `track()`/`@tracked` already handles that case with zero
  pandas-specific code.
- **`whytrail-sqlalchemy`** -- `StatementError` statement + params (params
  via the redactable `locals` field).
- **`whytrail-fastapi`** / **`whytrail-django`** -- safe-by-default exception
  handling: production response is a generic 500 with zero explanation
  detail; richer detail and raw locals each need a separate, explicit
  opt-in. The highest-severity item from the strategy review (§3 item 5),
  resolved with a full test suite covering every safety boundary, not
  just the happy path.
- **`whytrail-celery`** -- logs an explanation (+ redacted task args) on
  `task_failure`.
- **`whytrail-langchain`** -- chain/LLM/tool/retriever provenance via
  LangChain's callback system, architecturally mirroring the
  `sys.monitoring` deep-trace backend (a start event opens a Call node, an
  end event links it to its output, nested runs link via
  `OCCURRED_DURING`). Identified in the category strategy review as the
  highest-leverage integration *not* in the original brainstorm.
- **`whytrail-pydantic`** -- per-field `ValidationError` breakdown, bad
  values redacted by default.
- **`whytrail-boto3`** -- structured `ClientError` detail (AWS error code,
  message, HTTP status, request ID), resolving correctly against
  botocore's dynamically-generated per-service exception subclasses via
  the MRO walk.
- **`scripts/new_plugin.py`** -- scaffolds a new plugin's boilerplate for
  either shape (registry-based explainer or hook-based integration);
  deliberately does not generate explainer logic itself.
- **`.github/actions/whytrail-run`** -- composite GitHub Action wrapping
  the CLI for CI use; **`.github/workflows/ci.yml`** -- this repo's own
  test matrix, with plugin contract tests kept in a separate job per
  plugin so one plugin's dependency bump can't block a core-only PR.

## [0.1.0] - initial implementation

Pre-1.0: public API may still change. Implements the full roadmap from
`docs/adr/0001-whytrail-architecture.md` through the v3.0 buildable slice
in one pass; still labeled 0.1.0 rather than 1.0.0 because the packaging
policy in the ADR reserves 1.0 for after real-world plugin ecosystem
validation (currently one reference plugin, `whytrail-requests`, not the
two-to-three called for).

### Tier 1 -- zero configuration
- `why(exception)`: reconstructs a causal chain from `__traceback__`,
  `__cause__` (explicit), `__context__` (implicit, confidence-marked
  lower), and locals at the frame where the exception actually
  originated. Respects `raise ... from None` suppression.

### Tier 2 -- opt-in, scoped
- `track(obj, *, label=None, derived_from=None, **metadata)`.
- `@tracked` decorator: links function arguments -> a Call node -> the
  return value or raised exception.
- `trace(*, graph=None, sample_rate=1.0, max_depth=8, deep=False)`:
  context manager and decorator; reentrant under recursion/concurrency.
- `ProvenanceGraph`: weakref-based tombstoning on garbage collection,
  bounded retention (`max_nodes`, FIFO eviction).

### Explainability
- `Explanation`: `.text`, `.json()`, `.graph()` (Mermaid), `.rich()`
  (requires the `rich` extra). Confidence levels (explicit / inferred /
  heuristic / unknown) surfaced throughout; an untracked object gets an
  honest "unknown," never a fabricated chain.
- `__why__` protocol (`SupportsWhy`): opt-in, duck-typed, same shape as
  `__repr__`.
- Plugin registry: `register()` (manual, always wins) and
  `register_from_plugin()` (entry-point group `whytrail.explainers`, lazy
  discovery via `importlib.metadata`). Validated against a real installed
  plugin distribution, not a registry mock.

### v2.0 pieces
- `trace(deep=True)`: auto-instruments calls via `sys.monitoring` (PEP
  669), Python 3.12+ only, with a clear `RuntimeError` on older
  interpreters. Documented cost: PEP 669 events are process-wide once
  enabled.
- `whytrail` CLI (`whytrail run script.py [--json] [--graph]`): runs a
  script, prints `why()` instead of a bare traceback on an uncaught
  exception.
- `snapshot()` / `restore()`: JSON-lines graph persistence and replay.

### v3.0 buildable slice
- `whytrail.propagation`: `inject()`/`extract()`/`continue_trace()`,
  OTel-propagator-shaped context carrying for cross-process calls. No
  transport or remote graph merge -- that's real distributed-tracing
  infrastructure, out of scope for a library.
- `whytrail.otel`: attaches an `Explanation` to the current OpenTelemetry
  span as an event (`otel` extra).

### Explicitly not built
- A distributed provenance graph store/service, and a hosted web
  visualization UI -- both are infrastructure with a network/storage
  surface, not library features; see ADR 0001's "Decision: what v3.0
  actually is."
- Row-level pandas/dask/Spark lineage -- a natural next plugin
  distribution following the `whytrail-requests` pattern, not core work.
- AST import-hook "compile mode" capture -- deferred, see ADR 0001.

### Packaging
- `whytrail`: core, zero required dependencies, `py.typed`.
- Extras: `rich`, `cli`, `otel`.
- `plugins/whytrail-requests`: reference plugin distribution.
