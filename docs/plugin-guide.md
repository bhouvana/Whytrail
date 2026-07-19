# Writing a whytrail plugin

A plugin teaches `why()` to explain a type it doesn't know about, or wires
whytrail into a library's own hook system where one exists. There are two
ways to build one, and they matter for a different reason each (ADR 0006):

- **Bundled** -- add a module to `src/whytrail/integrations/` in this
  repo, and an extra in `pyproject.toml`. This is how all 30 integrations
  below ship: one PyPI package (`whytrail`), `pip install whytrail[X]`
  pulls in the extra dependency, and (for explainer-shaped ones)
  `why()` picks it up automatically with zero further setup. Requires a
  PR against this repo.
- **External** -- your own, separately published `whytrail-mylib`
  package, discovered via the `whytrail.explainers` entry point,
  reviewed by nobody but you. This is how the bundled 30 used to work,
  before ADR 0006 folded them into the core package for a simpler
  release process -- the mechanism itself wasn't removed, and it's still
  the right answer for an integration you want to own and release on
  your own schedule.

See [`src/whytrail/integrations/requests.py`](../src/whytrail/integrations/requests.py)
for a complete, tested reference implementation of the explainer shape,
and [`src/whytrail/integrations/celery.py`](../src/whytrail/integrations/celery.py)
for the hook-based shape. Both read the same either way; only where the
code lives and how it's registered differs.

**Before writing one:** read
[`docs/adr/0003-ecosystem-scale-triage.md`](adr/0003-ecosystem-scale-triage.md)
first. Most libraries don't need a plugin at all -- `track()`/`@tracked`
already works on arbitrary objects via `weakref` and `id()`-based
identity, no library-specific code required (this is exactly what the
`pandas` integration found: it only earns its keep for the
*untracked*-diagnostic case). A plugin is warranted when a library clears
one of three bars: it carries structured error data a bare traceback
throws away, it has a security-sensitive boundary needing safe defaults,
or it needs a non-standard capture mechanism (signals, callbacks, hooks).
If you can't point to which bar your idea clears, it probably shouldn't
be a plugin.

`python scripts/new_plugin.py <library> --kind explainer|integration`
scaffolds the boilerplate for an **external** plugin (pyproject.toml,
package stub, README, starter test) -- it does not, and should not,
generate the actual explainer logic; that judgment call is the point. For
a **bundled** integration, there's no scaffold script: copy the shape of
an existing module under `src/whytrail/integrations/` closest to what
you're building.

## The shape of an explainer (registry-based plugins)

An explainer is a function `(obj) -> Explanation | str | None`:

```python
from whytrail import Explanation, ExplanationStep, Confidence

def explain_my_type(obj: MyType) -> Explanation:
    return Explanation(
        subject=f"{obj!r}",
        steps=[
            ExplanationStep(
                description=f"created from {obj.source}",
                confidence=Confidence.EXPLICIT.value,
            ),
        ],
        tracked=True,
    )
```

Returning a plain `str` also works -- it gets wrapped in a single-step
`Explanation` automatically. Returning `None` means "I don't actually know
how to explain this one," and resolution falls through to the next
strategy rather than treating it as an answer.

**Never let your explainer raise.** whytrail catches exceptions from
explainers defensively, but a broken explainer still means the caller
gets "unknown" instead of your plugin's actual explanation -- test it.

**If any detail you're attaching could be sensitive** -- a SQL parameter,
a validation input, a task payload, anything that isn't safely public --
put it on `ExplanationStep.locals` (a `dict[str, str]`), not in
`description`. That's the one thing `Explanation.redacted()` strips
before an integration exports off-box (Sentry, OTel, a CI comment); text
smashed into `description` can't be redacted after the fact. See the
`sqlalchemy` integration (statement params) or `pydantic` (bad field
values) for the pattern, and ADR 0002 §3 item 5 for why this matters.

## Registering

### Bundled (adding to this repo)

Add `src/whytrail/integrations/mylib.py`:

```python
# src/whytrail/integrations/mylib.py
from ..registry import register_from_plugin

def register() -> None:
    register_from_plugin(MyType, explain_my_type)
```

Add `mylib` to `registry._BUILTIN_EXPLAINERS` in
[`src/whytrail/registry.py`](../src/whytrail/registry.py) -- that's the
whole activation step. `resolve_explainer()` tries to import each name in
that tuple lazily, once, the first time it needs to resolve an explainer
it doesn't already have; a missing dependency just means `ImportError`,
caught the same way a broken entry-point plugin's failure already is.
Add a `mylib = ["mylib>=X.Y"]` extra to `pyproject.toml` so
`pip install whytrail[mylib]` actually installs the library being
explained.

**Before opening the PR, update every place that states the aggregate
count**, not just the code: this table below, README.md's ecosystem
count and extras grid, and `docs/testing-maturity.md`'s opening
paragraph and version-matrix coverage claims. Skipping this is exactly
how the count drifted a full batch behind reality before it was caught
retroactively while cutting 0.2.1 -- see `CHANGELOG.md`.

### External (your own separate package)

Add an entry point in your plugin's `pyproject.toml`:

```toml
[project.entry-points."whytrail.explainers"]
mylib = "whytrail_mylib:register"
```

And a zero-argument `register()` function that your entry point points
to:

```python
# whytrail_mylib/__init__.py
from whytrail.registry import register_from_plugin

def register() -> None:
    register_from_plugin(MyType, explain_my_type)
```

whytrail discovers and calls `register()` lazily, once, the first time it
needs to resolve an explainer it doesn't already have -- your package is
never imported at whytrail's import time, and whytrail is never a required
dependency your users have to think about beyond `pip install`.

### From a notebook or script

No package, no entry point needed, whether you're extending a bundled or
external integration:

```python
import whytrail
whytrail.register(MyType, explain_my_type)
```

A user's `whytrail.register()` call **always** wins over a plugin's
`register_from_plugin()` for the same type, regardless of which runs first --
if someone wants to override a bundled or third-party explanation locally,
they can, without forking anything.

## Protocol version

The explainer contract above -- the `(obj) -> Explanation | str | None`
shape, `None`/exceptions meaning "fall through, not an error," the MRO
walk in `resolve_explainer()`, and `register()` always beating
`register_from_plugin()` for the same type -- is frozen as
`whytrail.registry.EXPLAINER_PROTOCOL_VERSION = 1`, tracked independently
of whytrail's own package version (ADR 0002 §3 item 6). This matters for
**external** plugins specifically: whytrail's release number moves for
reasons that have nothing to do with the protocol (a new bundled
integration, a CLI flag, a bug fix in `Explanation.graph()`), and an
external plugin author shouldn't have to guess which whytrail releases
are safe to depend on. They don't have to guess: protocol version 1 is a
promise, not a moving target, and stays valid across whytrail's 0.x/1.x/
2.x releases until something below actually needs to change.

Covered by v1, and won't change without a v2:

- The `Explainer` callable's signature and return contract.
- `register(type_, explainer)` semantics (manual, always wins).
- `register_from_plugin(type_, explainer)` semantics (entry-point-driven,
  `setdefault`, never overrides a manual registration).
- The `whytrail.explainers` entry-point group name and its
  zero-argument-`register()`-function calling convention.
- MRO-based resolution order (own class first, then base classes).

Not covered -- these can change in a whytrail minor/major release without
a protocol version bump, because no plugin should depend on them:
`Explanation`'s exact dataclass fields beyond what `docs/plugin-guide.md`
already asks you to set, the internal shape of `ProvenanceGraph`, and
anything under `whytrail.core`/`whytrail.runtime` not re-exported here.

If protocol v1 ever needs a breaking change, it becomes v2 with both
resolvable simultaneously for a deprecation window -- the same
non-negotiable a packaged plugin ecosystem needs from any host library,
made explicit here instead of left implicit and then broken by accident.

## The other shape: hook-based integrations

Some libraries don't have a type worth registering an explainer for --
they have their own lifecycle (a signal, a callback system, a middleware
protocol), and the useful thing is calling `whytrail.why()` at the right
point in it, not teaching `why()` about a new type. There's no
auto-registration for this shape, bundled or external: the user imports
the module and wires it in explicitly, the same way they already
configure the library's other hooks:

```python
# src/whytrail/integrations/mylib.py (bundled) or whytrail_mylib/__init__.py (external)
import whytrail

def install(*, log_locals: bool = False) -> None:
    @mylib.signals.something_failed.connect
    def _on_failure(sender, error, **kwargs):
        explanation = whytrail.why(error)
        logging.getLogger("whytrail.mylib").error(
            (explanation if log_locals else explanation.redacted()).text
        )
```

The `celery` integration (signals), `pytest` (pytest hooks, via the
`pytest11` entry-point group -- see its own module docstring for why that
one's registration is unconditional, unlike every other bundled
integration), and `fastapi`/`django` (exception middleware, with a
safe-by-default redaction posture) are the reference implementations.

## Naming

**Bundled**: the extra name matches the module name under
`src/whytrail/integrations/` (hyphenated in `pyproject.toml` for
multi-word ones, e.g. `google-cloud` -> `google_cloud.py`).

**External**: convention is `whytrail-<library>`. Depend on `whytrail`
and the library you're explaining; never the other way around.

## Testing your plugin

Write tests against the real installed integration, not a mock of the
registry or the hook. Every integration in `tests/plugin_contract/`
follows this pattern: install the extra (`pip install -e ".[mylib]"` for
a bundled one), then exercise real instances of the type/hook you're
explaining (a real `sqlalchemy.exc.IntegrityError` from an in-memory
SQLite database, a real `ClientError` via botocore's `Stubber`, a real
LangChain chain invocation) and assert on the result. If your plugin
touches anything that could be sensitive, test the redaction default
explicitly, not just the happy path -- see
`tests/plugin_contract/test_fastapi_plugin.py` for the thoroughness bar
a security-relevant integration needs to clear.

## The integrations that exist today

100, all bundled (ADR 0006) -- 63 reached the previous resting point (60
from the original ecosystem push, plus logging/structlog/loguru), and a
0.3.1 push added 37 more spanning vector databases, newer LLM SDKs,
SaaS/commerce APIs, orchestration/messaging, and identity/observability
tooling (see `CHANGELOG.md` for batch-by-batch
progress and ADR 0003 for the underlying triage methodology). Each earns
its place by clearing one of the
three bars in ADR 0003, verified against real objects, not assumed from
documentation -- several of these (marked *) were corrected after their
own tests caught the library's own message text leaking a value that was
supposed to be redacted. Not every popular library clears the bar: see
"Checked and not built" below for candidates found, on inspection, to
carry no structured data beyond what tier 1 already shows for free.

| Extra | Shape | What it adds |
|---|---|---|
| [`requests`](../src/whytrail/integrations/requests.py) | explainer | `Response`/`RequestException` detail (method, URL, status, body) |
| [`httpx`](../src/whytrail/integrations/httpx.py) | explainer | Same, for `httpx.HTTPStatusError`/`RequestError` |
| [`aiohttp`](../src/whytrail/integrations/aiohttp.py) | explainer | Same, for `aiohttp.ClientResponseError`/`ClientConnectionError` |
| [`huggingface-hub`](../src/whytrail/integrations/huggingface_hub.py) | explainer | `HfHubHTTPError` -- not covered by `httpx` (different base class) |
| [`openai`](../src/whytrail/integrations/openai.py) | explainer | `APIStatusError`/`APIConnectionError`, redacted response body |
| [`anthropic`](../src/whytrail/integrations/anthropic.py) | explainer | Same, for the anthropic SDK |
| [`boto3`](../src/whytrail/integrations/boto3.py) | explainer | `ClientError` structured AWS error response |
| [`google-cloud`](../src/whytrail/integrations/google_cloud.py) | explainer | `GoogleAPICallError` -- one registration covers storage/bigquery/pubsub/etc. |
| [`sqlalchemy`](../src/whytrail/integrations/sqlalchemy.py) | explainer | `StatementError` statement + redacted params |
| [`asyncpg`](../src/whytrail/integrations/asyncpg.py)* | explainer | `PostgresError` sqlstate/constraint + redacted detail |
| [`pymongo`](../src/whytrail/integrations/pymongo.py)* | explainer | `PyMongoError` code; message/details fully redacted (no safe driver string exists) |
| [`grpcio`](../src/whytrail/integrations/grpcio.py) | explainer | `RpcError` status code + redacted `.details()` |
| [`pydantic`](../src/whytrail/integrations/pydantic.py) | explainer | Per-field `ValidationError` breakdown, redacted bad values |
| [`marshmallow`](../src/whytrail/integrations/marshmallow.py) | explainer | Per-field `ValidationError` breakdown (nested schemas too) |
| [`jsonschema`](../src/whytrail/integrations/jsonschema.py)* | explainer | Path/validator; `.message`/`.instance` fully redacted |
| [`pyyaml`](../src/whytrail/integrations/pyyaml.py)* | explainer | Location; `.problem`/snippet fully redacted |
| [`pandas`](../src/whytrail/integrations/pandas.py) | explainer | Diagnostic for untracked DataFrame/Series; steps aside once tracked |
| [`polars`](../src/whytrail/integrations/polars.py) | explainer | Same, for polars |
| [`stripe`](../src/whytrail/integrations/stripe.py) | explainer | `StripeError` code/param/http_status, redacted response body |
| [`alembic`](../src/whytrail/integrations/alembic.py) | explainer | `ResolutionError`/`MultipleHeads` -- the actual bad revision id / ambiguous heads |
| [`paramiko`](../src/whytrail/integrations/paramiko.py) | explainer | `BadHostKeyException` as key fingerprints, never raw key material |
| [`elasticsearch`](../src/whytrail/integrations/elasticsearch.py) | explainer | `ApiError` HTTP status + redacted response body (`.body`'s `reason` can echo a raw query) |
| [`pika`](../src/whytrail/integrations/pika.py) | explainer | `ChannelClosed`/`ConnectionClosed` AMQP `reply_code` + redacted `reply_text` |
| [`kubernetes`](../src/whytrail/integrations/kubernetes.py) | explainer | `ApiException` HTTP status/reason + redacted response body |
| [`azure-core`](../src/whytrail/integrations/azure_core.py) | explainer | `HttpResponseError` status/error code + redacted message (shared base of every Azure SDK client) |
| [`sendgrid`](../src/whytrail/integrations/sendgrid.py) | explainer | `HTTPError` (python_http_client) status/reason + redacted response body |
| [`websockets`](../src/whytrail/integrations/websockets.py) | explainer | `ConnectionClosed` close code + redacted close reason |
| [`opensearch`](../src/whytrail/integrations/opensearch.py) | explainer | `TransportError` status/error + redacted response info (elasticsearch-py fork, same shape) |
| [`pyodbc`](../src/whytrail/integrations/pyodbc.py) | explainer | `Error` SQLSTATE code + redacted driver message |
| [`google-genai`](../src/whytrail/integrations/google_genai.py) | explainer | `APIError` code/status + redacted response message (not the deprecated `google-generativeai`) |
| [`oracledb`](../src/whytrail/integrations/oracledb.py) | explainer | `Error`'s `full_code`/`offset` + redacted driver message |
| [`confluent-kafka`](../src/whytrail/integrations/confluent_kafka.py) | explainer | `KafkaException`'s error name/fatal/retriable + redacted broker message |
| [`pymysql`](../src/whytrail/integrations/pymysql.py) | explainer | `Error` errno + redacted driver message |
| [`pymssql`](../src/whytrail/integrations/pymssql.py) | explainer | `Error` code + redacted driver message |
| [`clickhouse`](../src/whytrail/integrations/clickhouse.py) | explainer | `ClickHouseError` code/name + redacted driver message |
| [`snowflake`](../src/whytrail/integrations/snowflake.py) | explainer | `Error` errno/sqlstate/sfqid + redacted message/query |
| [`graphql-core`](../src/whytrail/integrations/graphql_core.py) | explainer | `GraphQLError` resolver path + redacted message (covers strawberry-graphql, Ariadne, graphene) |
| [`tenacity`](../src/whytrail/integrations/tenacity.py) | explainer | Unwraps `RetryError` to the real underlying exception via recursive `why()`, not a field extraction |
| [`psycopg`](../src/whytrail/integrations/psycopg.py) | explainer | `Error.sqlstate` (settable, unlike psycopg2's blocked `.pgcode`) + redacted message |
| [`cassandra`](../src/whytrail/integrations/cassandra.py) | explainer | `RequestExecutionException` (Unavailable/WriteTimeout/ReadTimeout) consistency-level detail, no redaction needed |
| [`influxdb`](../src/whytrail/integrations/influxdb.py) | explainer | `ApiException` status/reason + redacted response body |
| [`pyzmq`](../src/whytrail/integrations/pyzmq.py) | explainer | `ZMQError` errno that bare `str(exc)` drops entirely, no redaction needed |
| [`zeep`](../src/whytrail/integrations/zeep.py) | explainer | SOAP `Fault` code + redacted message/detail |
| [`sentry`](../src/whytrail/integrations/sentry.py) | integration | Attaches explanations to Sentry events via `before_send` |
| [`otel`](../src/whytrail/otel.py) (core module, always bundled) | integration | Attaches explanations to the current OpenTelemetry span |
| [`ddtrace`](../src/whytrail/integrations/ddtrace.py) | integration | Same, for Datadog spans |
| [`celery`](../src/whytrail/integrations/celery.py) | integration | Logs explanations (+ redacted task args) on `task_failure` |
| [`rq`](../src/whytrail/integrations/rq.py) | integration | Same, via RQ's exception-handler chain |
| [`dramatiq`](../src/whytrail/integrations/dramatiq.py) | integration | Same, via dramatiq middleware |
| [`prefect`](../src/whytrail/integrations/prefect.py) | integration | Same, via Prefect's `on_failure` hook (no arg capture -- see module docstring) |
| [`scrapy`](../src/whytrail/integrations/scrapy.py)† | integration | Logs explanations on `spider_error`, with the URL being parsed |
| [`pytest`](../src/whytrail/integrations/pytest_plugin.py) | integration | Explanation section on failing test reports |
| [`fastapi`](../src/whytrail/integrations/fastapi.py) | integration | Safe-by-default exception handler for FastAPI/Starlette |
| [`django`](../src/whytrail/integrations/django.py) | integration | Safe-by-default exception middleware for Django |
| [`flask`](../src/whytrail/integrations/flask.py) | integration | Same, for Flask |
| [`langchain`](../src/whytrail/integrations/langchain.py) | integration | Chain/LLM/tool/retriever provenance via LangChain callbacks |
| [`newrelic`](../src/whytrail/integrations/newrelic.py) | integration | Attaches explanations to New Relic error events via `notice_error()` |
| [`rollbar`](../src/whytrail/integrations/rollbar.py) | integration | Attaches explanations to Rollbar reports via `report_exc_info()` |
| [`honeybadger`](../src/whytrail/integrations/honeybadger.py) | integration | Attaches explanations to Honeybadger notifications via `notify()` |
| [`elastic-apm`](../src/whytrail/integrations/elastic_apm.py) | integration | Attaches explanations to Elastic APM error events via `capture_exception()` |
| [`bugsnag`](../src/whytrail/integrations/bugsnag.py) | integration | Attaches explanations to Bugsnag reports via `notify()` |
| [`logging`](../src/whytrail/integrations/logging.py) (core module, no extra needed) | integration | A `logging.Filter` appending explanations to any record with `exc_info` |
| [`structlog`](../src/whytrail/integrations/structlog.py) | integration | A processor adding a structured `why` key to the event dict |
| [`loguru`](../src/whytrail/integrations/loguru.py) | integration | `logger.patch()`-based, appends explanations to messages carrying exception info |
| [`pinecone`](../src/whytrail/integrations/pinecone.py) | explainer | `PineconeApiException` status/error_code/request_id, redacted body |
| [`weaviate-client`](../src/whytrail/integrations/weaviate_client.py) | explainer | `UnexpectedStatusCodeError`/`WeaviateQueryError` status, redacted response detail |
| [`qdrant-client`](../src/whytrail/integrations/qdrant_client.py) | explainer | `UnexpectedResponse` status/reason, redacted structured content |
| [`neo4j`](../src/whytrail/integrations/neo4j.py) | explainer | `Neo4jError`'s server-assigned code/classification/category/title, redacted message |
| [`cohere`](../src/whytrail/integrations/cohere.py) | explainer | `ApiError` status code, redacted response body (same shape as `openai`/`anthropic`) |
| [`mistralai`](../src/whytrail/integrations/mistralai.py) | explainer | `MistralError` status code, redacted response body |
| [`twilio`](../src/whytrail/integrations/twilio.py) | explainer | `TwilioRestException` status/Twilio error code, redacted msg/details |
| [`slack-sdk`](../src/whytrail/integrations/slack_sdk.py) | explainer | `SlackApiError`'s response status/error code, redacted response data |
| [`plaid`](../src/whytrail/integrations/plaid.py) | explainer | `ApiException` status/reason, redacted body |
| [`docker`](../src/whytrail/integrations/docker.py) | explainer | `APIError` status code, redacted daemon `.explanation` |
| [`hvac`](../src/whytrail/integrations/hvac.py) | explainer | `VaultError` (+ per-status subclasses) -- fully redacted, `.url` is a Vault secret path |
| [`square`](../src/whytrail/integrations/square.py) | explainer | `ApiError` status + per-error category/code taxonomy, redacted `.detail` |
| [`temporalio`](../src/whytrail/integrations/temporalio.py) | explainer | `ApplicationError`'s retry semantics (non_retryable/next_retry_delay/category), redacted details |
| [`dagster`](../src/whytrail/integrations/dagster.py) | explainer | Unwraps `DagsterUserCodeExecutionError` to the real underlying exception via recursive `why()` |
| [`discord-py`](../src/whytrail/integrations/discord.py) | explainer | `HTTPException` status/Discord error code, redacted `.text` |
| [`nats-py`](../src/whytrail/integrations/nats.py) | explainer | JetStream `APIError` code/err_code/stream/seq, redacted description |
| [`aiohttp-server`](../src/whytrail/integrations/aiohttp_server.py) | integration | Safe-by-default exception middleware for `aiohttp.web`, distinct from the client-side `aiohttp` explainer |
| [`firebase-admin`](../src/whytrail/integrations/firebase_admin.py) | explainer | `FirebaseError`'s canonical error code, redacted message + wrapped `.cause` |
| [`minio`](../src/whytrail/integrations/minio.py) | explainer | `S3Error`'s fully-parsed XML error response, redacted bucket/object identity |
| [`arango`](../src/whytrail/integrations/arango.py) | explainer | `ArangoServerError`'s HTTP + ArangoDB error codes, redacted message/URL |
| [`supabase`](../src/whytrail/integrations/supabase.py) | explainer | `postgrest.exceptions.APIError` (the real exception supabase-py raises) status/code, redacted detail |
| [`auth0`](../src/whytrail/integrations/auth0.py) | explainer | Authentication + Management API error hierarchies, status/error codes, redacted bodies |
| [`pagerduty`](../src/whytrail/integrations/pagerduty.py) | explainer | `HttpError` status, redacted message -- supersedes the deprecated `pdpyras` |
| [`algoliasearch`](../src/whytrail/integrations/algoliasearch.py) | explainer | `RequestException` status code, redacted message |
| [`mlflow`](../src/whytrail/integrations/mlflow.py) | explainer | `MlflowException`'s documented error-code taxonomy + HTTP status, redacted message |
| [`meilisearch`](../src/whytrail/integrations/meilisearch.py) | explainer | `MeilisearchApiError` status/code/type/link, redacted message |
| [`github`](../src/whytrail/integrations/github.py) | explainer | PyGithub `GithubException` status, redacted response data |
| [`okta`](../src/whytrail/integrations/okta.py) | explainer | `ApiException` status/reason, redacted response detail |
| [`chromadb`](../src/whytrail/integrations/chromadb.py) | explainer | `ChromaError`'s per-subclass code/name taxonomy, redacted message |
| [`wandb`](../src/whytrail/integrations/wandb.py) | explainer | `Error`'s context dict; `CommError` unwraps to the real underlying exception via recursive `why()` |
| [`datadog-api-client`](../src/whytrail/integrations/datadog_api_client.py) | explainer | Datadog's own REST management API `ApiException`, distinct from the `ddtrace` APM tracer |
| [`postmarker`](../src/whytrail/integrations/postmarker.py) | explainer | `ClientError`'s documented numeric error code |
| [`simple-salesforce`](../src/whytrail/integrations/simple_salesforce.py) | explainer | Unified `SalesforceError` base -- status/resource/URL, redacted content |
| [`zenpy`](../src/whytrail/integrations/zenpy.py) | explainer | Zendesk `APIException`'s real wrapped `requests.Response`, redacted body |
| [`notion-client`](../src/whytrail/integrations/notion_client.py) | explainer | `HTTPResponseError` code/status/request_id, redacted body/additional_data |
| [`dropbox`](../src/whytrail/integrations/dropbox.py) | explainer | `ApiError`'s request_id + Stone-generated route-specific error union, redacted |
| [`asana`](../src/whytrail/integrations/asana.py) | explainer | Same generated-OpenAPI-client shape as `pinecone`/`plaid`/`okta`, redacted body |

† required `weak=False` on the signal connection -- the default weak
reference let the handler closure get garbage-collected immediately
after `install()` returned, so the signal silently reached zero
receivers. Found by checking `send_catch_log`'s return value in this
plugin's own tests, not by reading pydispatch's docs.

**Not built, with reasons, not silence:** `psycopg2` (needs a real
PostgreSQL server -- its `.pgcode`/`.pgerror` are C-level read-only
attributes that can't be populated outside a real connection, unlike
`asyncpg`'s equivalent fields); `redis-py` (checked directly: its
exceptions carry no structured data beyond the message string, so
there's nothing to add over tier 1); `Playwright`/`Selenium` (need
browser binaries this environment doesn't have); `Airflow` (heavy
transitive dependency footprint, deferred); `LlamaIndex` (architecturally
identical to the `langchain` integration's already-proven callback
pattern -- building it would mostly duplicate work, not test anything
new); **`PyJWT` and `cryptography`** (checked directly, same reasoning as
`redis-py`: their exceptions carry no structured fields beyond the
message -- real value captured instead as gloss/fix-table entries for
`.plain_text`, not a full plugin that would add code without adding
information); **`kafka-python`** (checked directly against a live Kafka
container: `errno`/`message`/`description` on its error classes are
class-level constants from a static protocol-error-code table, not
populated per-instance, and there's no topic/partition/offset attribute
on the exception itself -- same "nothing to add over tier 1" verdict as
`redis-py`). See `docs/adr/0003-ecosystem-scale-triage.md` for the full
reasoning and the much larger list of libraries that don't need a plugin
at all.

**Also not built, from the 0.3.1 push (63->100):** `ray` (no installable
wheel for the environment this ecosystem was built in, an environment
gap rather than a triage verdict); `transformers` (checked directly:
its only real error types are the same class objects as
`huggingface_hub`'s, confirmed via `is` identity -- already covered by
that extra); `python-telegram-bot`, `typesense`, `duckdb`, `cloudinary`,
`mixpanel` (all checked directly and found GENERIC -- no structured
fields beyond a plain message string, same verdict as `redis-py`);
`launchdarkly-server-sdk` (N/A -- the SDK deliberately never raises at
all; flag evaluation degrades to a default value by design);
`pyairtable` (GENERIC -- its HTTP errors are plain
`requests.exceptions.HTTPError`, already covered by `whytrail[requests]`);
`hubspot-api-client` (structural, not a data problem: each CRM object
type generates its own unrelated `ApiException` class with no shared
base, so there's no single registration point that actually covers the
SDK -- would need ~15 near-duplicate registrations to approximate one
plugin).

**On test coverage:** every integration above is verified against a real
object from the real library, including its redaction behavior where
that applies -- not a mock, and several bugs (noted with * and †) were
only caught because of that. Every one's stated minimum dependency
version is also confirmed to actually install and pass its tests, on
real `ubuntu-latest` CI, not assumed from a version number or a
Windows-only local check -- that process alone found 20 real
version-compatibility bugs across two rounds (see
`docs/testing-maturity.md` for the full breakdown, and
`.github/workflows/ci.yml`'s `plugin-version-matrix` job for exactly
which floor was corrected and why). That's a meaningfully higher bar
than "the code looks correct," and it's still not the same claim as
"battle-tested in every condition" -- `docs/testing-maturity.md` lists
what's still open: the Python 3.10-3.12 range (only 3.13 has run this
matrix so far), concurrency beyond the three web frameworks, and full
exception-surface breadth per integration.
