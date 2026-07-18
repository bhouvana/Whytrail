# ADR 0011: The provenance vocabulary is already sufficient (Phase U)

## Status

Accepted. No engine changes. New: `tests/integration/test_provenance_patterns.py`
(5 tests, each proving one candidate primitive against real executed
output), `examples/ex_provenance_patterns.py`, a new section in
`docs/explanation-engine.md`.

## Context

A review proposed treating the provenance engine "as a programming
language whose vocabulary is incomplete," and asked for the smallest
set of missing semantic primitives needed to describe causality:
transformation semantics, confidence propagation, branching, merging,
override semantics, and "provenance algebra" (composition -- a value
derived from multiple independent provenances). The review's own
closing caveat set the bar correctly: *"only keep a primitive if it
arises from multiple real use cases already visible in the project or
a concrete next consumer you're committed to building... discover the
smallest [vocabulary] that repeatedly proves itself indispensable."*

Each candidate was checked against real, executed code before writing
anything -- not assumed missing because the review's examples were
hypothetical (a `Policy(timeout, retry)` class, a three-source config
merge) rather than drawn from this project's own code.

## Decision: four of six candidates already work today, verified directly

1. **Transformation semantics** ("A was validated, normalized, clamped,
   rounded" -- not just "A became B"). Already expressible: decorate
   each transform step with `@tracked`; the call node's label is the
   function's own name, so a chain of `validate()` → `normalize()` →
   `clamp()` narrates exactly as named operations, in order, with no
   new vocabulary. Verified by actually running a three-step chain and
   reading `why()`'s output (`test_transformation_sequence_is_expressible_with_tracked`).

2. **Confidence propagation**. Already shipped and already tested
   elsewhere (`test_known_explanation_confidence_is_the_weakest_link`,
   `tests/unit/test_explanation.py`): `Explanation.confidence` is the
   minimum across every step, so a chain's overall confidence already
   degrades to its weakest hop. Confirmed here specifically across a
   three-hop chain with three different confidence levels, not just two.

3. **Branching** (one value affecting several independent downstream
   systems). Structurally already possible -- nothing in
   `ProvenanceGraph.add_edge()` limits a node to one outgoing edge --
   confirmed by tracking two independent children from one shared
   parent and checking each child's own `why()` correctly traces back
   to it. **What's genuinely not built**: a single forward query
   ("what does this value affect," returning every downstream
   consumer in one call) -- `ancestors()` only walks backward.
   This is not a new discovery: `docs/roadmap.md` Phase F already
   names exactly this ("richer ProvenanceGraph queries... 'all values
   derived from this input' rather than just 'why does this value
   exist'") and marks it "not started, deliberately... highest
   complexity, highest risk of scope creep." Re-affirmed here, not
   built, for the same reason -- no concrete consumer exists yet, and
   the review's own example didn't supply one.

   **Update (ADR 0012)**: built shortly after this ADR, once a sharper
   follow-up question ("can a forward query exist as pure traversal,
   introducing no new semantic concept?") was answered yes and a real
   consumer showed up (the same need to demonstrate this exact
   branching example cleanly). `ProvenanceGraph.descendants()` mirrors
   `ancestors()` exactly, over an index (`_edges_by_source`) that
   already existed. See ADR 0012 for the full reasoning -- the
   deferral above was correct at the time; "no concrete consumer" and
   "high implementation risk" turned out to be two separate questions,
   and only the first was still true when this was revisited.

4. **Merging / override semantics** ("why did the final value win, not
   just where it came from"). Already shipped:
   `whytrail.config.env()`'s `source_label` doesn't just name the
   winning source, it states *why the others didn't apply* -- e.g.
   `"'KEY' from .env (not set in the process environment)"`. Verified
   across all three priority levels (environment wins over dotenv wins
   over default), not assumed from reading the one example in
   `config.py`'s docstring.

5. **"Provenance algebra" / composition** -- the example the review was
   most enthusiastic about: `Policy(timeout, retry)`, where `why(policy)`
   should explain it was "combined from independent provenances," not
   just list two facts. **Already true, exactly as described**:
   `@tracked`'s `_link_arguments` links every argument's own node to
   the call node regardless of how many arguments there are, so two
   independently-sourced config values converging on one constructor
   call already produce precisely this shape. Not hidden, either --
   `_steps_from_traversal`'s existing "+N other paths converge here,
   see .graph()" note (added for an unrelated `trace(deep=True)`
   diamond case, ADR 0002 finding 3) fires for this case too, and
   `.graph()` shows the complete join: both config values, both with
   their own root cause, both landing on the same call node via two
   `passed_to` edges. Verified by actually constructing this exact
   scenario and reading both `.text` and `.graph()`
   (`test_composition_algebra_a_value_derived_from_two_independent_provenances`).

## Decision: why this generalizes without new `NodeKind`/`EdgeKind` values

ADR 0008's invariant 2 already explains why: *"The engine's own code
never references a specific producer's vocabulary... `NodeKind`/
`EdgeKind` values are inert labels the engine stores and returns
without interpreting."* Transformation, branching, merging, and
composition aren't missing engine capabilities -- they're patterns of
*using* the existing inert-label graph (arbitrary fan-out, arbitrary
fan-in, free-text labels, `derived_from`/`passed_to` edges) that happen
to not have been written down as named patterns before. The one
candidate that would require new capability (a forward/downstream
query) is already named and deliberately deferred elsewhere, for a
reason that still holds.

## Consequences

- No new `EdgeKind`/`NodeKind` values, no query-language layer, no
  "algebra" abstraction added. The four proven-already-true patterns
  are now written down as permanent regression tests and a
  `docs/explanation-engine.md` section ("Expressing common provenance
  patterns"), so a future contributor doesn't have to independently
  rediscover that `@tracked` already composes this way.
- `docs/roadmap.md` Phase F is unchanged in status (still "not started,
  deliberately") but now cross-references this ADR as the second time
  the same forward-query idea was raised and deferred for lack of a
  real consumer.
- If a genuinely new primitive is proposed later, the bar this ADR sets
  is the same the review itself asked for: show it against real,
  executed code first, the way all four here were checked, before
  concluding the vocabulary needs to grow.
