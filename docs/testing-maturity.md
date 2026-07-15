# Testing maturity: what's verified, what isn't

This project has 237 tests across core whytrail and 30 plugin
distributions. Every plugin's tests run against a real object from the
real library rather than a mock, a representative sample of the
redaction-critical ones are now property-tested rather than
spot-checked, and the safety-critical web middleware is verified under
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
  input, task payloads, response bodies) -- and, for nine of them, are
  now **property-tested against ~40 generated values each (360 total)**
  via Hypothesis (`tests/plugin_contract/test_redaction_fuzz.py`)
  rather than one hand-picked string. Every generated value is first
  confirmed present in the *unredacted* output before checking it's
  absent from the redacted one -- proving the value was actually
  captured, not that the check is vacuous.
- **The safety-critical web middleware holds under real concurrent
  load**: 30 simultaneous requests to FastAPI/Flask/Django, each
  carrying a unique secret, with `include_locals_in_response=True`
  (maximizing what would be observable if request isolation broke) --
  every response contains only its own secret, never another request's
  (`tests/plugin_contract/test_web_concurrency.py`).
- **A plugin's stated minimum dependency version is confirmed to
  actually install and pass its tests on the newest supported Python**,
  now for all 30 plugins -- not assumed from the version number in
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

1. **Version compatibility beyond Python 3.13.** The version-matrix job
   now covers all 30 plugins, but only against Python 3.13 -- 3.10/3.11/
   3.12 floors are asserted in `pyproject.toml` but never installed and
   checked the way 3.13's were, and the twenty bugs just found on 3.13
   alone suggest that gap isn't hypothetical either.
2. **The library's full exception surface.** Most plugins exercise one
   or two exception subtypes out of the library's real hierarchy --
   `whytrail-sqlalchemy` is tested only against SQLite's `IntegrityError`,
   not `OperationalError`/`ProgrammingError` or other DBAPI drivers;
   `whytrail-pydantic`'s fuzz coverage is one field (an int type
   mismatch), not nested models, discriminated unions, or custom
   validators.
3. **Concurrency beyond the three web frameworks.** The task-queue
   plugins (Celery/RQ/dramatiq/Prefect) and Sentry/OTel/ddtrace capture
   paths are not tested under concurrent load -- only FastAPI, Flask,
   and Django are.
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
6. **Plugin-to-plugin interaction.** All 30 plugins have never been
   installed and exercised together in one process against the full
   registry resolution order at once.

## What closing the rest of this gap would require

- **Extend the version matrix to the full Python range (3.10-3.13)**,
  not just 3.13 -- every plugin is covered now, but only on the newest
  supported interpreter.
- **Extend property-based testing** to the plugins not yet covered
  (grpcio, boto3, google-cloud, requests/httpx/aiohttp's body previews)
  and to more of each already-covered library's exception surface, not
  just one representative field/error type per plugin.
- **Concurrency tests for the task-queue and observability plugins.**
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
