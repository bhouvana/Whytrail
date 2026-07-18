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

**Two more real candidates, confirmed missing (0.3), then explicitly
requested and shipped in the same version**: a stdlib `logging`/
`structlog`/`loguru` integration (checked by grep, none of the three
existed under `integrations/` at the time) and Jupyter/IPython display
hooks (`_repr_html_` -- confirmed absent, also since added). Both
surfaced auditing a "Phase I -- Production-Grade Integrations"
proposal that otherwise turned out to be already-shipped for
pytest/FastAPI/Rich (see `CHANGELOG.md`). The ecosystem count moved
from 60 to 63 as a direct, explicit instruction, not a speculative
reopening of "keep growing the ecosystem" above -- that question
(whether to keep pushing past 60 by default) stays open and unrelated.

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

**`whytrail.install()` shipped (0.3) as the project's flagship
feature** -- see ADR 0009 for the full "ten candidates, nine rejected"
reasoning. `sys.excepthook`/`threading.excepthook` replacement, zero
new engine work, README's opening section now built around it. This
isn't a Phase E item in the "small, incremental polish" sense the rest
of this phase means -- named here because it's the same kind of
evidence-gated decision (built on the existing engine, not a new
subsystem; two real technical gaps confirmed by testing, not assumed)
this whole roadmap holds everything else to.

- **CLI discoverability**: confirm `whytrail run --help` output is
  actually good (it's existed since 0.1.0's v2.0 slice but hasn't been
  reviewed since). Low cost, real value, no speculation required.
  **Found something real doing this** (0.3): `--json`/`--graph` placed
  after the script path -- the order most users would guess, and the
  order this project's own README implied -- were silently swallowed
  by `script_args`' `argparse.REMAINDER` with no error at all. Fixed
  with a stderr warning (not silent flag reinterpretation, since a
  script might genuinely want a literal `--json` argument of its own);
  `README.md` now shows the verified-working order.
- **`whytrail-pytest` now surfaces `track()`ed values, not just the
  bare exception** (0.3): Tier 1, which the plugin's failure-report
  section was built from entirely, never consults the provenance
  graph (ADR 0008 invariant 4) -- so a value that failed an assertion
  and was also `track()`ed only ever explained "AssertionError here,"
  never its own derivation. Fixed with a small addition to the
  existing hook, not a new plugin; see `CHANGELOG.md` for the
  before/after.
- **Error-message quality for whytrail's own failures** (e.g. what
  happens if `why()` is called on something genuinely unparseable, or
  a plugin's `register()` itself raises) -- dogfooding whytrail's own
  standard against itself.
- Everything else DX-shaped (a web playground, richer terminal
  rendering beyond `.rich()`, an interactive REPL mode) stays
  unscheduled until real usage exists to point at a specific friction
  point, not "developers probably want X."
- **`whytrail.config`** (ADR 0007) shipped since: `env()`/`load_dotenv()`
  give config-value resolution the same provenance `track()` gives any
  other value, without inventing a new capture mechanism. Not
  speculative -- built directly on `NodeKind.EXTERNAL`/`IMPORT`, the
  same primitives `propagation.py` already used.
- **A product/adoption audit (not a code audit)** against the real
  repo state -- README, docs, CLI, examples, benchmarks, visual
  identity, contributor experience, trust signals -- each finding
  checked against the actual files, not asserted. Six items shipped
  from it, all polish/DX, none touching the engine or adding a public
  verb:
  - README: PyPI/CI/license badges, real quoted benchmark numbers
    (previously asserted, never shown), a real rendered `.graph()`
    Mermaid diagram, and a `## Performance` section.
  - **A real bug this work found and fixed**: `registry.py` imported
    `importlib.metadata` eagerly at module load though it's only
    needed the first time an entry-point plugin is resolved -- ~30ms
    of every `import whytrail` for a path most processes never hit.
    Made lazy; confirmed with `-X importtime` before/after, not
    estimated.
  - `examples/ex_fastapi.py`, `ex_flask.py`, `ex_django.py`,
    `ex_pytest_fixtures.py` -- real, executed integration examples;
    previously only 2 generic examples existed despite 60 integrations.
  - `SECURITY.md` -- names the three genuinely security-sensitive
    areas of this codebase directly (locals capture/redaction, the web
    framework integrations' two-opt-in response safety, the graph
    never holding a strong reference) rather than a template with no
    project-specific content.
  - `whytrail plugins` CLI subcommand -- runtime introspection of the
    ecosystem (`registry.list_builtin_plugins()`/
    `list_hook_based_plugins()`/`list_entry_point_plugins()`), the
    second subcommand ever added, held to the same "demonstrated need"
    bar the CLI's own module docstring sets for a third. Four more
    followed in the same 0.3 (`inspect`/`explain`/`diff`/`doctor`,
    explicitly requested rather than independently justified against
    that bar one at a time) -- see `CHANGELOG.md` for what each does
    and the real bugs found building `diff`/`inspect`.
  - `docs/quickstart.md` -- a real onboarding path distinct from the
    README; every command and output block in it was executed against
    this codebase, not written to look plausible.
  - **Caught during this same work, not after**: while verifying the
    fix above, `_load_builtin_explainers()`'s own `except Exception`
    was found to be silently swallowing a `NameError` the fix itself
    introduced (a bare `importlib.import_module` call with no runtime
    `import importlib` left at module scope) -- every one of the 43
    built-in explainer plugins had silently stopped registering.
    Caught by running `tests/plugin_contract/` for real, not by
    excluding it and trusting the smaller suite. Fixed in the same
    pass; see `CHANGELOG.md` for the full sequence.

## Phase F -- Advanced provenance (not started, deliberately)

Deeper Tier-2 capabilities: richer `ProvenanceGraph` queries (e.g.
"all values derived from this input" rather than just "why does this
value exist"), multi-process graph merging (explicitly out of scope
per ADR 0001 as "real distributed-tracing infrastructure," revisit
only if that judgment changes). Highest complexity, highest risk of
scope creep, and Tier 1 correctness -- not Tier 2 sophistication -- is
still the trust asset actually being sold. Stays last of the "core
library" phases; the phases after this point are about the project
around the library, not the library's own feature surface.

**The same "all values derived from this input" query was proposed a
second time** (a "Phase U" review, framed as "branching"/"what does
this value affect") and re-affirmed as not-started here rather than
built -- see `docs/adr/0011-provenance-vocabulary-is-already-sufficient.md`.
That same review's other candidates (transformation sequences,
merge/override semantics, multi-parent composition) turned out to
already work with existing primitives, verified against real code, and
needed no new engine surface at all -- only this one, the forward
query, was a genuine gap.

**Built shortly after, once revisited (ADR 0012)**: `ProvenanceGraph.descendants()`,
a structural mirror of `ancestors()` over the already-existing
`_edges_by_source` index -- confirmed to be pure traversal, no new
`NodeKind`/`EdgeKind`, once a concrete consumer showed up (cleanly
demonstrating one value affecting several independent downstream
consumers, the same branching example both reviews used). This phase's
broader "richer queries" scope stays open for anything beyond this one
symmetric case -- this closes the one specific, named item above, not
Phase F as a whole.

**`@tracked` on `async def`, generator, and async generator functions
was a real bug, not a Phase F item, and is now fixed** (0.3): calling
one of these returns a coroutine/generator object immediately, so the
old wrapper (written with only plain functions in mind) tracked that
object itself, never the eventual result or yielded values, and its
exception-linking branch was dead code for all three cases. Fixed with
three additional wrapper variants chosen once at decoration time via
`inspect.iscoroutinefunction`/`isgeneratorfunction`/
`isasyncgenfunction`. Deliberately scoped: `.send()`/`.throw()` are
not forwarded into a wrapped generator (recorded as the call's own
outcome instead, documented in `tracked()`'s docstring) -- full
bidirectional-generator protocol fidelity is a materially bigger,
separate undertaking with no evidence anyone needs it from `@tracked`
specifically. What's still genuinely Phase F, not done by any of these
fixes: whether `trace(deep=True)`'s `sys.monitoring`-based
auto-instrumentation correctly follows execution across `await`
suspension points the same way it follows synchronous calls -- a
bigger, separate question about the deep-tracing mode specifically,
not about `@tracked`'s explicit opt-in.

**Also named, cosmetic, not fixed**: an unconsumed, infinite
`@tracked` generator left open until interpreter shutdown can print an
"Exception ignored" message (`weakref.finalize` failing because
`sys.meta_path` is already torn down at that point) -- confirmed
shutdown-specific; explicit `.close()` during normal execution is
unaffected, and no program behavior is changed by it. Fixing it well
means broadening `core/graph.py`'s exception handling for an
output-only edge case -- not done without more reason to believe it
matters in practice.

**Also named here, not started, lower priority than the above**:
- Element-level provenance for nested containers (`row["price"]` after
  `track(row)` has no node of its own) -- real (the README's own
  flagship example destructures a dict this way) but genuinely hard
  without re-approaching the transparent-proxy idea ADR 0001 already
  rejected. Would need a narrow, explicit helper, not automatic
  tracking.
- Snapshot diffing ("what changed between two captures") -- more
  natural now that `core/serialize.py` has format versioning (0.3),
  but needs a real design pass on diff semantics first.
- Source-code line context in `ExplanationStep` (today: `file:line, in
  func`, never the actual source line) -- cheap via stdlib
  `linecache`, real DX value, not started because nothing this session
  ranked it above the items that did ship.

ADR 0007 named this the home for any real extension of the general
explanation-engine model behind `why()` (config resolution, retry
provenance, and similar non-exception chains an external review
proposed) -- gated on the same "a real consumer shows up" trigger as
before, not moved up or expanded in scope by that ADR. ADR 0008 then
audited the engine itself (found it already generic, fixed one real
bug in `whytrail.config`, documented six invariants) and wrote
[`docs/explanation-engine.md`](../docs/explanation-engine.md) as the
guide a real extension here should be checked against. Neither ADR
moves this phase's status -- still "not started, deliberately."

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
- **Real numbers now exist** (0.3): `README.md`'s `## Performance`
  section quotes actual `pytest benchmarks/ --benchmark-only` and
  `-X importtime` output rather than an unquoted assertion, and a real
  ~30ms eager-import cost in `registry.py` was found and cut this way.
  Doesn't close this phase -- there's still no CI regression gate --
  but the baseline-gathering step above is partly done.
- `core/graph.py`'s `_evict_if_needed()` uses naive FIFO eviction
  (oldest node dropped first) at `DEFAULT_MAX_NODES = 10_000`, not
  LRU. Real technical debt, named directly, but zero evidence anyone
  has hit the ceiling in practice -- not scheduled ahead of that
  evidence, same standard as everything else in this document.
  **A related, real bug found and fixed (0.3), evidence this time
  gathered directly**: a 50,000-object soak test found eviction never
  cleaned up `_object_to_node`/`_finalizers`, so either dict grew
  unboundedly whenever an evicted node's object was still alive --
  `_nodes` itself was correctly bounded the whole time, the FIFO-vs-LRU
  question above is unaffected. See `CHANGELOG.md`.
- **A real regression gate now exists (0.3)**, closing the "premature
  today" note above: `ci.yml`'s `benchmarks` job compares each run
  against cached history on the same OS/Python combination
  (`pytest-benchmark --benchmark-compare-fail=min:400%`), not a fixed
  microsecond threshold -- confirmed directly that GitHub-hosted
  runner variance alone would make a hard absolute number flaky. See
  `CHANGELOG.md` for why no baseline was committed to the repo.

## Phase H -- Cross-platform & version breadth

Named gaps, not new discoveries: `docs/testing-maturity.md` already
states the version-matrix only covers Python 3.13, not the full
3.10-3.13 floor range each plugin claims to support, and concurrency
testing only covers three web frameworks. Closing this is mechanical
(extend `ci.yml`'s matrix) but not free -- every additional Python
version roughly multiplies plugin-version-matrix's job count, so this
should land deliberately, not accidentally via scope creep on an
unrelated PR.

**Both gaps addressed directly (0.3), on explicit request rather than
by default.** A `plugin-version-matrix-py-range` job checks every
extra's `pyproject.toml`-stated floor (not the 3.13-corrected floor the
existing job pins) against Python 3.10/3.11/3.12 -- 186 jobs, gated to
the same weekly `schedule` trigger `plugin-version-matrix` already
runs on, for exactly the cost reason named above (every push shouldn't
pay for a check whose answer rarely changes). Concurrency coverage
extended to Celery, dramatiq, RQ, Sentry, ddtrace, and OTel
(`test_task_queue_concurrency.py`, `test_observability_concurrency.py`),
using the same "N concurrent calls, unique secret each, assert no
cross-contamination" pattern already proven for the three web
frameworks. Prefect deliberately excluded (no locals-bearing state to
test, per its own module docstring); RQ's real forking `Worker` still
isn't exercised, only whytrail's own installed handler called
concurrently (see `docs/testing-maturity.md` gap #3/#5 for the full
reasoning on both). Doesn't close this phase outright -- the new
version-matrix job hasn't actually executed on real CI yet as of this
writing, so "the check exists" and "3.10-3.12 are confirmed working"
are still two different claims, per this project's own standing rule
about not asserting more than verified.

## Phase I -- Security & supply-chain hardening

- **Dependency scanning**: no Dependabot/Renovate config exists yet
  for the growing extras list. Worth adding once the 60-plugin push
  settles, so it isn't fighting churn from constant new extras.
- **Extend property-based redaction fuzzing** (`test_redaction_fuzz.py`)
  beyond the current 9 plugins to the rest of the ecosystem -- every
  new plugin should arguably get this from day one going forward
  rather than added retroactively in a batch.
  **Widened (0.3): 11 targets to 22** (`anthropic`, `psycopg`, `pymysql`,
  `pymssql`, `clickhouse`, `snowflake`, `influxdb`, `graphql-core`,
  `google-genai`, `requests`, `httpx`), checked against each plugin's
  own source first rather than assumed -- `boto3`, `aiohttp`, and
  `marshmallow` turned out to have no redaction-critical field at all
  (each plugin's own docstring says so directly), and `oracledb` is
  excluded for the same reason `grpcio`/Prefect already were (its
  exception can only be constructed via a real per-example connection
  attempt). Two real bugs found building this batch, both in the new
  tests themselves rather than in whytrail: a `requests.Response.text`
  charset-detection mismatch, and an `except ... as exc` scoping bug.
  Remaining ecosystem still uncovered by this mechanism; extending
  further stays open.
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
met yet. What's missing regardless of that trigger: issue/PR templates,
and Phase D's sunset-policy gap belongs here -- deciding what happens
to a plugin whose upstream library goes dead is a governance decision,
not a testing one. Do this when a second contributor's PR actually
arrives, not speculatively for a contributor who doesn't exist yet.

**`CONTRIBUTING.md` added anyway (0.3), ahead of that trigger, on
explicit request** -- scoped narrowly to what's actually true today
rather than invented process: the "write the regression test before
the fix" rule this project already followed for every real bug in
`CHANGELOG.md`, written down explicitly for the first time, plus
pointers to the existing plugin-guide/ADR conventions. Says directly
that it's not a complete governance process and that the real trigger
for one (a second maintainer) hasn't fired.

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

**A first real pre-1.0 consistency pass happened anyway** (0.3): asked
to review every public API/integration/CLI command as though changing
it later would be expensive, and found three real naming
inconsistencies introduced this same session (`redact`/`log_locals`
polarity mismatch across the logging integrations; `"hook"`/
`"integration"` terminology mismatch between `registry.PluginStatus.kind`
and the vocabulary `docs/plugin-guide.md` already established;
`SnapshotVersionError` living two levels deeper than `ConfigError`
relative to the top-level functions each one belongs to) -- all three
fixed, see `CHANGELOG.md`. Doesn't answer Phase Q's actual question
(what 1.0 requires); it's evidence that the codebase can survive this
kind of audit without a major rewrite, not a substitute for the real
decision.

## How to use this document

Phases C, E, G, and H have concrete next actions and should absorb most
near-term work. Phases K, L, N, O, and P are intentionally decisions
deferred to a real trigger (a second contributor, real user feedback, a
specific request) rather than work items -- revisit them when that
trigger fires, not on a schedule. This document should be updated
alongside `CHANGELOG.md` as phases complete, the same discipline
`docs/testing-maturity.md` already follows.
