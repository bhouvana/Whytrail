# ADR 0002: Category strategy and pre-1.0 API fixes

**Status:** Accepted. API fixes applied; plugin roadmap in progress.

## Context

Before 1.0, a strategy review asked what category whytrail actually belongs
to, audited the implementation with fresh eyes, and proposed an ecosystem
plan. Full reasoning below; the review itself was more thorough in
narrative form than this record needs to be verbatim.

## Decision: the category is "runtime provenance," not "causality"

Rejected as brand/category words: **causality** (collides with statistical
causal inference -- Pearl, do-calculus -- a real, different field; ADR
0001 already rejected doing causal inference, so claiming the word invites
a fight this library doesn't need to have) and **explainability** (collides
with ML model interpretability -- SHAP, LIME). Chosen: **provenance**, an
established field (W3C PROV, OpenLineage) that currently operates at
pipeline/table granularity. whytrail occupies an unserved granularity one
level below OpenTelemetry and one above a bare traceback: which local
call/value produced this object, inside a single process. The sentence:
"I use whytrail to find out where a value came from."

## Decision: six issues found on re-reading the implementation

1. **`trace()`'s decorator form collided with `@tracked`** -- two
   similarly-spelled decorators, different meanings. **Fixed**: `trace()`
   is context-manager-only now (`src/whytrail/runtime/context.py`).
2. Confidence markers (`==`/`~~`/`..`) are illegible without documentation.
   Not yet fixed -- low cost to fix later, tracked as a follow-up.
3. `Explanation.text`'s single-dominant-path summary can silently hide a
   real DAG (discovered via `trace(deep=True)` on a diamond-shaped call
   graph, see `tests/integration/test_deep_trace.py`). Documented in code;
   UX fix (surface "+N other paths, see .graph()") not yet implemented.
4. **Top-level namespace carried advanced surface** (`NodeKind`,
   `EdgeKind`, `Node`, `Edge`, `ProvenanceGraph`, `TraceScope`,
   `SupportsWhy`). **Fixed**: `whytrail.__all__` shrunk to the five verbs,
   `snapshot`/`restore`, and `Explanation`/`ExplanationStep`/`Confidence`
   (kept, unlike the review's stricter suggestion, because they're the
   vocabulary of writing an explainer per `docs/plugin-guide.md`, not an
   advanced-only concern). Everything else stays importable from its
   submodule.
5. **Locals capture is a live security liability the moment a web
   framework is involved.** Tier 1's locals capture is correct for local
   dev/CI and wrong to expose unmodified in an HTTP response. Binding
   constraint on `whytrail-fastapi`/`whytrail-django`: default OFF for
   anything reachable from a response; explicit opt-in with a redaction
   hook.
6. **The plugin protocol (`Explainer = Callable[[Any], Explanation | str |
   None]`) has no version independent of whytrail's own release.** **Fixed**:
   `whytrail.registry.EXPLAINER_PROTOCOL_VERSION = 1` names the frozen
   contract (explainer shape, `register()`/`register_from_plugin()`
   precedence, entry-point group, MRO resolution order) independent of
   whytrail's own semver, with what's covered and what a v2 would require
   documented in `docs/plugin-guide.md`'s "Protocol version" section.

## Decision: ecosystem strategy is tiered, not a flat list

Rejected treating ~20 candidate integrations as equally real. Tiered by
actual leverage (cheap-and-real vs. plausible vs. named-but-not-a-fit) --
see `docs/plugin-guide.md` and the plugin distributions under `plugins/`
for what shipped. Kubernetes/Redis/Celery-as-named were flagged as weak
fits absent a concrete use case; LangChain-style LLM application
debugging was flagged as the highest-leverage wedge *not* in the original
brainstorm, because "why did this chain produce this output" is close to
exactly whytrail's model applied to a currently underserved, fast-moving
market.

## Decision: governance, naming, PEP adoption, and "the company question"

- **Governance**: borrow OpenTelemetry's spec/core/contrib split in
  shape, not in scale -- build it when a second maintainer and a real
  plugin backlog exist, not before.
- **Naming**: `whytrail` is a genuine asset (memorable, matches the API) and
  a genuine liability (reads as a side project next to `SQLAlchemy`/
  `Pydantic`). Not a reason to rename; a reason to give the underlying
  contract a separate, sober identity later if enterprise credibility
  becomes the binding constraint (the Jupyter / Project Jupyter pattern).
- **PEP adoption**: not a goal. The realistic precedent (`contextvars`,
  PEP 567) required a widely-shared problem across many independent
  libraries, not one library's success. `__why__` doesn't need CPython's
  involvement, the same way `__repr__`-adjacent third-party protocols
  never have.
- **The company question**: the coherent shape, if pursued at all, is a
  Sentry-shaped hosted aggregation/search layer over the `Explanation`/
  graph events the OSS library already emits via the OTel/Sentry export
  paths -- conditioned on the core library never making a network call on
  its own, and the local/free experience staying fully complete forever.
  Multi-year outcome, not a 1.0 workstream.

## Consequences

- Building further plugins now proceeds against the shrunk namespace and
  single-form `trace()`, avoiding a second breaking change once external
  plugins exist.
- Item 2 above remains open and is cheap to fix post-hoc (additive),
  unlike items 1 and 4 (namespace/API shape, expensive to change once
  depended upon) and item 5 (security, expensive to get wrong even
  once). Items 3 and 6 have since been fixed.
