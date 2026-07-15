# ADR 0003: Ecosystem-scale triage

**Status:** Accepted and build-out complete for this pass. Every
library marked `PLUGIN` or `PLUGIN (candidate)` below that was
practically buildable in this environment now has one -- 30 plugins
total (up from the 9 that existed when this ADR was first written).
See `docs/plugin-guide.md`'s table for the full current list; the
triage below is left as originally written, since the reasoning still
holds -- only the verdicts for a handful of specific libraries changed
after actually building against them, noted inline where relevant.

**What changed on contact with real code, beyond what the original
triage predicted:**

- **`redis-py`** was downgraded from "candidate, low priority" to
  **confirmed no plugin needed** -- checked directly rather than left
  as a guess: `redis.exceptions.OperationFailure` and its siblings
  carry no structured data beyond the message string, so there is
  nothing this ecosystem's model adds over tier 1.
- **`psycopg2`** could not be built in this environment: its
  `.pgcode`/`.pgerror` are C-level, read-only `member_descriptor`
  attributes populated only by a real PostgreSQL connection --
  confirmed by trying to set them and getting `AttributeError:
  readonly attribute`, not assumed. `asyncpg` (built instead) doesn't
  have this constraint; its equivalent fields are plain, settable
  Python attributes.
- **`pymongo`, `jsonschema`, `asyncpg`'s own `__str__`, and PyYAML's
  `ConstructorError.problem`** all turned out to bake the value they
  were being asked to protect directly into a string this plugin
  initially assumed was safe (the library's own message text) --
  caught by each plugin's own redaction test, not anticipated in
  advance. `docs/plugin-guide.md`'s table marks each of these with an
  asterisk and links to the specific finding.
- **`whytrail-scrapy`** had a real, silent-failure bug: pydispatch (which
  Scrapy's signals are built on) defaults to weak references, so the
  handler closure was garbage-collected the instant `install()`
  returned and the signal reached zero receivers -- in production this
  would have looked like the plugin doing nothing, with no error at
  all. Fixed with `weak=False`, caught by checking `send_catch_log`'s
  return value in a test, not by reading pydispatch's documentation.
- **`google.api_core.exceptions.GoogleAPICallError`** turned out to be
  the shared base every google-cloud-* client library raises from, not
  storage-specific -- one plugin (`whytrail-google-cloud`) covers
  storage, bigquery, pubsub, and firestore, verified against three
  different concrete exception types mapping to different underlying
  services, not just the one originally scoped.
- **`LlamaIndex`** was reassessed and deferred: architecturally
  identical to `whytrail-langchain`'s callback-based design, so building
  it now would mostly duplicate already-proven work rather than test
  anything new. A real candidate for later, not ruled out.

None of this changes the ADR's central claim -- if anything it
reinforces it. The value in this ecosystem came from testing against
real objects and finding out what the library actually does, not from
correctly guessing it in advance.

## Context

After nine real plugin distributions, the question became: does this
scale to covering the top ~150 Python libraries? The honest answer,
learned directly from building those nine (`whytrail-pandas` in
particular): **most libraries don't need a plugin at all.**
`DataFrame`/`Series` support `weakref` and `id()`-based identity like
any other Python object, so generic `track()`/`@tracked` already works
on them with zero pandas-specific code — the plugin only earns its
keep for the untracked-diagnostic case. That pattern holds for the
large majority of the ecosystem.

## Decision: three categories, not one

A library only warrants a dedicated plugin if it clears one of three
bars, all visible across the nine plugins already built:

1. **Structured domain error data a bare traceback discards** —
   `StatementError.statement`/`.params` (SQLAlchemy), `Response`/
   `RequestException.request` (requests), a validation error's
   per-field breakdown (Pydantic). The exception already knows more
   than `str(exc)` shows.
2. **A security-sensitive boundary needing safe-by-default design** —
   FastAPI/Django, where the actual work is redaction defaults, not
   explaining anything new.
3. **A non-standard capture mechanism** — LangChain's callbacks,
   Celery's signals, pytest's hooks. The object model itself doesn't
   need explaining; the *lifecycle* does.

A library that fails all three gets **no plugin**, and that's the
correct, final answer for it — not a placeholder for later. Building a
thin wrapper anyway is the "fifteen integrations done shallowly"
failure mode ADR 0002 §7 already rejected at n=15; doing it at n=150
would be the same mistake at ten times the scale, and would actively
damage trust in the plugin ecosystem's quality bar.

## Decision: a generator, not hand-written boilerplate each time

`scripts/new_plugin.py` scaffolds the pyproject.toml, package stub,
README, and starter test for either shape (`--kind explainer` for the
entry-point pattern, `--kind integration` for the hook-based pattern).
It deliberately does not attempt to generate the actual explainer
logic — that's the judgment call in category 1 above, not boilerplate.
Every `TODO` it emits is a place a human decision is still required.

## The triage

~100 libraries spanning the categories most represented in real
Python codebases. `PLUGIN` = clears one of the three bars above.
`GENERIC` = `why()` already works via `track()`/`@tracked` with no
library-specific code; a plugin would add polish, not capability.
`N/A` = no runtime object/exception surface `why()` has a role
against (build tooling, dev-time linters, low-level transitive deps).

### Web frameworks

| Library | Verdict | Why |
|---|---|---|
| Django | **PLUGIN** (built) | Safety-critical response boundary |
| FastAPI / Starlette | **PLUGIN** (built) | Safety-critical response boundary |
| Flask | PLUGIN (candidate) | Same middleware pattern as Django/FastAPI |
| aiohttp (server) | PLUGIN (candidate) | Same safety pattern, lower usage share |
| Tornado, Sanic | GENERIC | Declining share; safe-default pattern still applies if requested |
| uvicorn, gunicorn, hypercorn | N/A | Process servers, no app-level object model |

### HTTP clients

| Library | Verdict | Why |
|---|---|---|
| requests | **PLUGIN** (built) | `Response`/`RequestException` structured data |
| httpx | PLUGIN (candidate) | Same shape as requests, async-capable |
| urllib3 | GENERIC | Low-level; requests already covers most direct usage |

### Data / arrays

| Library | Verdict | Why |
|---|---|---|
| pandas | **PLUGIN** (built) | Untracked-diagnostic case; tracked case already generic |
| numpy | GENERIC | `ndarray` tracks via `id()`; diagnostic plugin possible, low priority |
| polars | PLUGIN (candidate) | Same diagnostic pattern as pandas, Rust-backed nulls/schema |
| pyarrow, scipy | GENERIC | No structured error surface beyond what tier 1 shows |
| dask | GENERIC / interesting | Its own lazy task graph *is* a provenance graph; interop, not a wrapper plugin |

### ML / AI

| Library | Verdict | Why |
|---|---|---|
| PyTorch | GENERIC | Tensors track via `id()`; autograd's own tape is the real provenance answer (ADR 0001 §13 already flags this as prior art, not a wrap target) |
| scikit-learn | GENERIC | Shape-mismatch diagnostic plugin possible, low priority |
| transformers / huggingface_hub | PLUGIN (candidate) | Specific HF exceptions carry structured detail |
| openai SDK | PLUGIN (candidate) | `APIError` carries `status_code`/`request_id`/response body |
| anthropic SDK | PLUGIN (candidate) | Same shape as openai |
| LangChain | **PLUGIN** (built) | Non-standard capture mechanism (callbacks) |
| LlamaIndex | PLUGIN (candidate) | Same callback-based pattern as LangChain |

### Databases / ORMs

| Library | Verdict | Why |
|---|---|---|
| SQLAlchemy | **PLUGIN** (built) | `StatementError` structured data |
| psycopg2 / psycopg | PLUGIN (candidate) | `.pgcode`/`.pgerror` structured fields |
| pymongo | **PLUGIN (built)** | `.code`/`.details`, fully redacted -- no safe driver string exists (found by testing) |
| asyncpg | **PLUGIN (built)** | `.sqlstate`/constraint/detail; `psycopg2` itself deferred, see status note above |
| redis-py | **GENERIC, confirmed** | Checked directly: no structured data beyond the message string |
| Tortoise ORM, peewee, `databases` | GENERIC | Lower adoption than SQLAlchemy; revisit on demand |

### Validation / serialization

| Library | Verdict | Why |
|---|---|---|
| Pydantic | **PLUGIN** (built, this ADR) | Per-field structured `ValidationError` data |
| marshmallow | PLUGIN (candidate) | Same shape as Pydantic |
| jsonschema | PLUGIN (candidate) | `.path`/`.schema_path` on `ValidationError` |
| cerberus | GENERIC, low priority | Smaller adoption |
| attrs, stdlib `dataclasses` | GENERIC | No meaningful error surface beyond `TypeError` |

### Task queues / schedulers

| Library | Verdict | Why |
|---|---|---|
| Celery | **PLUGIN** (built) | Non-standard mechanism (signals) |
| RQ, dramatiq | PLUGIN (candidate) | Same signal/hook shape as Celery |
| Prefect | PLUGIN (candidate) | Own state/exception model |
| Airflow | PLUGIN (candidate, deferred) | Heavy transitive dependency footprint (ADR 0002 §7 already flagged this) |
| APScheduler | GENERIC | No structured error surface |

### Testing

| Library | Verdict | Why |
|---|---|---|
| pytest | **PLUGIN** (built) | Non-standard mechanism (hooks) |
| hypothesis | GENERIC | Its own shrinking/falsifying-example output already solves this well |
| tox, nox, coverage.py | N/A | Orchestration/dev tooling, no runtime object model |
| unittest, `unittest.mock` | GENERIC | tier 1 already covers plain exceptions |

### CLI

| Library | Verdict | Why |
|---|---|---|
| click, Typer, argparse, Fire | GENERIC | Errors are already clear at the point of failure; low incremental value |
| Rich | N/A | Rendering library, not an error surface |

### Cloud SDKs

| Library | Verdict | Why |
|---|---|---|
| boto3 / botocore | **PLUGIN** (built, this ADR) | `ClientError` structured AWS error response data |
| google-cloud-* | PLUGIN (candidate) | Same structured-error shape |
| azure-sdk-for-python | PLUGIN (candidate) | Same shape |

### Observability

| Library | Verdict | Why |
|---|---|---|
| OpenTelemetry | **Interop, not a plugin** (built: `whytrail.otel`) | whytrail is upstream of it, not wrapping it |
| Sentry SDK | **PLUGIN** (built) | `before_send` hook, safe-by-default redaction |
| structlog, loguru | GENERIC | Logging libraries, not domain-exception sources |
| Datadog (`ddtrace`) | PLUGIN (candidate, low priority) | Same shape as Sentry |

### Serialization / config

| Library | Verdict | Why |
|---|---|---|
| PyYAML | PLUGIN (candidate) | `YAMLError` carries mark/line/column |
| toml/tomli, python-dotenv, configparser | GENERIC | Errors are already simple/clear |

### Date/time, security, parsing — and the deliberate "no"s

| Library | Verdict | Why |
|---|---|---|
| dateutil, pytz, arrow, pendulum, croniter | GENERIC | No structured error surface worth wrapping |
| cryptography, PyJWT, bcrypt, passlib | **GENERIC, and not revisited** | Security libraries deliberately keep error detail opaque; adding a whytrail layer here works against their own threat model, not with it |
| BeautifulSoup4, lxml | GENERIC | No structured error surface |
| Scrapy | PLUGIN (candidate) | Has its own signal system, same shape as Celery |
| Selenium, Playwright | PLUGIN (candidate, low priority) | Playwright's own trace viewer already covers most of this; limited marginal value |
| protobuf | GENERIC | Low incremental value |
| grpcio | PLUGIN (candidate, low priority) | `RpcError.code()`/`.details()` structured, smaller audience |
| pip, setuptools, wheel, poetry, hatchling, build, twine | **N/A** | Dev-time tooling; no runtime application object model |
| six, packaging, typing-extensions, certifi, charset-normalizer, idna, urllib3 (as a transitive dep), anyio, sniffio, h11 | **N/A** | Low-level transitive dependencies; not something an application developer calls `why()` on directly |

## Consequences

Of roughly 100 libraries actually assessed: **9 already have a real
plugin**, **2 more (Pydantic, boto3) were added from this triage**,
roughly **20 are credible future candidates** ranked by the reasoning
above (httpx and psycopg2 are the strongest next two), and the
remainder are either already fully served by generic tracking or
structurally out of scope. That ratio — a genuine plugin need in
roughly a tenth to a fifth of what was surveyed — is the actual answer
to "does this scale to 150 libraries." It scales as an *audit*
methodology and a *generator* for the ones that clear the bar; it does
not, and should not, scale as "150 plugin packages."
