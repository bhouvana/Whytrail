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

## [0.2.1] - elasticsearch, batch-1 plugin growth, plain-English explanations, ExceptionGroup support

Six units of work since 0.2.0, newest first. 297 tests pass total;
`mypy --strict` clean.

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
