# ADR 0010: Positioning refinement -- "why," not "where," and why `.share()`/`.coach()`/`.timeline()` were declined

## Status

Accepted and implemented: `README.md`'s tagline and structure,
`pyproject.toml`'s `description`, `mkdocs.yml`'s `site_description`.
No code changes -- this is a documentation/positioning decision, the
same category ADR 0002 already made once.

## Context

ADR 0002 ("Category strategy") already did this exercise once and
landed on **provenance** as the category word and *"I use whytrail to
find out where a value came from"* as the elevator sentence. A later
review (following the shipped `whytrail demo` command, ADR 0009's
flagship feature, and `whytrail.config`'s second-consumer proof) asked
the same question again, sharper: given only what's *actually shipped*
today (`why()`, Tier 2 tracked provenance, `whytrail.config`,
snapshots, `Explanation`, `install()`, the integrations), what single
sentence describes whytrail such that it would still be true if every
mention of "exceptions" disappeared from the project? Twenty candidate
sentences were generated and critiqued for truthfulness, specificity,
uniqueness, credibility, and immediate understandability; the
strongest three:

1. "Whytrail answers 'why does this value have this value,' not just
   'where did this happen' -- for any value you choose to track."
2. "Whytrail is provenance-first debugging: explicit capture, honest
   confidence, and it never fabricates an answer it isn't sure of."
3. "Whytrail lets you ask 'why' about a value the same way Python's
   own traceback already lets you ask 'where' about an exception."

## Decision: refine ADR 0002's sentence, don't replace the category

**"Where a value came from" undersells the actual capability** --
"where" is exactly the question a traceback, `pdb`, and a log line
already answer for free, and using that word as the headline claim
puts whytrail in competition with tools it isn't competing with on
their own terms. The refinement isn't a new category (still
*provenance*, still the same W3C-PROV-adjacent granularity ADR 0002
already placed it at) -- it's sharper language for the same idea: the
distinguishing question is causal derivation of a specific value
("why does this have this value"), not just lineage/origin ("where did
this come from"). All three finalist sentences above are checkable
against real, shipped behavior (`why()`'s actual output, the
`Confidence` enum, ADR §11's "never fabricate" guarantee, tested
directly in `tests/unit/test_negative_inputs.py`) -- none broaden the
claim beyond what a reader can verify by running `whytrail demo`.

**Applied in `README.md`:** the tagline now reads *"Python tells you
*where* something happened. `whytrail` tells you *why a value has the
value it has.*"* -- keeping the original tagline's recognizable
where/why cadence (nothing here contradicts ADR 0002's instinct that
this contrast is the right axis) while making the claim specific enough
to be falsifiable. Sentence 3 (the traceback analogy) follows
immediately as the concrete anchor a Python engineer already trusts.
Sentence 2 (explicit/honest/never-fabricates) is placed where the
"never fabricate" guarantee is already discussed, summarizing the three
properties in one line rather than requiring a reader to infer them
from separate paragraphs. `pyproject.toml`'s `description` and
`mkdocs.yml`'s `site_description` (previously identical to the old
tagline) are updated to match.

## Decision: `.share()`, `.coach()`, `.timeline()` declined, not built

Proposed alongside the positioning question, evaluated against it
directly:

- **`.share()`** (generate a hosted `https://whytrail.app/r/...` link)
  -- this is a different product, not a library feature: a live web
  service (hosting, a database, uptime, a security surface, ongoing
  cost) for a solo-maintained, currently zero-required-dependency
  library. ADR 0002 already named the only coherent shape for anything
  hosted -- "a Sentry-shaped hosted aggregation layer... conditioned on
  the core library never making a network call on its own... multi-year
  outcome, not a 1.0 workstream" -- and nothing about this idea changes
  that conclusion.
- **`.coach()`** -- checked against the code before rejecting:
  `Explanation.plain_text` already renders a confidence-labeled gloss
  plus a "How to avoid this" line per exception type
  (`_EXCEPTION_GLOSS`/`_EXCEPTION_FIXES`, shipped 0.2.1). A new
  `.coach()` method would mostly restyle output that already exists
  under a new name. `whytrail/__init__.py`'s own "five verbs,
  deliberately small" comment (held since ADR 0001, broken exactly once
  so far for `install()`/`uninstall()`, reasoned through in ADR 0009
  each time) is the bar a genuinely new verb has to clear -- not
  cleared here without a concrete gap `.plain_text()` doesn't already
  close.
- **`.timeline()`** -- more grounded than `.coach()` (`Node.timestamp`
  already captures wall-clock time per step, so the underlying data
  exists), but still a new top-level method decision against the same
  "five verbs" bar. Not built speculatively; a real candidate later if
  a specific gap in `.graph()`/`.rich()` surfaces that per-step timing
  would actually close, gated the same way `install()` was: real
  candidates generated, critiqued, and only the strongest one built.

## Consequences

- The elevator sentence changes; the category word (provenance) and
  the underlying architecture do not. Nothing in `docs/adr/0001` through
  `0009` is invalidated by this ADR -- it sharpens language ADR 0002
  chose, using evidence (`whytrail.config`, `install()`, `whytrail demo`)
  that didn't exist when ADR 0002 was written.
- `.share()`/`.coach()`/`.timeline()` are recorded as evaluated and
  declined, not merely unmentioned -- if raised again, this ADR is the
  answer, the same way ADR 0005 is the standing answer for a VS Code
  extension.
