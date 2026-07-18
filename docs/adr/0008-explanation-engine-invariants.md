# ADR 0008: Explanation Engine invariants

## Status

Accepted and implemented: an audit of every file that touches `Node`/
`Edge`, six new architecture-level tests
(`tests/integration/test_engine_invariants.py`), one real bug found
and fixed (`whytrail/config.py`), and the internal guide
(`docs/explanation-engine.md`) this ADR points to.

## Context

ADR 0007 named the Explanation Engine and proved it with a second real
producer (`whytrail.config`). The natural next mistake -- the one most
projects make at exactly this point -- is to keep adding consumers
until the "engine" is just a label over an increasingly ad hoc pile of
special cases. The brief for this phase was the opposite: stop adding
consumers, and instead check whether the engine actually deserves the
"general" label ADR 0007 gave it, then write down the rules that keep
it that way.

Two scoping calls made before the audit, both directly from how this
phase was briefed:

- **No `Producer` class hierarchy.** Every current producer (Tier 1's
  `explain_exception`, `capture.py`'s `track()`/`@tracked`,
  `propagation.py`, `config.py`) already follows the same shape --
  write `Node`/`Edge` via `ProvenanceGraph`'s public API -- without
  inheriting from anything. Introducing an ABC today would be
  speculative machinery for a convention three call sites already
  follow; the concept is documented in `docs/explanation-engine.md`,
  not enforced by a base class.
- **No new producers.** AWS Parameter Store, Secrets Manager, Terraform,
  workflow engines, and the rest of the review's later-phase list stay
  unbuilt -- this phase is about the seam those would eventually plug
  into, not about building one of them early to test the seam.

## Audit: is the graph secretly exception-shaped?

Read every file that touches `Node` or `Edge` looking for one thing:
code that assumes its subject is an exception, or behaves differently
depending on producer identity.

1. **`core/graph.py`, `core/node.py`, `core/serialize.py`,
   `registry.py`, `protocols.py` -- clean.** `NodeKind.EXCEPTION` is one
   of six enum members (`VALUE`, `CALL`, `EXCEPTION`, `MUTATION`,
   `EXTERNAL`, `IMPORT`); nothing in storage, traversal, or
   serialization treats it differently from the other five. No
   `if kind == "exception"` (or `"config"`, or any producer's name)
   anywhere in the engine's own code.
2. **`core/explanation.py` is domain-aware, and that's fine, but it
   needs saying out loud.** `.plain_text` and `.json()`'s `suggestion`
   field carry exception-specific glosses (`_EXCEPTION_GLOSS`,
   `_EXCEPTION_FIXES`), gated on `ExplanationStep.kind == "exception"`.
   This is *rendering* reading an opaque string field and choosing
   prose for it -- not the graph or traversal knowing what an exception
   is. The distinction matters because it's easy to conflate "does
   whytrail's output mention exceptions specifically" with "is
   whytrail's graph exception-shaped," and the audit's honest answer is
   yes to the first, no to the second.
3. **A real architectural boundary, not a bug:** `whytrail/__init__.py`'s
   `_why_impl` routes any `BaseException` to Tier 1
   (`explain_exception`) unconditionally, before the graph-lookup path
   (`_explain_from_graph`) is ever reached. Concretely: if an exception
   object was separately given graph provenance (e.g. passed to
   `track()` before being raised), `why()` on it still answers purely
   from the traceback walk -- the graph-tracked provenance is never
   consulted or merged in. This is ADR 0001's two-tier split working
   exactly as designed (Tier 1 needs zero setup and answers from data
   CPython already retains; Tier 2 needs an opt-in `trace()` scope),
   not an oversight. Merging the two would be a real change to `why()`'s
   resolution order with no evidence it's needed -- not made here.
   Pinned instead of silently assumed:
   `test_tier1_does_not_consult_the_graph_even_for_a_graph_tracked_exception`.
4. **A real bug, found and fixed:** `whytrail/config.py`'s missing-key
   branch created a `NodeKind.EXTERNAL` node with no `obj=` and no edge
   pointing at it. Per finding 3, `why()` never looks at the graph for
   the `ConfigError` about to be raised anyway -- so this node was
   permanently unreachable by any traversal from the moment it was
   written. Removed; `ConfigError`'s own message already states what
   was checked, and Tier 1 explains the raised exception for free.

Conclusion: the graph engine itself was already general, confirmed by
reading it rather than assumed from ADR 0007's own argument. The one
real defect this audit found was in the newest producer, not the
engine.

## Decision: six invariants

These are checked against the audit above, not aspirational -- each
one is either confirmed true today or now has a test pinning it.

1. **Producers use only `ProvenanceGraph`'s public API**
   (`add_node`, `add_edge`, `node_for`, `ancestors`) -- never its
   leading-underscore internals. `core/serialize.py` is the one
   deliberate exception (already marked `# noqa: SLF001`, for the
   reason stated there: it's core-internal persistence, not a plugin).
2. **The engine's own code never references a specific producer's
   vocabulary.** No `if kind == "config"` or equivalent anywhere in
   `core/`, `registry.py`, or `protocols.py`. `NodeKind`/`EdgeKind`
   values are inert labels the engine stores and returns without
   interpreting.
3. **Rendering may be domain-aware; the graph is not, and the two
   claims are independent.** `.text`/`.plain_text`/`.json()` may
   special-case specific `ExplanationStep.kind`/`.description` values
   for better prose (see finding 2). That never implies anything about
   whether storage or traversal special-case that domain -- confirmed
   separately, per invariant 2.
4. **Tier 1 and the provenance graph are separate, non-merging
   producers for exceptions, by design.** `why()` on a `BaseException`
   always resolves via the traceback walk; it does not consult graph
   provenance for that object even if some exists. Not a gap to close
   without real evidence it matters (see finding 3).
5. **Unknown is always representable, for any producer.** An object
   nothing has recorded anything about gets
   `Explanation(steps=[], tracked=False)` -- never a fabricated chain.
   True today across exceptions, tracked values, and config values
   alike.
6. **Traversal is deterministic for a fixed graph and safe against
   cycles.** `ProvenanceGraph.ancestors()`'s `visited_nodes` id-set
   prevents re-expanding an already-visited node, so a cycle terminates
   rather than looping. Both properties are now pinned by tests, not
   just true by inspection.

## Consequences

- New: this ADR, `docs/explanation-engine.md` (the internal guide these
  invariants are explained in prose for a first-time contributor), and
  `tests/integration/test_engine_invariants.py` (6 tests covering
  invariants 4, 5, and 6 directly, plus cross-producer traversal).
- Fixed: `whytrail/config.py`'s missing-key branch no longer creates an
  unreachable graph node.
- No core redesign. The audit's answer to "is the graph secretly
  optimized only for exceptions" is no, and that answer is now backed
  by having read every file that touches `Node`/`Edge`, not by
  repeating ADR 0007's own claim.
- "Freeze the core" is named as a norm the six invariants above encode,
  not imposed as a new hard process gate (no CI enforcement added) --
  consistent with this project's general discipline of not building
  enforcement machinery ahead of a real violation to enforce against.
  A future PR that violates one of these six should cite this ADR in
  review, not invent a new debate about whether the graph is allowed to
  know about exceptions.
- The next real producer -- a plugin, or a future core module -- has
  `docs/explanation-engine.md` to read and
  `test_engine_invariants.py` to hold itself against, instead of
  re-deriving "is this allowed" from first principles each time.
