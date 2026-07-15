#!/usr/bin/env python
"""Scaffold a new *external* whytrail plugin distribution (ADR 0003, ADR 0006).

As of ADR 0006, whytrail's own 30 integrations ship bundled inside the
whytrail package itself as optional extras (src/whytrail/integrations/,
`pip install whytrail[requests]` etc.) -- one release process instead of
30. This script is NOT for adding to that bundled set: if you're
contributing a new integration directly to this repo, add a module under
src/whytrail/integrations/, register it in registry.py's
_BUILTIN_EXPLAINERS (explainer-shaped) or leave it to be imported
directly (integration-shaped), and add its extra to pyproject.toml --
see docs/plugin-guide.md.

What this script generates instead is a *separate*, independently
published plugin -- for anyone who wants to maintain their own
integration outside this repo, discovered via the `whytrail.explainers`
entry point the same way the bundled 30 used to work before ADR 0006.
That mechanism was deliberately kept, not removed: it's still how a
third party (or whytrail itself, again, if governance ever needs the
OpenTelemetry-style core/contrib split ADR 0002 mentions) plugs in
without a PR against this repo.

The boilerplate that's identical every time is: a pyproject.toml with
the right build backend and dependency shape, a package that imports
whytrail's public API correctly, and a starter test file in the right
place using the right importorskip pattern. What's *not* boilerplate --
and this script deliberately does not try to generate -- is the actual
judgment call of what to explain and how, which is the entire point of
ADR 0003's triage: most libraries don't need a plugin at all, and the
ones that do need a real design pass, not a template filled in on
autopilot.

Usage:
    python scripts/new_plugin.py requests_toolbelt --kind explainer --type RequestsToolbeltError
    python scripts/new_plugin.py airflow --kind integration

--kind explainer:   registers via the whytrail.explainers entry point
                     (the requests/pandas/sqlalchemy pattern) -- use
                     this when the library has specific exception
                     types or objects worth a dedicated explainer.
--kind integration:  no entry point; the user wires it in explicitly
                     (the sentry/celery/pytest/fastapi/django pattern)
                     -- use this when there's a hook system (signals,
                     callbacks, middleware) rather than a type to
                     register an explainer for.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLUGINS_DIR = ROOT / "plugins"
TESTS_DIR = ROOT / "tests" / "plugin_contract"

EXPLAINER_INIT = '''"""whytrail plugin for {library} (ADR 0003).

TODO: one sentence on what this actually explains, and why a bare
traceback / tier-1 exception explainer isn't already good enough for
it -- if you can't answer that concretely, this plugin probably
shouldn't exist (see ADR 0003's triage methodology before going
further).
"""

from __future__ import annotations

import {import_name}

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin

__version__ = "0.1.0"


def _explain_{safe_name}(exc: "{import_name}.{type_name}") -> Explanation:
    steps = [
        ExplanationStep(
            description=f"{{type(exc).__name__}}: {{exc}}",
            confidence=Confidence.EXPLICIT.value,
            kind="exception",
        ),
        # TODO: add steps for whatever structured detail {type_name}
        # actually carries (see whytrail-sqlalchemy's .statement/.params,
        # or whytrail-requests' .request/.response, for the pattern).
        # If any of it could be sensitive (payloads, tokens, PII), put
        # it in `locals=` on an ExplanationStep, not `description` --
        # that's what makes Explanation.redacted() strip it before
        # anything exports off-box. See ADR 0002 §3 item 5.
    ]
    return Explanation(subject=f"{{type(exc).__name__}}: {{exc}}", steps=steps, tracked=True)


def register() -> None:
    register_from_plugin({import_name}.{type_name}, _explain_{safe_name})
'''

INTEGRATION_INIT = '''"""whytrail plugin for {library} (ADR 0003).

TODO: this is the "integration" shape -- no whytrail.explainers entry
point, because {library} has its own hook system (a signal, a
callback, a middleware protocol) rather than a type worth registering
a why()-explainer for. Wire whytrail.why() into that hook here, the way
whytrail-celery does for task_failure or whytrail-pytest does for
pytest_exception_interact.

If any data this touches could be sensitive (task payloads, request
locals, query params), redact by default and require an explicit,
separate opt-in to include it anywhere that leaves the process --
see whytrail-fastapi and whytrail-django for the reference pattern
(ADR 0002 §3 item 5). This is not optional polish; it's the most
common way one of these integrations goes wrong.
"""

from __future__ import annotations

import logging
import typing as t

import whytrail

__version__ = "0.1.0"

_logger = logging.getLogger("whytrail.{safe_name}")


def install(*, log_locals: bool = False, logger: logging.Logger | None = None) -> None:
    """TODO: wire this into {library}'s actual hook system."""
    log = logger or _logger
    raise NotImplementedError("wire this into {library}'s hook system, then delete this line")
'''

TEST_TEMPLATE = '''"""Validates whytrail-{safe_name} end to end against the real {library}
library -- not a mock of its API. See docs/plugin-guide.md for what
a plugin's test suite needs to cover before it ships:
  - the entry point (or hook) actually fires
  - the happy path produces a real explanation
  - a manual whytrail.register() override still wins, if this is an
    `explainer`-kind plugin
  - anything sensitive is redacted by default, if this plugin touches
    data that could be (see ADR 0002 §3 item 5)
"""

from __future__ import annotations

import pytest

{import_name} = pytest.importorskip("{import_name}")
pytest.importorskip("whytrail_{safe_name}")

import whytrail  # noqa: E402


def test_plugin_loads():
    import whytrail_{safe_name}  # noqa: F401


# TODO: real tests against real {library} objects/errors.
'''

README_TEMPLATE = """# whytrail-{safe_name_dash}

TODO: one paragraph -- what does why() show for {library} that a bare
traceback doesn't? If you can't fill this in convincingly, revisit
whether this plugin should exist (ADR 0003).

```python
# TODO: a real, runnable example
```
"""

PYPROJECT_EXPLAINER = '''[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "whytrail-{safe_name_dash}"
version = "0.1.0"
description = "TODO"
readme = "README.md"
license = "MIT"
requires-python = ">=3.10"
dependencies = ["whytrail", "{library}"]

[project.entry-points."whytrail.explainers"]
{safe_name} = "whytrail_{safe_name}:register"

[tool.hatch.build.targets.wheel]
packages = ["src/whytrail_{safe_name}"]
'''

PYPROJECT_INTEGRATION = '''[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "whytrail-{safe_name_dash}"
version = "0.1.0"
description = "TODO"
readme = "README.md"
license = "MIT"
requires-python = ">=3.10"
dependencies = ["whytrail", "{library}"]

[tool.hatch.build.targets.wheel]
packages = ["src/whytrail_{safe_name}"]
'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("library", help="the library to explain, e.g. 'requests_toolbelt' or 'airflow'")
    parser.add_argument("--kind", choices=["explainer", "integration"], required=True)
    parser.add_argument("--type", dest="type_name", default="TODOException", help="(explainer only) the exception/type to register for")
    parser.add_argument("--import-name", default=None, help="the module import name, if different from `library`")
    args = parser.parse_args()

    safe_name = args.library.replace("-", "_")
    import_name = args.import_name or safe_name
    safe_name_dash = safe_name.replace("_", "-")

    plugin_dir = PLUGINS_DIR / f"whytrail-{safe_name_dash}"
    src_dir = plugin_dir / "src" / f"whytrail_{safe_name}"
    if plugin_dir.exists():
        print(f"error: {plugin_dir} already exists", file=sys.stderr)
        return 1

    src_dir.mkdir(parents=True)

    (plugin_dir / "README.md").write_text(
        README_TEMPLATE.format(safe_name_dash=safe_name_dash, library=args.library)
    )

    if args.kind == "explainer":
        (plugin_dir / "pyproject.toml").write_text(
            PYPROJECT_EXPLAINER.format(safe_name_dash=safe_name_dash, safe_name=safe_name, library=args.library)
        )
        (src_dir / "__init__.py").write_text(
            EXPLAINER_INIT.format(
                library=args.library, import_name=import_name, safe_name=safe_name, type_name=args.type_name
            )
        )
    else:
        (plugin_dir / "pyproject.toml").write_text(
            PYPROJECT_INTEGRATION.format(safe_name_dash=safe_name_dash, library=args.library)
        )
        (src_dir / "__init__.py").write_text(INTEGRATION_INIT.format(library=args.library, safe_name=safe_name))

    test_path = TESTS_DIR / f"test_{safe_name}_plugin.py"
    test_path.write_text(TEST_TEMPLATE.format(safe_name=safe_name, library=args.library, import_name=import_name))

    print(f"Created {plugin_dir}")
    print(f"Created {test_path}")
    print()
    print("Next: fill in the TODOs, then:")
    print(f"  pip install -e ./plugins/whytrail-{safe_name_dash}")
    print(f"  pytest {test_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
