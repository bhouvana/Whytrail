# API stability

whytrail is pre-1.0: the public API may still change between minor
versions (`CHANGELOG.md`'s "Status" section has always said this). This
page makes that concrete instead of leaving it as a blanket disclaimer
-- what's actually stable in practice, what's still moving, and what
1.0 requires.

## What's stable in practice

- **The five verbs and two persistence helpers**: `why`, `track`,
  `tracked`, `trace`, `register`, `snapshot`, `restore`. Unchanged in
  shape since 0.1.0; `trace()`'s decorator form was removed pre-1.0
  (ADR 0002 §3), but the context-manager form and every other verb's
  signature has not changed since.
- **`Explanation`, `ExplanationStep`, `Confidence`**: the vocabulary
  every explainer author and plugin depends on. New *fields* have been
  added additively (`ExplanationStep.locals`, `Explanation.plain_text`,
  the `"suggestion"` key in `.json()`) -- nothing existing has been
  renamed or removed since 0.1.0.
- **The Explainer Protocol**, frozen at v1
  (`whytrail.registry.EXPLAINER_PROTOCOL_VERSION`), independent of
  whytrail's own package version. See `docs/plugin-guide.md`'s
  "Protocol version" section for exactly what v1 covers and what a v2
  would require.

## What's still moving

- **`ExplanationStep`'s field set.** Two fields have been added since
  0.1.0 (`locals`, and the suggestion machinery). A third addition is
  more likely than a removal, but isn't ruled out.
- **The set of names in `whytrail.__all__`.** Deliberately small
  (ADR 0002 §3) -- additions are more likely than removals, but a name
  moving from top-level to submodule-only (as `NodeKind`/`EdgeKind`/
  `ProvenanceGraph`/`TraceScope`/`SupportsWhy` already did once) isn't
  ruled out again if a similar review finds cause.
- **Everything under `whytrail.integrations.*`.** Each plugin's own
  internal helpers (the `_explain_*` functions, module-private
  constants) are not public API -- only `register()` existing and
  being importable is guaranteed. A plugin's *behavior* (what shows up
  in `.text`/`.json()`) can change as bugs are found, same as this
  project's whole floor-testing history already shows.

## Deprecation policy

No formal grace-period mechanism exists yet (no `DeprecationWarning`
infrastructure, no "deprecated in X, removed in Y" convention has been
needed so far -- every pre-1.0 API change to date has been a same-PR
removal, documented in `CHANGELOG.md`, not a phased deprecation). Until
1.0, treat any change documented in `CHANGELOG.md` as authoritative;
this page describes intent, not a contract.

## What 1.0 actually requires

No ADR currently states a checkable, specific bar for cutting 1.0 --
worth naming plainly rather than pointing at a citation that doesn't
hold up (`CHANGELOG.md`'s 0.1.0 entry references "the packaging policy
in the ADR" reserving 1.0 for after real-world plugin ecosystem
validation, but no ADR in `docs/adr/` actually states that criterion in
checkable terms). Whatever the real bar for 1.0 is, if the informal
one was ever "more than a couple of real plugins, proven against real
objects" -- that's now true 41 times over (see `docs/plugin-guide.md`).
That doesn't mean 1.0 should be cut immediately; it means the question
of what 1.0 actually requires is open and worth a real decision, not
assumed settled by an old, unverifiable citation.
