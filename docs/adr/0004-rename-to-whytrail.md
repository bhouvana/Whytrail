# ADR 0004: Rename from butwhy to whytrail

**Status:** Accepted and executed.

## Context

Before a real PyPI publish, the package name `butwhy` was checked against
the live PyPI index for the first time. It was already taken -- an
unrelated project, published 2026-06-30 (roughly two weeks before this
check), with a real 0.1.0 release: full README, badges, keywords,
classifiers. Not a placeholder or a squat.

The collision was more than a naming inconvenience. Reading that
project's own README surfaced a real, substantive conflict: its
approach is pattern-matching plus optional LLM calls (`OPENAI_API_KEY`/
`ANTHROPIC_API_KEY`) to generate explanations, surfaced with a
confidence percentage (`[pattern match · 93%]`). That is close to the
opposite of the design this project committed to in ADR 0001 §1: never
fabricate a causal chain, answer "unknown" rather than guess, ground
every claim in data CPython actually retains. Shipping under the same
name as a tool with a contradictory philosophy would have meant a
permanent, unresolvable branding collision -- users searching "butwhy
python" would land on a tool making exactly the kind of confident,
ungrounded guess this project's entire architecture exists to avoid.

## Decision

Renamed the project, in full, to **whytrail**.

Candidate names were checked against the live PyPI index before
selection, not assumed available:

| Candidate | Status |
|---|---|
| `causeway` | Taken |
| `whytrace` | Taken |
| `pywhy` | Taken -- Microsoft's real causal-inference toolkit, which independently confirms ADR 0002's reasoning for avoiding "causal" in this project's own naming |
| `whycause` | Available, rejected -- same "causal" collision risk |
| `causalwhy` | Available, rejected -- same reason |
| `tracewhy` | Available |
| `rootwhy` | Available, rejected -- implies root-cause *analysis*, a heavier and different discipline than provenance |
| **`whytrail`** | **Available, selected** -- names the actual mechanism (following the trail back to a value's origin) without touching "causal" (taken, and flagged as dangerous in ADR 0002) or "explain" (collides with ML explainability, also flagged in ADR 0002) |

## What changed

A complete, uniform rename across the repository: `src/butwhy` →
`src/whytrail`; all 30 `plugins/butwhy-*` directories and their inner
`butwhy_*` package directories → `whytrail-*` / `whytrail_*`; the
`butwhy.explainers` entry-point group → `whytrail.explainers` (every
plugin's `pyproject.toml` updated to match, not just the registry
constant); class names (`ButwhyMiddleware` → `WhytrailMiddleware`,
`ButwhyCallbackHandler` → `WhytrailCallbackHandler`); environment/settings
names (`BUTWHY_DEBUG` → `WHYTRAIL_DEBUG`, etc.); the CLI command; the
GitHub Action directory; and all prose across the README, CHANGELOG,
plugin guide, testing-maturity doc, and — deliberately, including — the
prior ADRs (0001-0003).

That last point is worth being explicit about: renaming the historical
ADRs' prose and file paths (rather than leaving them referring to
`butwhy`) trades a small amount of literal historical accuracy for a
repository that is internally consistent and has working links, which
was judged the better trade given this document exists specifically to
preserve the "why did we ever call it butwhy" context that would
otherwise be lost. The original name and the reasoning for changing it
live here, once, rather than being scattered as stale references
throughout documents that predate the rename.

## Consequences

- No functional or architectural change. Every design decision in ADRs
  0001-0003 stands; only the name changed.
- The entry-point group rename (`butwhy.explainers` →
  `whytrail.explainers`) is a breaking change to the plugin protocol
  ADR 0002 §6 already flagged as needing to be frozen before external
  (non-reference) plugins depend on it. Doing the rename now, before any
  1.0 release or external plugin exists, is the cheapest this kind of
  change will ever be — exactly the reasoning ADR 0002 applied to the
  API fixes it made pre-1.0.
- All packages had to be uninstalled and reinstalled under the new
  names in the local development environment; a fresh clone or CI run
  is unaffected since it only ever sees the renamed state.
