# Testing maturity: what's verified, what isn't

This project has 692 tests (679 passing plus 12 skipped for extras not
installed in a given environment, and one pre-existing, unrelated
failure -- `test_snowflake_redaction`, a Hypothesis-fuzzed case where
the literal string "sqlstate" leaks into a Snowflake driver's own
message text; found while verifying the 0.3.1 batch below, confirmed
via `git stash` to already fail on unmodified `main`, not something
this pass introduced or fixed) across core whytrail and 100 bundled
integrations (ADR 0006 -- extras of the one `whytrail` package, not
separate distributions) -- 63 reached the previous resting point, and a
0.3.1 push added 37 more (see `CHANGELOG.md`). Every plugin's tests run against a real object from the
real library rather than a mock, a representative sample of the
redaction-critical ones are now property-tested rather than
spot-checked, and the safety-critical web middleware, task-queue
integrations, and observability integrations are all verified under
real concurrent load. That's a meaningfully higher bar than "the code
looks correct" -- it caught real bugs (see below), including twenty
version-compatibility bugs across two rounds of finding them: an initial
local pass (Windows, before this project had ever run on real CI), and a
second, different set found only once the workflow actually executed on
GitHub's Linux/macOS/Windows runners for the first time -- several
plugins this project had locally called "confirmed fine" turned out not
to be, once something other than "does it install and import" was
actually checked. It is still a different and smaller claim than "works
in any condition," and this document exists so nobody mistakes one for
the other.

**A pass explicitly aimed at closing gaps #1, #2 (partially), and #3
below** (rather than adding features) widened three things that were
already checked for real elsewhere in this document, using the same
mechanisms, not new ones: redaction property-fuzzing from 11 targets to
22 (`tests/plugin_contract/test_redaction_fuzz.py`), concurrency testing
from the three web frameworks to the task-queue and observability
integrations (`test_task_queue_concurrency.py`,
`test_observability_concurrency.py`), and the version-matrix's Python
coverage from 3.13-only to 3.10-3.13
(`plugin-version-matrix-py-range` in `ci.yml`, weekly-gated). Checking
each candidate against real plugin source before writing a test found
three named Phase I candidates (`boto3`, `aiohttp`, `marshmallow`) don't
actually have a redaction-critical field to fuzz at all -- each
plugin's own docstring already said so -- and caught two real bugs in
the new tests themselves (a `requests.Response.text` charset-detection
mismatch, and an `except ... as exc` variable-scoping bug in a
hand-written test), both fixed the same way every other bug in this
document was: the test failed first, then the cause was found.

**A second pass aimed at the shared engine itself, not the plugin
ecosystem** (`core/graph.py`, `core/serialize.py`, `core/explanation.py`,
`why()`'s own implementation), found and fixed two real bugs in
whytrail's own code, not just in tests: `core/graph.py`'s FIFO eviction
never cleaned up `_object_to_node`/`_finalizers`, so either dict grew
unboundedly whenever an evicted node's object was still alive (found by
a 50,000-object soak test, `tests/integration/test_graph_soak.py`); and
`core/serialize.py`'s `loads()` silently dropped any snapshot line with
an unrecognized `"type"`, contradicting its own docstring (found by a
negative test, `tests/unit/test_chaos_and_recovery.py`). Also added: a
Hypothesis `RuleBasedStateMachine` running randomized track/why/
snapshot/restore sequences (`tests/integration/test_stateful_graph.py`,
which also found a real, previously-unverified serialize round-trip
asymmetry, now documented directly in `core/serialize.py`); targeted
fault injection at `why()`'s real internal call sites confirming its
"never raises" promise (ADR §19) holds under `MemoryError`/
`RecursionError`/`OSError`/`ImportError`/`PermissionError` and that its
boundary is also correct (`KeyboardInterrupt`/`SystemExit` still
propagate); an API-invariant battery of 15 pathological inputs; and a
weekly, informational mutation-testing job (`mutmut`, scoped to
`core/`) -- see `CHANGELOG.md` for the full account, including three
real bugs found in this round's own test harness along the way (a
`__slots__` class missing `"__weakref__"`, silently defeating its own
weakref test; two fault-injection tests patching the wrong module
reference and never actually firing their simulated fault until
rewritten as `pytest.raises` checks that failed loudly instead of
passing vacuously). Running mutation testing for the first time found
450 mutants against `core/`, 128 surviving; investigating the
highest-value ones (graph eviction bookkeeping, serialize round-trip
field preservation) closed 8 of them with real regression tests and
confirmed 2 more as equivalent mutants, not gaps. The remaining ~119,
concentrated in `core/explanation.py`'s rendering helpers, are a real,
named, uninvestigated remainder -- see gap #8 below and `CHANGELOG.md`
for the full breakdown, rather than mechanically forcing a
0-survivor count.

## What the current test suite actually verifies

- **The integration mechanism is real.** An entry point resolves, a
  signal fires, a middleware wraps correctly, a callback is invoked --
  checked by exercising the real hook, not by asserting a function was
  called with the right mock arguments.
- **The happy path produces a correct explanation** from a real,
  concretely-constructed instance of the library's exception or object
  type -- a real `sqlalchemy.exc.IntegrityError` from an in-memory
  SQLite database, a real `botocore.exceptions.ClientError` via
  `Stubber`, a real LangChain chain invocation, a real gRPC error from
  an in-process server over loopback.
- **The safety-critical paths are verified against a known-sensitive
  value, not merely designed to look right**, for every plugin that
  touches something that could be sensitive (SQL params, validation
  input, task payloads, response bodies) -- and, for eleven of them
  (nine Tier 1 exception explainers, plus `track()` and
  `whytrail.config.env()` themselves since a 0.3 audit found
  `Explanation.redacted()` had never been fuzzed against the Tier 2
  path at all), are now **property-tested against ~40 generated values
  each (440 total)** via Hypothesis
  (`tests/plugin_contract/test_redaction_fuzz.py`) rather than one
  hand-picked string. Every generated value is first confirmed present
  in the *unredacted* output before checking it's absent from the
  redacted one -- proving the value was actually captured, not that
  the check is vacuous.
- **The safety-critical web middleware holds under real concurrent
  load**: 30 simultaneous requests to FastAPI/Flask/Django, each
  carrying a unique secret, with `include_locals_in_response=True`
  (maximizing what would be observable if request isolation broke) --
  every response contains only its own secret, never another request's
  (`tests/plugin_contract/test_web_concurrency.py`).
- **A plugin's stated minimum dependency version is confirmed to
  actually install and pass its tests on the newest supported Python**,
  now for all 60 plugins -- not assumed from the version number in
  `pyproject.toml`. This is what found the twenty version-compatibility
  bugs below, twelve locally and eight only once real CI ran.
- **Precedence contracts hold**: a user's manual `whytrail.register()`
  always wins over a plugin's `register_from_plugin()`, verified per plugin,
  not just in core.

## Bugs this level of testing found, worth naming

- **`whytrail-asyncpg`, `whytrail-pymongo`, `whytrail-jsonschema`,
  `whytrail-pyyaml`**: each library's own message/tag text turned out to
  embed the exact value the plugin was supposed to redact -- found by
  a test asserting the value's absence, not by reading source first.
- **`whytrail-scrapy`**: pydispatch's default weak-reference receivers
  meant the signal handler was silently garbage-collected the instant
  `install()` returned; the integration would have done nothing in
  production, with no error anywhere.
- **`whytrail-rq`**: an early version of its own test used
  `is_async=False`, executing the job synchronously at `enqueue()` time
  before the worker (and its exception handler) existed -- the test was
  accidentally asserting nothing.
- **Twenty dependency-floor bugs, found by the version-matrix job
  across two rounds** -- twelve found locally (Windows) once the job
  was extended from 2 plugins to all 30, and eight more found only once
  the job actually ran on real `ubuntu-latest` CI for the first time.
  The gap between the two rounds is itself a finding: several plugins a
  local "does it install and import" check called fine turned out
  broken the moment a real CI run actually exercised each plugin's
  contract tests against its pinned floor.

  Round one (local, install-and-import level):
  - **No prebuilt Python 3.13 wheel, source build also fails**:
    `pydantic==2.0.3` (`typing` internals changed; first working:
    2.8.0), `pyyaml==6.0` (Cython/setuptools mismatch; first working:
    6.0.2), `grpcio==1.60.0` (first working: 1.66.2), `pandas==2.0.0`
    (first working: 2.2.3).
  - **Installs, crashes on import -- genuine 3.13 runtime
    incompatibility, not a packaging gap**: `sqlalchemy==2.0.0` (its
    `TypingOnly` assertion predates two dunders 3.13 added to every
    class; first working: 2.0.36), `asyncpg==0.29.0` (`pgproto.c`
    calls a C API function with the pre-3.13 argument count; first
    working: 0.30.0).
  - **Uses a standard-library module removed by a later Python
    version**: `marshmallow==3.0.0` imports
    `distutils.version.LooseVersion`, removed in 3.12 by PEP 632
    (first working, by bisection: 3.15.0).
  - **Transitive dependency drift**: `requests==2.20.0` imports
    `urllib3.packages.six.moves`, a shim urllib3 2.0 removed (first
    working, by bisection: 2.25.0).

  Round two (real CI, found by Docker/WSL2 reproduction on actual Linux
  after Windows couldn't reproduce compiled-package issues reliably):
  - **Passed local install-and-import, crashes for real**:
    `sentry-sdk==2.0.0` copies frame locals via `copy.copy()`, which
    breaks against Python 3.13's `FrameLocalsProxy` (PEP 667) -- only
    surfaced once its actual capture path ran against a real exception.
    First working, by bisection: 2.11.0.
  - **Not fixable within the floor's major-version line at all**:
    `prefect==2.14.0`-`2.20.0`'s `GatherTaskGroup` (its own
    `asyncio.TaskGroup` subclass) doesn't implement an abstract method
    3.13's `asyncio` added -- independent of the `griffe`/pydantic
    issues also present on the same versions. Floor moved to the 3.x
    line: 3.7.8. Same pattern for `huggingface_hub==0.20.0`: the
    `huggingface_hub.errors` module the plugin imports didn't exist
    until 0.22, and `hf_raise_for_status()`'s response handling didn't
    match until the 1.x line. First working: 1.0.0.
  - **More transitive dependency drift**: `flask==2.3.0`'s
    `testing.py` reads `werkzeug.__version__`, removed by werkzeug 3.x
    (first working: 2.3.3).
  - **Plugin/test written against a newer SDK API than the stated
    floor provides** (not a Python-version or drift issue -- just an
    old client library): `ddtrace==2.0.0` (the test imports
    `ddtrace.trace.tracer`, a singleton added later; first working:
    2.20.0), `openai==1.0.0` and `anthropic==0.30.0` (both read
    `exception.body`, whose shape didn't match until later releases;
    first working: 1.30.0 and 0.34.0, both by bisection).
  - **Not independently version-testable as originally set up**:
    `whytrail-fastapi`'s entry pinned `starlette` alone, but the test
    builds a real FastAPI app -- an old starlette floor against a
    separately-installed newer fastapi breaks on an unrelated
    `TestClient` API mismatch. Switched the pinned dependency to
    `fastapi` itself (floor: 0.115.0).

  Every other plugin's stated floor (`boto3`, `httpx`, `django`,
  `celery`, `dramatiq`, `rq`, `langchain-core`, `google-api-core`,
  `pytest`, `jsonschema`, `scrapy`, `polars`, `aiohttp`, `pymongo`) was
  checked the same way on real CI and confirmed to already work -- not
  assumed, just not (yet) found broken. Every plugin's floor in
  `pyproject.toml` is left as-is, since it's still technically correct
  for older supported Python versions; `.github/workflows/ci.yml`'s
  `plugin-version-matrix` job now pins the *actually*
  Python-3.13-compatible floor for every plugin instead, so a future
  dependency bump that reintroduces any of these gaps fails CI instead
  of shipping silently. Full detail on each fix is in that job's own
  comment block, not duplicated here.

## What still isn't verified

1. **Version compatibility beyond Python 3.13, partially closed.** A
   new `plugin-version-matrix-py-range` job in `ci.yml` now installs
   every extra's *original* `pyproject.toml`-stated floor (not the
   3.13-corrected floor `plugin-version-matrix` pins) against Python
   3.10/3.11/3.12 and runs its real contract test -- 186 jobs (62
   extras x 3 versions). Deliberately weekly-`schedule`-gated rather
   than on every push, the same cost/signal tradeoff `plugin-version-
   matrix` itself already applies at 1x scale (see that job's own
   comment and `docs/roadmap.md` Phase H). This closes the mechanism
   gap, not the evidence gap: as of this writing the job has been
   added but never actually executed on a real GitHub Actions runner
   (it only fires on the Monday 06:00 UTC schedule or the next
   `schedule` trigger) -- following this document's own standard, that
   means "the check now exists," not "3.10-3.12 are confirmed working."
   Update this item once the job has actually run.
2. **The library's full exception surface.** Most plugins exercise one
   or two exception subtypes out of the library's real hierarchy --
   `whytrail-sqlalchemy` is tested only against SQLite's `IntegrityError`,
   not `OperationalError`/`ProgrammingError` or other DBAPI drivers;
   `whytrail-pydantic`'s fuzz coverage is one field (an int type
   mismatch), not nested models, discriminated unions, or custom
   validators. Redaction-fuzz coverage specifically (a narrower claim
   than "full exception surface") widened from 11 to 22 targets in the
   same pass that closed item 1 above -- see this document's opening
   note.
3. **Concurrency beyond the three web frameworks, mostly closed.**
   Celery, dramatiq, and RQ (`test_task_queue_concurrency.py`) and
   Sentry, ddtrace, and OTel (`test_observability_concurrency.py`) are
   now verified under real concurrent load, the same "N calls, each
   carrying a unique secret, assert no cross-contamination" pattern
   `test_web_concurrency.py` already established. Two real scope limits,
   named rather than hidden: RQ's own concurrency model is
   `os.fork()`-based process isolation (see item 5 below), so what's
   actually tested there is whytrail's installed handler function
   called concurrently, not RQ's real worker fleet; and Prefect is not
   included at all -- `whytrail.integrations.prefect`'s own module
   docstring already states it doesn't capture task arguments the way
   the other three do, so there's no locals-bearing state for a
   cross-contamination test to meaningfully exercise.
4. **Scale and pathological input.** A validation error with hundreds
   of nested fields, a multi-gigabyte DataFrame, a malformed or huge SQL
   statement -- untested.
5. **Cross-platform behavior, partially closed.** The CI workflow has
   now actually run on `ubuntu-latest`/`windows-latest`/`macos-latest`
   (first push to `github.com/bhouvana/Whytrail`), and validated the
   concern that prompted this item: 45 of 47 jobs failed on the very
   first run, all three root causes real and all invisible to every
   local check this project had run until then (see `CHANGELOG.md`'s
   "first real CI run" entry) -- a mypy override missing for an
   intentionally-optional import, two plugins' test files silently
   depending on undeclared test-only tools, and a CI matrix
   configuration bug that quietly ran 2 jobs instead of the intended
   60. All three are fixed, but this is one data point, not a track
   record: the OS-parity claim now rests on whatever the *next* few
   pushes show, not on zero evidence. Separately, and still fully open:
   `whytrail-rq`'s tests use `SimpleWorker` specifically because RQ's
   default `Worker` calls `os.fork()`, which doesn't exist on Windows --
   meaning the code path real production deployments actually use (the
   default `Worker`, Celery's prefork pool) has still never run at all,
   on any OS, in this repository.
6. **Plugin-to-plugin interaction, partially checked.** `pip install
   whytrail[all]` plus the full test suite has now actually been run
   once with all 60 extras installed together (`pip check` clean, 359
   passed, 0 failed) -- previously this had never been done for real.
   One real cross-plugin interaction surfaced, cosmetic rather than a
   whytrail bug: `sentry-sdk`'s global logging monkeypatch
   (`logging.Logger.callHandlers`, installed automatically on import,
   independent of whether Sentry is actually configured) races with
   `prefect`'s own test-server teardown logging at interpreter
   shutdown, printing a `--- Logging error ---: ValueError: I/O
   operation on closed file` after pytest has already reported success.
   Both sides of that interaction are third-party code, not whytrail's
   -- worth naming so it isn't mistaken for a real failure if seen
   again, not something to fix here. This was one test run, not a
   track record; still not the same claim as "no interaction issues
   exist across all 60."
7. **No plugin sunset policy exists.** If an integration's upstream
   library stops releasing, changes its exception shape incompatibly,
   or a maintainer simply stops using it, there's no documented process
   for deprecating or removing that plugin -- it just stays in
   `registry._BUILTIN_EXPLAINERS` indefinitely. `ci.yml`'s weekly
   schedule trigger (added alongside this note) closes the *detection*
   half of this gap -- a floor break from a new upstream release no
   longer waits for an unrelated push to this repo to surface -- but
   detection isn't the same as a policy for what happens next when one
   fires and nobody's actively working on that plugin.
8. **~119 of 450 mutation-testing survivors against `core/`,
   uninvestigated.** The first real run found 128 survivors; 8 were
   real test gaps (fixed) and 2 were confirmed equivalent mutants, but
   the remaining ~119 -- sampled, not exhaustively triaged, concentrated
   in `core/explanation.py`'s rendering helpers -- were left as a named
   remainder rather than mechanically chased to zero. Some of that
   remainder is likely more equivalent mutants (confirmed for at least
   one sampled case); some may be real, lower-value gaps in exact
   string-formatting/styling decisions the existing behavioral tests
   don't pin down. Neither has been established at scale yet.

## What closing the rest of this gap would require

- **Watch the version-matrix's Python-range job actually run** on its
  weekly schedule (or trigger it manually) and fold the result back
  into item 1 above -- the mechanism exists now, the evidence doesn't
  yet.
- **Extend property-based testing** further, to more of each
  already-covered library's exception surface (not just one
  representative field/error type per plugin), and to `grpcio` if a
  cheaper-than-a-real-server construction path is ever found. `boto3`,
  `google-cloud`, and `requests`/`httpx`/`aiohttp`'s body previews are
  no longer open items: checked directly against each plugin's own
  source, `boto3` and `aiohttp` have no redaction-critical field to
  fuzz at all (both plugins' own docstrings say so), `google-cloud`
  was already covered, and `requests`/`httpx` are now covered too.
- **Triage the remaining ~119 mutation-testing survivors** against
  `core/explanation.py` in particular -- sample a wider set than the
  two checked so far to establish whether the remainder skews toward
  equivalent mutants (as both sampled cases did) or real, if low-value,
  formatting-detail gaps, rather than guessing at the ratio from two
  data points.
- **Watch the next several CI runs, not just the first.** The first run
  found and fixed three real bugs; that's evidence the check is worth
  having, not evidence the workflow is now trustworthy -- confidence
  here should come from a track record, the same way it does for the
  test suite itself.
- **Exercise the RQ default `Worker` (fork-based) path on Linux/macOS**,
  gated to non-Windows runners, instead of only ever testing
  `SimpleWorker`.
- **Scale/pathological-input tests** for the plugins most likely to
  encounter them in practice (pandas/polars with large frames,
  pydantic/jsonschema with deeply nested payloads).

This document is updated as that work happens, not written once and
left to go stale -- once this repository has a commit history, the
prior version of this file (before the fuzz tests, concurrency tests,
and version-matrix job existed) will be visible in it for anyone who
wants to see exactly what changed and why.
