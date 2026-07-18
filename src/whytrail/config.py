"""Configuration-value provenance.

env() answers "where did this setting come from" the same way track()
answers "where did this value come from" for anything else -- built
entirely on existing primitives (ProvenanceGraph, NodeKind.EXTERNAL /
NodeKind.IMPORT), not a new capture mechanism (ADR 0007: the graph
model was already general, this is a second real consumer of it, not
new architecture). Not part of the top-level `whytrail` namespace --
`import whytrail.config` explicitly, same discipline as
`whytrail.core.graph.ProvenanceGraph` or `whytrail.runtime.context.trace`
(see whytrail/__init__.py's namespace note).
"""

from __future__ import annotations

import os
import typing as t

from .core.node import Confidence, EdgeKind, NodeKind
from .runtime.context import active_graph, current_scope

_T = t.TypeVar("_T")
_MISSING: t.Any = object()


class ConfigError(LookupError):
    """No value found for a config key, and no default was given.

    Raising (rather than returning None) means Tier 1 already explains
    this the moment it's caught or left uncaught, straight from
    __traceback__ -- no separate explainer needed for "why is this
    missing," the same "answer through the one thing that's already
    free" reasoning ADR 0001 applied to exceptions generally.
    """


def load_dotenv(path: str) -> dict[str, str]:
    """Parse a simple KEY=VALUE .env file into a dict.

    Deliberately minimal: no interpolation, no multiline values, no
    `export` prefix. A narrow parser that's honest about what it
    covers beats a broad one that's iffy about edge cases -- the same
    "never fabricate" standard whytrail holds its causal chains to,
    applied here to what this function claims to parse. Use
    python-dotenv directly and pass its result as `dotenv=` to env()
    if a file needs more than this handles.
    """
    values: dict[str, str] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            if key:
                values[key] = value
    return values


def env(
    name: str,
    default: t.Any = _MISSING,
    *,
    dotenv: t.Mapping[str, str] | None = None,
    cast: t.Callable[[str], _T] | None = None,
) -> t.Any:
    """Look up an environment variable, recording where the returned
    value actually came from: the process environment, a `dotenv`
    mapping (e.g. from load_dotenv()), or `default` -- in that order.
    Raises ConfigError if none of those has it.

        API_KEY = whytrail.config.env("API_KEY")
        TIMEOUT = whytrail.config.env("TIMEOUT", 30, cast=int)
        DEBUG = whytrail.config.env("DEBUG", False, dotenv=whytrail.config.load_dotenv(".env"))

    Provenance is only recorded inside an open trace() scope, at zero
    cost outside one -- the same "off by default" contract as
    track() (ADR §09). Whether a value is found or not never depends
    on tracing being active; only whether that resolution gets
    recorded into the graph does.
    """
    scope = current_scope()
    capture = scope is not None and scope.should_capture()

    checked = ["the environment"]
    raw: str | None
    if name in os.environ:
        raw = os.environ[name]
        source_kind = NodeKind.EXTERNAL
        source_label = f"environment variable {name!r}"
        confidence = Confidence.EXPLICIT.value
    elif dotenv is not None and name in dotenv:
        checked.append(".env")
        raw = dotenv[name]
        source_kind = NodeKind.IMPORT
        source_label = f"{name!r} from .env (not set in the process environment)"
        confidence = Confidence.INFERRED.value
    else:
        if dotenv is not None:
            checked.append(".env")
        if default is _MISSING:
            # No graph node recorded here on purpose (a prior version of
            # this function added one): why() never consults the graph
            # for a BaseException subject (see ADR 0008 -- Tier 1 always
            # wins for exceptions), so a node here would be created and
            # then be permanently unreachable by anything. ConfigError's
            # own message already carries what was checked; Tier 1
            # explains it for free the moment it's raised or caught.
            raise ConfigError(
                f"no value for {name!r}: checked {', '.join(checked)}, and no default was given"
            )
        raw = None
        source_kind = NodeKind.EXTERNAL
        source_label = f"default value for {name!r} (checked {', '.join(checked)}, not found)"
        confidence = Confidence.EXPLICIT.value

    value: t.Any = default if raw is None else (cast(raw) if cast is not None else raw)

    if capture:
        graph = active_graph()
        source_node = graph.add_node(source_kind, source_label)
        value_node = graph.add_node(NodeKind.VALUE, f"{name}={value!r}", obj=value)
        graph.add_edge(source_node, value_node, EdgeKind.DERIVED_FROM, confidence=confidence)

    return value
