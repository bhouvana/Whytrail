# ADR 0006: Unify the 30 plugins into extras of one package

## Status

Implemented. Reverses the "30 separate distributions" shape decided in
ADR 0001/0002 and built out across this project's early sessions.

## Context

By the time whytrail first published to PyPI, the ecosystem was 30
separate distributions (`whytrail-requests`, `whytrail-pydantic`, ...),
each its own `pyproject.toml`, each independently versioned, each
needing its own PyPI project and (per ADR 0004's trusted-publishing
setup) its own pending-publisher registration.

Two things surfaced together, right after the first publish:

1. **None of the 30 were actually on PyPI.** Only core `whytrail` was.
   The README's ecosystem table implied `pip install whytrail-requests`
   would work; it didn't. Anyone who read the README and tried it got
   "no matching distribution found" -- the entire integration story was
   non-functional for a real user beyond the bare core library.
2. **Publishing all 30 meant registering 30 separate PyPI
   pending-publishers**, one at a time, by hand, on pypi.org -- real,
   repetitive setup work for packages with zero users yet, and 30
   ongoing release processes to keep in sync with core whytrail's own
   version going forward. The stated objection: "we can't keep creating
   new PyPI releases."

## Decision: bundle all 30 as optional extras of the single `whytrail` package

`pip install whytrail[requests]`, `pip install whytrail[all]`. One
PyPI project, one version number, one release process, one
trusted-publisher registration (already done). Nobody pays for
integrations they don't request -- `pip install whytrail` alone still
has zero required dependencies, same promise as before.

**Why extras, not just bundling everything as required dependencies**:
forcing pandas, Django, boto3, and 27 others onto every `pip install
whytrail` regardless of use is a real anti-pattern (bloat, install
time, dependency-conflict surface) that the "zero required dependencies"
design existed specifically to avoid. Extras get the release-simplicity
win without that cost -- the same pattern `sqlalchemy[postgresql,mysql]`
and `uvicorn[standard]` already use.

**What moved**: each `plugins/whytrail-X/src/whytrail_X/__init__.py`
became `src/whytrail/integrations/X.py`. The 18 explainer-shaped ones
(requests, pydantic, sqlalchemy, ...) auto-register the first time
`why()` needs them, via a new static list
(`registry._BUILTIN_EXPLAINERS`) checked lazily, the same
try-import-catch-ImportError pattern entry-point plugins already used --
installing the extra is the only step now, no entry point indirection
needed for code that lives in the same package as the thing discovering
it. The 12 integration-shaped ones (celery, fastapi, sentry, ...) don't
auto-register at all, same as before: a user imports
`whytrail.integrations.X` and wires it in explicitly (an
`on_failure=[...]` hook, a middleware class, `before_send=...`).

**What didn't change**: the `whytrail.explainers` entry-point mechanism
and `register_from_plugin()` stay exactly as documented -- not removed,
because they're still the right answer for a third party who wants to
publish their *own* integration without a PR against this repo (`scripts
/new_plugin.py` now scaffolds that external case specifically, having
previously scaffolded what's now the bundled 30). The Explainer Protocol
v1 freeze (ADR 0002 §3 item 6) and everything it guarantees is unchanged
by this ADR; it governs the entry-point path, which still exists.

## Consequences

- **CI got simpler, not just reshuffled.** The `plugin-version-matrix`
  job no longer needs an "install the plugin package without its
  dependency pin" step -- the integration module is already on disk as
  soon as core `whytrail` installs; it just doesn't successfully
  register until the extra's dependency is present. One fewer moving
  part, one fewer place for the kind of bug ADR 0006's own build found
  in the old two-step install sequence.
- **Losing independent plugin governance, deliberately, for now.**
  ADR 0002's own governance section already named the condition for a
  real core/contrib split: "build it when a second maintainer and a
  real plugin backlog exist, not before." That condition still hasn't
  been met -- this reversal doesn't contradict that reasoning, it
  follows it. If it's ever met, the entry-point mechanism this ADR keeps
  intact is exactly the seam a future split would use.
- **The `pytest` extra needs a caveat.** pytest's own `pytest11` entry
  point is registered unconditionally once whytrail is installed at
  all -- pytest's plugin discovery doesn't gate on which extras were
  requested, only on whether the package is present. In practice this
  means the pytest failure-report integration activates automatically
  for anyone who has both `whytrail` and `pytest` installed, whether or
  not they asked for the `pytest` extra specifically. Judged acceptable:
  the behavior is additive (an extra report section), has an explicit
  opt-out flag (`--no-whytrail`) already built in, and matches how every
  other pytest plugin's auto-discovery already works.
- **Version-matrix and contract-test CI jobs were rewritten**, not just
  patched, to install `whytrail[extra]` instead of a separate
  distribution. Verified against real Linux (Docker was unavailable in
  this sandbox; WSL2 + `uv`-managed Python filled in) before being
  pushed, the same discipline as every other CI change this project has
  made.
