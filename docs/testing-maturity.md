# Testing maturity: what's verified, what isn't

This project has 237 tests across core whytrail and 30 plugin
distributions. Every plugin's tests run against a real object from the
real library rather than a mock, a representative sample of the
redaction-critical ones are now property-tested rather than
spot-checked, and the safety-critical web middleware is verified under
real concurrent load. That's a meaningfully higher bar than "the code
looks correct" -- it caught real bugs (see below), including twelve
version-compatibility bugs found by actually installing every plugin's
stated minimum dependency version rather than assuming it works. It is
still a different and smaller claim than "works in any condition," and
this document exists so nobody mistakes one for the other.

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
  `pyproject.toml`. This is what found the twelve version-compatibility
  bugs below.
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
- **Twelve dependency-floor bugs, found by the version-matrix job**,
  once it was extended from 2 plugins to all 30 -- every one found by
  actually running `pip install <dep>==<stated-floor>` on Python 3.13
  and checking whether the result imports, not by reading a changelog:
  - **No prebuilt Python 3.13 wheel, source build also fails**:
    `pydantic==2.0.3` (`typing` internals changed; first working:
    2.8.0), `pyyaml==6.0` (Cython/setuptools mismatch; first working:
    6.0.2).
  - **No prebuilt Python 3.13 wheel anywhere, on any platform**:
    `grpcio==1.60.0` (first working: 1.66.2), `ddtrace==2.0.0` (first
    working: 2.19.0), `pandas==2.0.0` (first working: 2.2.3).
  - **Installs, crashes on import -- genuine 3.13 runtime
    incompatibility, not a packaging gap**: `sqlalchemy==2.0.0` (its
    `TypingOnly` assertion predates two dunders 3.13 added to every
    class; first working: 2.0.36), `asyncpg==0.29.0` (`pgproto.c`
    calls a C API function with the pre-3.13 argument count; first
    working: 0.30.0).
  - **Uses a standard-library module removed by a later Python
    version, not a dependency-vs-3.13 issue**: `marshmallow==3.0.0`
    imports `distutils.version.LooseVersion`, removed in 3.12 by PEP
    632 (first working, by bisection: 3.15.0).
  - **Transitive dependency drift -- the floor's own unpinned
    sub-dependency moved on and broke it**: `requests==2.20.0`
    imports `urllib3.packages.six.moves`, a shim urllib3 2.0 removed
    (first working, by bisection: 2.25.0); `prefect==2.14.0` through
    `2.19.0` import a `griffe` internal path a later `griffe` release
    removed (first working: 2.20.0).

  Every other plugin's stated floor (`boto3`, `httpx`, `flask`,
  `django`, `celery`, `dramatiq`, `rq`, `sentry-sdk`, `langchain-core`,
  `huggingface_hub`, `google-api-core`, `anthropic`, `openai`,
  `pytest`, `jsonschema`, `scrapy`, `polars`, `aiohttp`, `starlette`,
  `pymongo`) was checked the same way and confirmed to already work --
  not assumed, just not broken. Every plugin's floor in
  `pyproject.toml` is left as-is, since it's still technically correct
  for older supported Python versions; `.github/workflows/ci.yml`'s
  `plugin-version-matrix` job now pins the *actually*
  Python-3.13-compatible floor for every plugin instead, so a future
  dependency bump that reintroduces any of these gaps fails CI instead
  of shipping silently.

## What still isn't verified

1. **Version compatibility beyond Python 3.13.** The version-matrix job
   now covers all 30 plugins, but only against Python 3.13 -- 3.10/3.11/
   3.12 floors are asserted in `pyproject.toml` but never installed and
   checked the way 3.13's were, and the twelve bugs just found on 3.13
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
