# ADR 0007: name the Explanation Engine, reject the platform vision

## Status

Accepted and implemented: `whytrail/config.py` ships as part of this
ADR, proving the claim below with a real, tested consumer rather than
leaving it as a documentation-only assertion. No new `NodeKind`/
`EdgeKind` values were needed to build it.

## Context

An external review pitched a ten-phase, ten-year vision for whytrail
modeled on how `httpx` grew: "boring," axis-balanced architecture first,
then a long tail culminating in an observability platform, an IDE/CI
tooling ecosystem, and whytrail as cross-project "infrastructure." Its
sharpest claim, isolated from the rest: whytrail's core should be
architected as a general **Explanation Engine** with pluggable data
sources, provenance tracking, and renderers -- exceptions are just its
first consumer, not the whole mission.

That claim needed checking against the actual code before deciding
anything, the same standard `docs/roadmap.md` already holds itself to
("never claim more than is actually true"). Most of the review's later
phases (observability platform, editor/CI integrations, "becoming
infrastructure") are the same shape of thing this project has already
declined twice: ADR 0005 shelved a VS Code extension for "zero users to
serve" reasons, and `docs/roadmap.md` Phase O explicitly rejected an
"Enterprise Adoption" phase invented with no signal behind it. That
reasoning isn't revisited here because nothing in the review changes
it -- no new user signal exists today that didn't exist when those two
decisions were made.

The Explanation Engine claim is different in kind: it's a statement
about what the code *already is*, checkable by reading it rather than a
speculative feature to schedule.

## What the code actually shows

- `NodeKind` (`whytrail/core/node.py`) is not exception-shaped: `VALUE`,
  `CALL`, `EXCEPTION`, `MUTATION`, `EXTERNAL`, `IMPORT`. `EdgeKind` is
  not exception-shaped either: `DERIVED_FROM`, `RAISED_FROM`,
  `CAUSED_BY`, `OCCURRED_DURING`, `MUTATED_BY`, `PASSED_TO`.
- `EXTERNAL` is already load-bearing outside the exception path:
  `whytrail/propagation.py` records a `NodeKind.EXTERNAL` node for
  "this value crossed a process boundary," and
  `whytrail/integrations/langchain.py` uses the same node/edge
  vocabulary for a domain that has nothing to do with tracebacks.
- Resolution order in `why()` (`whytrail/__init__.py:_why_impl`) checks
  the `__why__` protocol and the type registry *before* the
  exception-specific tier-1 fallback -- both are already generic over
  "any type," not "any type or an exception."
- `register()` / `register_from_plugin()` (`whytrail/registry.py`) key
  on `type`, full stop. Nothing in the registry, the protocol, or the
  graph model assumes its subject is an exception or a `track()`ed
  value specifically.

Put together: the general engine the review is asking for was already
the actual decision in ADR 0001 (`## Decision: reject the literal
pitch, ship the reframed version`). What's missing isn't architecture,
it's a name. Every public-facing description of whytrail --
`whytrail/__init__.py`'s module docstring, `README.md`'s opening pitch
-- introduces the library through its two current consumers (Tier 1
exceptions, Tier 2 tracked values) without ever stating that the model
underneath is deliberately general. That's a real gap: a contributor
reading only the README has no reason to know `NodeKind.EXTERNAL` or
`NodeKind.IMPORT` exist, let alone that they're meant as the
extension point for exactly the "config resolved from an env var from
a secret manager" kind of chain the review describes.

## Decision

1. **Name it.** State explicitly, in `whytrail/__init__.py`'s module
   docstring and `README.md`'s opening section, that the core
   (`Node`/`Edge`/`Explanation`/registry/protocol) is a general causal-
   explanation engine, and that exceptions and tracked values are its
   first two consumers -- not the limit of what it models.
2. **Prove it with a real, scoped consumer, not just wording.**
   `whytrail/config.py` ships `env()`: resolves a setting from the
   process environment, a parsed `.env` mapping, or a default, and
   records which one actually won into the same `ProvenanceGraph`
   `track()` writes to, using only existing primitives
   (`NodeKind.EXTERNAL`, `NodeKind.IMPORT`, `graph.add_node`/
   `add_edge`). This is a deliberately narrow slice of the review's own
   "config -> .env -> Secret Manager -> Terraform -> AWS Parameter
   Store" example -- environment variable and `.env` mapping only, no
   cloud secret-manager integration. A missing key with no default
   raises `ConfigError`, a normal exception, so Tier 1 already explains
   *that* case for free -- no separate explainer needed, following the
   same "route through what's already free" logic ADR 0001 applied to
   exceptions generally. `load_dotenv()` is a matching narrow-by-design
   `.env` parser (no interpolation, no multiline, no `export`) rather
   than a partial reimplementation of `python-dotenv`'s full format --
   callers needing more pass their own parser's output as `dotenv=`.
3. **Reject the platform phases.** The observability-platform,
   IDE/CI-ecosystem, and "becoming infrastructure" phases of the
   reviewed vision are not adopted, for the same reason ADR 0005 and
   roadmap Phase O already gave: whytrail has real releases (0.1.0,
   0.2.0, 0.2.1) but still no evidence of real usage to build
   speculative consumer tooling against. Building for imagined
   consumers before real ones is the adoption-funnel inversion ADR
   0005 already named. Cloud secret-manager/Terraform/Parameter Store
   integration specifically stays out for the same reason plugins
   generally require a checked real object before code is written
   (ADR 0003) -- none of those was checked against real usage here.
4. **One phase does get a citation, not new scope.** `docs/roadmap.md`
   Phase F ("Advanced provenance") is already the named home for any
   real extension of the *graph engine itself* -- richer
   `ProvenanceGraph` queries, async-aware tracing across `await`
   boundaries. `whytrail.config` doesn't touch any of that; it's a new
   caller of existing capability, the same relationship
   `propagation.py` already has to the graph. This ADR adds one
   sentence to Phase F pointing back here so "does the model already
   support X" doesn't get re-derived from scratch next time someone
   asks. It does not move Phase F earlier or expand its scope; that
   stays gated on the same evidence standard as before ("not started,
   deliberately").

## Consequences

- New module: `whytrail/config.py` (`env`, `load_dotenv`,
  `ConfigError`), covered by `tests/integration/test_config.py` (9
  tests) and `mypy --strict`-clean. Not part of the top-level
  `whytrail` namespace -- `import whytrail.config` explicitly, the
  same discipline `ProvenanceGraph`/`TraceScope`/`NodeKind` already
  follow (see `whytrail/__init__.py`'s namespace note).
- No new `NodeKind`, `EdgeKind`, or top-level public verb. `why()`
  itself is unchanged -- `config.env()`'s tracked return value flows
  through the existing graph-lookup path with zero special-casing.
- Cloud secret-manager/Parameter Store/Terraform provenance stays
  unimplemented -- named here as explicitly out of scope, not silently
  dropped, so it isn't re-proposed as if this ADR never considered it.
  Revisit only if a real user asks, same trigger as ADR 0005 names for
  the platform-scale phases.
- This ADR is citable the next time a "make whytrail into a platform"
  pitch comes up: the general-engine part was already true and is now
  both named and demonstrated; the platform part was assessed and
  declined for a stated, checkable reason, not silently ignored.
