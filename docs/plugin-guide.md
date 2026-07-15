# Writing a whytrail plugin

A plugin teaches `why()` to explain a type it doesn't know about, or wires
whytrail into a library's own hook system where one exists. See
[`plugins/whytrail-requests`](../plugins/whytrail-requests/) for a complete,
tested reference implementation of the first shape, and
[`plugins/whytrail-celery`](../plugins/whytrail-celery/) for the second.

**Before writing one:** read
[`docs/adr/0003-ecosystem-scale-triage.md`](adr/0003-ecosystem-scale-triage.md)
first. Most libraries don't need a plugin at all -- `track()`/`@tracked`
already works on arbitrary objects via `weakref` and `id()`-based
identity, no library-specific code required (this is exactly what
`whytrail-pandas` found: its plugin only earns its keep for the
*untracked*-diagnostic case). A plugin is warranted when a library clears
one of three bars: it carries structured error data a bare traceback
throws away, it has a security-sensitive boundary needing safe defaults,
or it needs a non-standard capture mechanism (signals, callbacks, hooks).
If you can't point to which bar your idea clears, it probably shouldn't
be a plugin.

`python scripts/new_plugin.py <library> --kind explainer|integration`
scaffolds the boilerplate (pyproject.toml, package stub, README, starter
test) for either shape -- it does not, and should not, generate the
actual explainer logic; that judgment call is the point.

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
smashed into `description` can't be redacted after the fact. See
`whytrail-sqlalchemy` (statement params) or `whytrail-pydantic` (bad field
values) for the pattern, and ADR 0002 §3 item 5 for why this matters.

## Registering

### From a package (the common case)

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

No package, no entry point needed:

```python
import whytrail
whytrail.register(MyType, explain_my_type)
```

A user's `whytrail.register()` call **always** wins over a plugin's
`register_from_plugin()` for the same type, regardless of which runs first --
if someone wants to override your plugin's explanation locally, they can,
without forking your package.

## Protocol version

The explainer contract above -- the `(obj) -> Explanation | str | None`
shape, `None`/exceptions meaning "fall through, not an error," the MRO
walk in `resolve_explainer()`, and `register()` always beating
`register_from_plugin()` for the same type -- is frozen as
`whytrail.registry.EXPLAINER_PROTOCOL_VERSION = 1`, tracked independently
of whytrail's own package version (ADR 0002 §3 item 6). This matters
because whytrail's release number moves for reasons that have nothing to
do with plugins (a new built-in explainer, a CLI flag, a bug fix in
`Explanation.graph()`); coupling plugin compatibility to that number
would force every plugin author to guess which whytrail releases are
safe to depend on. They don't have to guess: protocol version 1 is a
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
point in it, not teaching `why()` about a new type. There's no entry
point for this shape; the user wires it in explicitly, the same way they
already configure the library's other hooks:

```python
# whytrail_mylib/__init__.py
import whytrail

def install(*, log_locals: bool = False) -> None:
    @mylib.signals.something_failed.connect
    def _on_failure(sender, error, **kwargs):
        explanation = whytrail.why(error)
        logging.getLogger("whytrail.mylib").error(
            (explanation if log_locals else explanation.redacted()).text
        )
```

`whytrail-celery` (signals), `whytrail-pytest` (pytest hooks), and
`whytrail-fastapi`/`whytrail-django` (exception middleware, with a
safe-by-default redaction posture) are the reference implementations.

## Naming your distribution

Convention: `whytrail-<library>`. Depend on `whytrail` and the library you're
explaining; never the other way around.

## Testing your plugin

Write tests against the real installed distribution, not a mock of the
registry or the hook. Every plugin in `tests/plugin_contract/` follows
this pattern: install the plugin editable, then exercise real instances
of the type/hook you're explaining (a real `sqlalchemy.exc.IntegrityError`
from an in-memory SQLite database, a real `ClientError` via botocore's
`Stubber`, a real LangChain chain invocation) and assert on the result.
If your plugin touches anything that could be sensitive, test the
redaction default explicitly, not just the happy path -- see
`tests/plugin_contract/test_fastapi_plugin.py` for the thoroughness bar
a security-relevant integration needs to clear.

## The plugins that exist today

30 plugins. Each earns its place by clearing one of the three bars in
ADR 0003, verified against real objects, not assumed from documentation
-- several of these (marked *) were corrected after their own tests
caught the library's own message text leaking a value that was supposed
to be redacted.

| Plugin | Shape | What it adds |
|---|---|---|
| [`whytrail-requests`](../plugins/whytrail-requests/) | explainer | `Response`/`RequestException` detail (method, URL, status, body) |
| [`whytrail-httpx`](../plugins/whytrail-httpx/) | explainer | Same, for `httpx.HTTPStatusError`/`RequestError` |
| [`whytrail-aiohttp`](../plugins/whytrail-aiohttp/) | explainer | Same, for `aiohttp.ClientResponseError`/`ClientConnectionError` |
| [`whytrail-huggingface-hub`](../plugins/whytrail-huggingface-hub/) | explainer | `HfHubHTTPError` -- not covered by whytrail-httpx (different base class) |
| [`whytrail-openai`](../plugins/whytrail-openai/) | explainer | `APIStatusError`/`APIConnectionError`, redacted response body |
| [`whytrail-anthropic`](../plugins/whytrail-anthropic/) | explainer | Same, for the anthropic SDK |
| [`whytrail-boto3`](../plugins/whytrail-boto3/) | explainer | `ClientError` structured AWS error response |
| [`whytrail-google-cloud`](../plugins/whytrail-google-cloud/) | explainer | `GoogleAPICallError` -- one registration covers storage/bigquery/pubsub/etc. |
| [`whytrail-sqlalchemy`](../plugins/whytrail-sqlalchemy/) | explainer | `StatementError` statement + redacted params |
| [`whytrail-asyncpg`](../plugins/whytrail-asyncpg/)* | explainer | `PostgresError` sqlstate/constraint + redacted detail |
| [`whytrail-pymongo`](../plugins/whytrail-pymongo/)* | explainer | `PyMongoError` code; message/details fully redacted (no safe driver string exists) |
| [`whytrail-grpcio`](../plugins/whytrail-grpcio/) | explainer | `RpcError` status code + redacted `.details()` |
| [`whytrail-pydantic`](../plugins/whytrail-pydantic/) | explainer | Per-field `ValidationError` breakdown, redacted bad values |
| [`whytrail-marshmallow`](../plugins/whytrail-marshmallow/) | explainer | Per-field `ValidationError` breakdown (nested schemas too) |
| [`whytrail-jsonschema`](../plugins/whytrail-jsonschema/)* | explainer | Path/validator; `.message`/`.instance` fully redacted |
| [`whytrail-pyyaml`](../plugins/whytrail-pyyaml/)* | explainer | Location; `.problem`/snippet fully redacted |
| [`whytrail-pandas`](../plugins/whytrail-pandas/) | explainer | Diagnostic for untracked DataFrame/Series; steps aside once tracked |
| [`whytrail-polars`](../plugins/whytrail-polars/) | explainer | Same, for polars |
| [`whytrail-sentry`](../plugins/whytrail-sentry/) | integration | Attaches explanations to Sentry events via `before_send` |
| [`whytrail.otel`](../src/whytrail/otel.py) (core module, not a separate package) | integration | Attaches explanations to the current OpenTelemetry span |
| [`whytrail-ddtrace`](../plugins/whytrail-ddtrace/) | integration | Same, for Datadog spans |
| [`whytrail-celery`](../plugins/whytrail-celery/) | integration | Logs explanations (+ redacted task args) on `task_failure` |
| [`whytrail-rq`](../plugins/whytrail-rq/) | integration | Same, via RQ's exception-handler chain |
| [`whytrail-dramatiq`](../plugins/whytrail-dramatiq/) | integration | Same, via dramatiq middleware |
| [`whytrail-prefect`](../plugins/whytrail-prefect/) | integration | Same, via Prefect's `on_failure` hook (no arg capture -- see its README) |
| [`whytrail-scrapy`](../plugins/whytrail-scrapy/)† | integration | Logs explanations on `spider_error`, with the URL being parsed |
| [`whytrail-pytest`](../plugins/whytrail-pytest/) | integration | Explanation section on failing test reports |
| [`whytrail-fastapi`](../plugins/whytrail-fastapi/) | integration | Safe-by-default exception handler for FastAPI/Starlette |
| [`whytrail-django`](../plugins/whytrail-django/) | integration | Safe-by-default exception middleware for Django |
| [`whytrail-flask`](../plugins/whytrail-flask/) | integration | Same, for Flask |
| [`whytrail-langchain`](../plugins/whytrail-langchain/) | integration | Chain/LLM/tool/retriever provenance via LangChain callbacks |

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
identical to `whytrail-langchain`'s already-proven callback pattern --
building it would mostly duplicate work, not test anything new). See
`docs/adr/0003-ecosystem-scale-triage.md` for the full reasoning and the
much larger list of libraries that don't need a plugin at all.

**On test coverage:** every plugin above is verified against a real
object from the real library, including its redaction behavior where
that applies -- not a mock, and several bugs (noted with * and †) were
only caught because of that. That is a real, meaningful bar, and it is
not the same claim as "battle-tested in every condition." None of these
are tested across a version matrix, under concurrent load, against the
library's full exception surface, or on Linux (everything here ran on
Windows). See the coverage note in `CHANGELOG.md` for what closing that
gap would actually require.
