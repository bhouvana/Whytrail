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

import importlib.metadata
import typing as t

from ._repr import safe_repr
from .core.explanation import Explanation, ExplanationStep

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
    "pandas",
    "polars",
)


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
