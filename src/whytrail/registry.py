"""Plugin registry: manual registration and entry-point discovery
(ADR §06).

Two mechanisms because they solve different problems: entry points let
a packaged plugin (whytrail-pandas et al.) register itself without
either side importing the other at module load time; manual
registration covers notebooks and scripts with no package to attach an
entry point to. A manual registration always wins over a plugin's,
regardless of which happens first -- see register() vs register_from_plugin().
"""

from __future__ import annotations

import dataclasses
import importlib
import sys
import typing as t

from ._repr import safe_repr
from .core.explanation import Explanation, ExplanationStep

if t.TYPE_CHECKING:
    import importlib.metadata

Explainer = t.Callable[[t.Any], t.Union[Explanation, str, None]]

ENTRY_POINT_GROUP = "whytrail.explainers"

# Frozen contract for third-party explainer plugins, independent of
# whytrail's own package version (ADR 0002 §3 item 6). A plugin built
# against protocol version 1 keeps working across whytrail 0.x/1.x/2.x
# releases as long as this number doesn't change; a future breaking
# change to the contract below bumps this constant, not whytrail's
# semver, so a plugin can assert compatibility (or CI can gate on it)
# without coupling to whytrail's release cadence. See
# docs/plugin-guide.md's "Protocol version" section for what's covered.
EXPLAINER_PROTOCOL_VERSION = 1

_registry: dict[type, Explainer] = {}
_manual_types: set[type] = set()
_entry_points_loaded = False
_builtins_loaded = False

# The 18 explainer-shaped integrations bundled into whytrail itself as
# optional extras (ADR 0006) rather than shipped as 18 separate PyPI
# packages -- one release process instead of many, with the underlying
# third-party dependency only pulled in when its extra is requested
# (`pip install whytrail[requests]`). Each name here is a real module
# under `whytrail.integrations`; importing it is how its underlying
# library gets checked for, not a separate lookup table that could
# drift from what's actually on disk -- an ImportError (library not
# installed) is indistinguishable here from "this integration doesn't
# exist," which is the same failure mode entry-point plugins already
# have. The 12 integration-shaped ones (hook/middleware/signal-based --
# whytrail-celery, whytrail-fastapi, etc.) don't need this list: nothing
# auto-registers for them, a user imports the specific
# `whytrail.integrations.<name>` module and wires it in explicitly, the
# same way they always have.
_BUILTIN_EXPLAINERS = (
    "requests",
    "httpx",
    "aiohttp",
    "huggingface_hub",
    "openai",
    "anthropic",
    "boto3",
    "google_cloud",
    "sqlalchemy",
    "asyncpg",
    "pymongo",
    "grpcio",
    "pydantic",
    "marshmallow",
    "jsonschema",
    "pyyaml",
    "numpy",
    "pandas",
    "polars",
    "stripe",
    "alembic",
    "paramiko",
    "elasticsearch",
    "pika",
    "kubernetes",
    "azure_core",
    "sendgrid",
    "websockets",
    "opensearch",
    "pyodbc",
    "google_genai",
    "oracledb",
    "confluent_kafka",
    "pymysql",
    "pymssql",
    "clickhouse",
    "snowflake",
    "graphql_core",
    "tenacity",
    "psycopg",
    "cassandra",
    "influxdb",
    "pyzmq",
    "zeep",
    # Batch: vector DBs / newer LLM SDKs (0.3.1, ecosystem push 63->100)
    "pinecone",
    "weaviate_client",
    "qdrant_client",
    "neo4j",
    "cohere",
    "mistralai",
    # Batch: SaaS / commerce APIs (0.3.1)
    "twilio",
    "slack_sdk",
    "plaid",
    "docker",
    "hvac",
    "square",
    # Batch: orchestration / messaging (0.3.1)
    "temporalio",
    "dagster",
    "discord",
    "nats",
    # Batch: infra / DB (0.3.1). `transformers` considered and rejected:
    # its only real error types (Repository/Revision/EntryNotFoundError)
    # are literally the same class objects as huggingface_hub's, already
    # registered by that extra -- confirmed via `is` identity, not
    # assumed. transformers exposes no exception types of its own.
    "firebase_admin",
    "minio",
    "arango",
    "supabase",
    # Batch: identity / observability / search / MLOps (0.3.1). `typesense`
    # and `duckdb` considered and rejected -- both checked directly and
    # found GENERIC (no structured fields beyond a plain message string
    # on any exception class), the same verdict as redis-py/PyJWT.
    # `pdpyras` (originally scoped) is deprecated as of 2025-06-20;
    # `pagerduty`, its official successor, is what's actually built here.
    "auth0",
    "pagerduty",
    "algoliasearch",
    "mlflow",
    "meilisearch",
    "github",
    "okta",
    "chromadb",
    "wandb",
    # Batch: final round closing the 63->100 gap (0.3.1). `cloudinary`,
    # `pyairtable`, `launchdarkly-server-sdk`, `mixpanel` considered and
    # rejected -- GENERIC or N/A (pyairtable's HTTP errors are plain
    # requests.exceptions.HTTPError, already covered by
    # whytrail[requests]; launchdarkly's SDK deliberately never raises
    # at all, by design -- flag evaluation degrades to a default value
    # instead). `hubspot-api-client` considered and rejected for a
    # different reason: each CRM object type (contacts, deals, tickets,
    # ...) generates its own unrelated ApiException class with no
    # shared base, so there's no single registration point that
    # actually covers the SDK -- would need ~15 near-duplicate
    # registrations to approximate one plugin, the concentrated version
    # of the "shallow integrations" antipattern ADR 0003 already
    # rejects at the ecosystem level.
    "datadog_api_client",
    "postmarker",
    "simple_salesforce",
    "zenpy",
    "notion_client",
    "dropbox",
    "asana",
    # Two more closing out the ecosystem table's last row (100->102).
    "groq",
    "replicate",
)

# The remaining 20 of the 63 total integrations: hook/middleware/signal
# -based (fastapi, django, celery, ...). These never auto-register --
# ADR 0006 -- so they're listed separately from _BUILTIN_EXPLAINERS
# above, purely for `whytrail plugins`' introspection below; nothing
# else in the registry reads this tuple.
_HOOK_BASED_INTEGRATIONS = (
    "bugsnag",
    "celery",
    "ddtrace",
    "django",
    "dramatiq",
    "elastic_apm",
    "fastapi",
    "flask",
    "honeybadger",
    "langchain",
    "logging",
    "loguru",
    "newrelic",
    "prefect",
    "pytest_plugin",
    "rollbar",
    "rq",
    "scrapy",
    "sentry",
    "structlog",
    "aiohttp_server",
)

# The real top-level import for the underlying third-party library each
# hook-based integration wraps. list_hook_based_plugins() checks this
# import directly instead of trusting "whytrail.integrations.<name>
# imports cleanly" the way _BUILTIN_EXPLAINERS' check does above --
# several of these modules (bugsnag, ddtrace, elastic_apm, flask,
# honeybadger, newrelic, rollbar, rq, scrapy, sentry) import their real
# dependency lazily inside a function body rather than at module top
# level, and prefect never imports it at all (pure duck typing over
# whatever object Prefect's hook signature passes). That means the
# wrapper module imports without error whether or not the real library
# is installed, so it can't be used as the availability signal. Found
# via a clean-venv smoke test: `whytrail plugins` reported these as
# "available" with zero of their third-party packages present.
_HOOK_BASED_UNDERLYING_IMPORT: dict[str, str] = {
    "bugsnag": "bugsnag",
    "celery": "celery",
    "ddtrace": "ddtrace",
    "django": "django",
    "dramatiq": "dramatiq",
    "elastic_apm": "elasticapm",
    "fastapi": "starlette",
    "flask": "flask",
    "honeybadger": "honeybadger",
    "langchain": "langchain_core",
    "logging": "logging",
    "loguru": "loguru",
    "newrelic": "newrelic",
    "prefect": "prefect",
    "pytest_plugin": "pytest",
    "rollbar": "rollbar",
    "rq": "rq",
    "scrapy": "scrapy",
    "sentry": "sentry_sdk",
    "structlog": "structlog",
    "aiohttp_server": "aiohttp",
}


@dataclasses.dataclass(frozen=True, slots=True)
class PluginStatus:
    """One row of `whytrail plugins`' output -- not part of the
    registry's own resolution logic, purely a read-only introspection
    view over it."""

    name: str
    # "explainer" (auto-registers on import) or "integration" (needs
    # explicit install()/wiring) -- matches docs/plugin-guide.md's own
    # "Shape" column vocabulary exactly (a first version of this used
    # "hook" instead, a third term for the same two-shape taxonomy
    # already established there and in pyproject.toml's own "Integration
    # -shaped" extras comment; found auditing for naming consistency
    # before 1.0, since this is a public JSON field via `whytrail
    # plugins --json` and would be expensive to rename once real
    # scripts depend on it).
    kind: str
    available: bool  # underlying third-party library is importable


def list_builtin_plugins() -> list[PluginStatus]:
    """Status of every explainer-shaped extra bundled in this package
    (auto-registers via why() the moment its extra is installed --
    see _load_builtin_explainers()). Calling this triggers that same
    lazy load if it hasn't happened yet, so `available` reflects
    reality rather than "not checked yet.\""""
    _load_builtin_explainers()
    return [
        PluginStatus(name=name, kind="explainer", available=f"whytrail.integrations.{name}" in sys.modules)
        for name in _BUILTIN_EXPLAINERS
    ]


def list_hook_based_plugins() -> list[PluginStatus]:
    """Status of every hook/middleware-based integration bundled in
    this package. These never auto-register (ADR 0006 -- they need an
    explicit install()/wiring call in user code), so `available` here
    means only "the underlying library is importable," not "currently
    wired into an app." Verified via _HOOK_BASED_UNDERLYING_IMPORT's
    real package name, not merely by importing whytrail's own wrapper
    module -- see that mapping's comment for why the wrapper import
    alone isn't a reliable signal.
    """
    statuses = []
    for name in _HOOK_BASED_INTEGRATIONS:
        try:
            importlib.import_module(f"whytrail.integrations.{name}")
            importlib.import_module(_HOOK_BASED_UNDERLYING_IMPORT[name])
            available = True
        except Exception:  # noqa: BLE001 - missing extra, either way just report unavailable
            available = False
        statuses.append(PluginStatus(name=name, kind="integration", available=available))
    return statuses


def list_entry_point_plugins() -> list[str]:
    """Names of external plugins discovered via the whytrail.explainers
    entry-point group -- installed as separate packages, not bundled
    in this repo (ADR §06)."""
    import importlib.metadata

    try:
        eps = importlib.metadata.entry_points(group=ENTRY_POINT_GROUP)
    except Exception:  # noqa: BLE001 - a broken environment must not break this either
        return []
    return sorted(ep.name for ep in eps)


def register(type_: type, explainer: Explainer) -> None:
    """Public, user-facing registration. Always takes precedence over
    a plugin-provided explainer for the same type, even if the plugin
    is (re)loaded afterward.

        whytrail.register(MyType, lambda obj: f"a MyType worth {obj.value}")
    """
    _registry[type_] = explainer
    _manual_types.add(type_)


def unregister(type_: type) -> None:
    _registry.pop(type_, None)
    _manual_types.discard(type_)


def register_from_plugin(type_: type, explainer: Explainer) -> None:
    """Plugin-facing registration, called from the function an entry
    point in group `whytrail.explainers` points to. Never overrides a
    user's manual register() call for the same type."""
    if type_ in _manual_types:
        return
    _registry.setdefault(type_, explainer)


def _load_entry_points() -> None:
    global _entry_points_loaded
    if _entry_points_loaded:
        return
    _entry_points_loaded = True
    import importlib.metadata  # lazy: ~30ms of this module's own import cost

    try:
        eps = importlib.metadata.entry_points(group=ENTRY_POINT_GROUP)
    except Exception:  # noqa: BLE001 - a broken environment must not break why()
        return
    for ep in eps:
        try:
            register_fn = ep.load()
            register_fn()
        except Exception:  # noqa: BLE001 - one broken plugin must not break the rest
            continue


def _load_builtin_explainers() -> None:
    global _builtins_loaded
    if _builtins_loaded:
        return
    _builtins_loaded = True
    for name in _BUILTIN_EXPLAINERS:
        try:
            module = importlib.import_module(f"whytrail.integrations.{name}")
            module.register()
        except Exception:  # noqa: BLE001 - missing extra or broken integration, either way skip it
            continue


def resolve_explainer(cls: type) -> Explainer | None:
    """Walk the MRO for a registered explainer -- own class first,
    then base classes, so a more specific registration always wins."""
    _load_builtin_explainers()
    _load_entry_points()
    for klass in cls.__mro__:
        if klass in _registry:
            return _registry[klass]
    return None


def coerce(obj: t.Any, result: t.Any) -> Explanation | None:
    if result is None:
        return None
    if isinstance(result, Explanation):
        return result
    if isinstance(result, str):
        return Explanation(subject=safe_repr(obj), steps=[ExplanationStep(description=result)], tracked=True)
    return None


def reset() -> None:
    """Testing hook: clear all registrations and force entry points and
    builtin integrations to be reloaded on next resolve."""
    global _entry_points_loaded, _builtins_loaded
    _registry.clear()
    _manual_types.clear()
    _entry_points_loaded = False
    _builtins_loaded = False
