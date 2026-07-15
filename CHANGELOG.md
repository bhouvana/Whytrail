# Changelog

All notable changes to this project are documented here. Format loosely
follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased] - first real CI run found three bugs no local check could

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

## [Unreleased] - VS Code extension scope assessment

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

## [Unreleased] - mkdocs documentation site

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

## [Unreleased] - renamed to whytrail; protocol freeze; version-matrix expanded to all 30 plugins

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

## [Unreleased] - Phase 2: closing part of the testing-maturity gap

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

## [Unreleased] - 21 more plugins (30 total), and an honest coverage note

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

## [Unreleased] - pre-1.0 API fixes from the category strategy review

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

### Core fix: locals moved to a dedicated, redactable field

Found while wiring up `whytrail-sentry`: locals were embedded directly in
`ExplanationStep.description` text, which meant any integration exporting
an `Explanation` off-box (Sentry, OTel) shipped raw local variable values
with no way to strip them. `ExplanationStep` now has a separate
`locals: dict[str, str] | None` field, and `Explanation.redacted()`
returns a copy with every step's locals cleared. `whytrail.otel.record()`
and `whytrail_sentry.before_send()` both redact by default now, with an
explicit `include_locals=True` opt-in. See ADR 0002 §3 item 5.

### Nine ecosystem integrations, plus a generator and a triage for the next ~150

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
