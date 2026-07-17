# Roadmap: Phase A through Q

This is the long-range plan behind whytrail's day-to-day work, written
so "what's next and why" doesn't have to be re-derived from git history
each session. Phases are lettered for reference, not dated -- some run
in parallel, some are genuinely sequential, and several past F are
**decisions to make, not code to ship**, which this document says
plainly rather than padding out with speculative work to look complete.
That distinction matters: this project's whole engineering culture
(ADR 0003's plugin triage, the "never fabricate" rule that gives
whytrail its name) is built on not claiming more than is actually true.
Treat the same standard as applying to this roadmap.

## Status at a glance

| Phase | Name | Status |
|---|---|---|
| A | Release discipline & doc sync | Done |
| B | API stability policy | Done |
| C | Plugin ecosystem to 60 | **Done (60/60)** |
| D | Plugin health policy | Done (detection); no sunset policy yet |
| E | Developer experience polish | Starting now, scoped narrowly |
| F | Advanced provenance | Not started, deliberately last of the "core" phases |
| G | Performance & benchmarking rigor | Planned below |
| H | Cross-platform & version breadth | Planned below |
| I | Security & supply chain hardening | Planned below |
| J | Telemetry & propagation maturity | Planned below |
| K | Governance & contribution process | Planned below |
| L | Editor/IDE integration | Planned below (ADR 0005 already said "not yet") |
| M | Framework-specific deep integrations | Planned below |
| N | Internationalization of output | Planned below |
| O | Team/organization features | Planned below, lowest confidence |
| P | Maintainer succession & bus factor | Planned below |
| Q | 1.0 and long-term support policy | Planned below, the actual finish line |

## Phase A -- Release discipline & doc sync (done)

Cut 0.2.1's changelog properly (a `[0.2.0]` heading had never existed,
despite 0.2.0 already being on PyPI), fixed `docs/testing-maturity.md`'s
stale aggregate counts, added a docs-sync reminder to the plugin
checklist. See `CHANGELOG.md`.

## Phase B -- API stability policy (done)

`docs/api-stability.md`: what's actually stable in practice (the five
verbs, `Explanation`/`ExplanationStep`/`Confidence`, the frozen
Explainer Protocol v1) versus what's still moving, plus an honest note
that no ADR states a checkable 1.0 bar today. Phase Q below picks that
question back up for real.

## Phase C -- Plugin ecosystem to 60 (done: 60/60)

Batches 2b through 6 shipped (`pika`, `kubernetes`, `azure-core`,
`elasticsearch`, `sendgrid`, `websockets`, `opensearch`, `pyodbc`,
`google-genai`, `oracledb`, `confluent-kafka`, `pymysql`, `pymssql`,
`clickhouse`, `snowflake`, `graphql-core`, `tenacity`, `newrelic`,
`rollbar`, `honeybadger`, `psycopg`, `cassandra`, `influxdb`, `pyzmq`,
`zeep`, `elastic-apm`, `bugsnag`), each checked against a real object
per ADR 0003's bar before any code was written, several rejected with
reasons (`kafka-python`, `tomllib`, `fastavro`, `paho-mqtt`, `duckdb`,
`pymemcache`, `pysolr`). Full detail per batch in `CHANGELOG.md`.

**60/60 doesn't mean stop, it means the target this push was scoped
against is met.** Whether to keep growing the ecosystem further, and
against what criteria, is exactly the open question Phase Q already
names for 1.0 -- more plugins is not automatically more valuable past
this point, and ADR 0003's own reasoning (a genuine plugin need in
roughly a tenth to a fifth of what gets surveyed, not "wrap everything")
argues against treating 60 as a floor to keep pushing past by default.
Five candidates researched during this push (`falcon`, `authlib`,
`gql`, `cohere`, `twilio`) were dispatched to background research
before the no-subagents correction landed this session and never
reported back in-session -- worth checking for stray output before
assuming they're still open, not re-researching from scratch.

## Phase D -- Plugin health policy (detection done, policy gap open)

`ci.yml` gained a weekly `schedule:` trigger so a floor break from a
new upstream release doesn't wait for an unrelated push to surface.
What's still missing, named plainly in `docs/testing-maturity.md`'s
gap #7: no policy for what happens when a plugin's upstream goes
stale and nobody's actively maintaining that integration. That's a
governance question (Phase K), not a testing one -- deliberately not
answered here by inventing a process nobody's agreed to yet.

## Phase E -- Developer experience polish (starting now)

Scoped narrowly on purpose: real DX work should follow real usage
friction, and whytrail has no external users yet to generate that
signal (memory: "no evidence exists" was the honest state as of the
last review). What's actionable *without* fabricating user feedback:

- **CLI discoverability**: confirm `whytrail run --help` output is
  actually good (it's existed since 0.1.0's v2.0 slice but hasn't been
  reviewed since). Low cost, real value, no speculation required.
- **Error-message quality for whytrail's own failures** (e.g. what
  happens if `why()` is called on something genuinely unparseable, or
  a plugin's `register()` itself raises) -- dogfooding whytrail's own
  standard against itself.
- Everything else DX-shaped (a web playground, richer terminal
  rendering beyond `.rich()`, an interactive REPL mode) stays
  unscheduled until real usage exists to point at a specific friction
  point, not "developers probably want X."

## Phase F -- Advanced provenance (not started, deliberately)

Deeper Tier-2 capabilities: async-aware tracing across `await`
boundaries, richer `ProvenanceGraph` queries (e.g. "all values derived
from this input" rather than just "why does this value exist"),
multi-process graph merging (explicitly out of scope per ADR 0001 as
"real distributed-tracing infrastructure," revisit only if that
judgment changes). Highest complexity, highest risk of scope creep,
and Tier 1 correctness -- not Tier 2 sophistication -- is still the
trust asset actually being sold. Stays last of the "core library"
phases; the phases after this point are about the project around the
library, not the library's own feature surface.

## Phase G -- Performance & benchmarking rigor

`benchmarks/` and a CI `benchmarks` job already exist, explicitly
labeled "informational, not a merge gate yet." Making that real:

- Turn informational benchmarks into an actual regression gate (fail
  CI if `track()`/`why()` overhead regresses beyond a threshold),
  once a baseline exists stable enough to set a sane threshold against
  -- premature today, the baseline itself needs a few real runs first.
- Profile the two hot paths that matter for a debugging library used
  in production: `track()`'s per-call overhead when tracing is
  *disabled* (should be near-zero -- that's the whole "zero overhead
  when unused" promise) and `why()`'s cost on a deep/wide provenance
  graph.
- No work starts here until Phase G's baseline-gathering step
  actually runs; listed now so the intent isn't lost.

## Phase H -- Cross-platform & version breadth

Named gaps, not new discoveries: `docs/testing-maturity.md` already
states the version-matrix only covers Python 3.13, not the full
3.10-3.13 floor range each plugin claims to support, and concurrency
testing only covers three web frameworks. Closing this is mechanical
(extend `ci.yml`'s matrix) but not free -- every additional Python
version roughly multiplies plugin-version-matrix's job count, so this
should land deliberately, not accidentally via scope creep on an
unrelated PR.

## Phase I -- Security & supply-chain hardening

- **Dependency scanning**: no Dependabot/Renovate config exists yet
  for the growing extras list. Worth adding once the 60-plugin push
  settles, so it isn't fighting churn from constant new extras.
- **Extend property-based redaction fuzzing** (`test_redaction_fuzz.py`)
  beyond the current 9 plugins to the rest of the ecosystem -- every
  new plugin should arguably get this from day one going forward
  rather than added retroactively in a batch.
- **SBOM / provenance attestation** for the PyPI release itself
  (trusted publishing already removes the stored-token risk; an SBOM
  is the next incremental step, not urgent pre-1.0).

## Phase J -- Telemetry & propagation maturity

whytrail already has `whytrail.otel` (span events) and
`whytrail.propagation` (cross-process context carrying, no transport)
-- deliberately not "add observability as a new feature," since that
already exists and a prior review already rejected inventing more of
it without a named gap. The real open item: verify `propagation`'s
`inject()`/`extract()` round-trip against a real second process, not
just unit-level -- it's never been exercised end-to-end.

## Phase K -- Governance & contribution process

ADR 0006 already names the trigger for a real core/contrib split:
"a second maintainer and a real plugin backlog." Neither condition is
met yet. What's missing regardless of that trigger: no
`CONTRIBUTING.md`, no issue/PR templates, and Phase D's sunset-policy
gap belongs here -- deciding what happens to a plugin whose upstream
library goes dead is a governance decision, not a testing one. Do this
when a second contributor's PR actually arrives, not speculatively for
a contributor who doesn't exist yet.

## Phase L -- Editor/IDE integration

ADR 0005 already assessed a VS Code extension and concluded "not now
-- building an editor extension for a library with zero published
releases inverts the adoption funnel it's meant to serve." That
reasoning hasn't changed; whytrail now has real releases (0.1.0, 0.2.0)
but still no evidence of real adoption to invert the funnel against.
Revisit if that changes, not before.

## Phase M -- Framework-specific deep integrations

Named candidates already in the backlog: a Django ORM-specific
enhancement (beyond the existing safety-boundary `django.py` plugin),
deeper pytest failure-report detail. Lower priority than Phase C's
raw plugin count, since these are *enhancements* to already-shipped
integrations, not new coverage -- matters more once the 60-plugin
push settles and there's less "un-covered library" surface left to
prioritize against.

## Phase N -- Internationalization of output

`Explanation.plain_text` (English only) is the only prose-rendering
surface that would need this. No signal yet that non-English output
is a real request rather than a plausible-sounding feature -- listed
for completeness, not scheduled. The honest version of this phase is
"wait for someone to ask."

## Phase O -- Team/organization features

Lowest-confidence phase on this list, worth saying directly: shared
redaction-policy config, org-wide default settings, anything
"enterprise"-shaped. An earlier architectural review already pushed
back on manufacturing an "Enterprise Adoption" phase with no signal
behind it, and that reasoning still holds -- individual-developer
trust (the httpx/Rich adoption pattern) comes before any team-feature
motion for a library at this stage, not after. Listed here only
because the instruction was to plan through Q, not because there's a
real case for building it soon.

## Phase P -- Maintainer succession & bus factor

Currently a single-maintainer project. Worth naming as a real risk
without pretending there's an action to take about it yet beyond what
Phase K already covers (documentation quality, ADRs, CI discipline --
all of which lower the cost of a second maintainer joining later, which
is the actual mitigation available right now).

## Phase Q -- 1.0 and long-term support policy

The real finish line this roadmap is building toward. `docs/api-stability.md`
already found that no ADR states a checkable 1.0 bar, and that the one
often-cited criterion ("real-world plugin ecosystem validation... two-to-three
plugins") is now cleared 44 times over by raw count, whatever the real bar
turns out to be. This phase is a decision, not an implementation task:
once Phases C through E reach a natural resting point, revisit what 1.0
actually requires and write it down as a real ADR -- not before, and not
by unilaterally deciding it from inside a roadmap document.

## How to use this document

Phases C, E, G, and H have concrete next actions and should absorb most
near-term work. Phases K, L, N, O, and P are intentionally decisions
deferred to a real trigger (a second contributor, real user feedback, a
specific request) rather than work items -- revisit them when that
trigger fires, not on a schedule. This document should be updated
alongside `CHANGELOG.md` as phases complete, the same discipline
`docs/testing-maturity.md` already follows.
