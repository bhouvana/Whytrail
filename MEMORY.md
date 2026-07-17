# whytrail -- project memory / handoff

Status snapshot as of 2026-07-17. Read this first in a new conversation
instead of re-deriving context from git history and old chat logs.

## What this project is

`whytrail`: Python tells you *where* an exception happened; whytrail
tells you *why*. Two tiers:

- **Tier 1** (zero config): `why(some_exception)` reconstructs a causal
  chain from `__traceback__` / `__cause__` / `__context__` / frame
  locals -- no setup.
- **Tier 2** (opt-in): `why(some_tracked_value)` walks a provenance
  graph built only for values explicitly wrapped with `track()` /
  `@tracked` inside a `trace()` scope.

Hard rule baked into the design (ADR 0001, ADR 0002 §3.5): never
fabricate a causal chain it isn't sure about. An untracked value gets
an honest "unknown" answer, not a guess.

## Where it lives

- GitHub: https://github.com/bhouvana/Whytrail.git (branch `main`)
- PyPI: `pip install whytrail` (trusted publishing via
  `pypa/gh-action-pypi-publish`, no stored token) -- 0.1.0 and 0.2.0
  both shipped
- Docs site: https://bhouvana.github.io/Whytrail/ (GitHub Pages)
- Current version in `pyproject.toml`: **0.2.1** (bumped from 0.2.0
  mid-session by the same background documentation-consistency process
  noted below; `CHANGELOG.md`'s `[0.2.1]` heading consolidates
  everything since 0.2.0 -- plain_text/fix-suggestions, ExceptionGroup,
  and every plugin batch so far. Not yet actually published to PyPI as
  of this writing -- check PyPI before assuming it's live.)

## What's been achieved, in order

1. **Publish-readiness pass**: fixed GitHub Pages deployment (a
   toggle-off/toggle-on UI quirk), set up PyPI trusted publishing,
   wrote the GitHub About description, iterated on then fully removed
   a README banner image (PyPI's README renderer doesn't resolve
   GitHub-relative image paths -- lesson: keep README images either
   absolute URLs or none).
2. **Verified the real published package** end-to-end: `pip install
   whytrail` from PyPI, run against a real sample bug, confirmed the
   output matches what's documented.
3. **ADR 0006 -- unify the plugin ecosystem**: originally 30 separate
   `whytrail-X` PyPI packages. At the user's explicit direction ("we
   can't keep creating new pypi releases"), all 30 were folded into
   `whytrail` itself as optional extras (`pip install whytrail[stripe]`
   etc.), living under `src/whytrail/integrations/`. One release
   process, one version number, for everything. The old
   `whytrail.explainers` entry-point mechanism is kept, unremoved, for
   *external* third-party plugin authors -- it's just no longer how the
   bundled set works.
4. **0.2.1-in-progress feature work**:
   - `Explanation.plain_text` -- a ChatGPT-style plain-English
     rendering of the *same* structural facts `.text` already has, not
     an LLM call and not new information (explicitly chosen over an
     actual-LLM approach to avoid hallucination risk -- see the
     AskUserQuestion answer "Plainer English, same facts").
   - Per-exception-type fix suggestions (`"How to avoid this: ..."` /
     `.json()`'s `"suggestion"` field) -- general well-established
     guidance, not a diagnosis of the specific failure.
   - Fixed `why()` being blind to `ExceptionGroup`/`BaseExceptionGroup`
     sub-exceptions (PEP 654, Python 3.11+) -- now recursively expands
     `.exceptions`, capped at `MAX_GROUP_EXCEPTIONS = 5`.
5. **Growing the plugin count toward 60** (user's target, up from an
   original "aim for 100" that got talked down to a more honest
   "Rich/httpx-tier ambition, not numpy-tier" scope -- see ADR 0003).
   Batch 1 shipped: **stripe, alembic, paramiko** (30 -> 33 total).
   Each was checked against real library objects before writing any
   code; two candidates (**PyJWT**, **cryptography**) were deliberately
   *not* built as full plugins because direct inspection showed no
   structured fields beyond the exception's own message -- their value
   was captured instead as gloss/fix-table entries only.
6. **CI floor-testing discipline caught 3 real bugs in batch 1** (matching
   the ~1-bug-per-new-floor rate the original 30 integrations hit):
   - `stripe==7.0.0` -> floor moved to `8.0.0` (top-level
     `StripeError`/`CardError` didn't exist yet at 7.0.0).
   - `alembic==1.7.0` -> floor moved to `1.8.0` (transitive
     SQLAlchemy-version-drift `NameError` inside alembic's own code).
   - `paramiko==2.7.0` -> floor moved to `2.10.0` (paramiko's own
     package metadata at 2.7.0-2.9.0 doesn't declare `six` as a
     dependency even though `ed25519key.py` imports it directly -- a
     packaging bug in paramiko itself).
   All three fixed via real-Linux bisection (WSL2 + `uv`, not guessed),
   `ci.yml` updated with explanatory comments, `pyproject.toml`'s
   aspirational floors left untouched by convention (only the
   CI-*tested* floor moves). Commit `b78ceb2`, pushed; CI run
   `29579902029` completed with **conclusion: success** -- batch 1
   (stripe/alembic/paramiko) is fully done and verified green.
7. Also fixed in this session, unrelated to the above: two real bugs
   found before they ever reached a commit --
   - `whytrail-paramiko`'s first draft read `exc.got_key`; the actual
     stored attribute is `exc.key` (constructor param name != stored
     attribute name).
   - All three new integrations (stripe/alembic/paramiko) were
     initially unreachable: added as modules and `pyproject.toml`
     extras, but never added to `registry._BUILTIN_EXPLAINERS` (the
     actual discovery list) -- silently broken until
     `test_plugin_is_discovered()` caught it. **This is the single most
     important gotcha for adding any new plugin** -- see below.
8. **Batch 2 shipped: `elasticsearch`** (33 -> 34). `ApiError`/
   `NotFoundError`'s `.meta.status` + `.body`, verified via a real
   request/response round trip against a throwaway local HTTP server
   (no live Elasticsearch needed). `.body` fully redacted (an
   `error.reason` can echo a raw query fragment verbatim). Commit
   `b2db38c`; CI run `29580955949` completed with **conclusion:
   success**.
9. **Batch 2b shipped: `pika`, `kubernetes`, `azure-core`** (34 -> 37).
   A background research agent (`Agent` tool, real installs + real
   exceptions, not docs-reading) checked these plus `kafka-python`:
   - **`pika`**: `ChannelClosed`/`ConnectionClosed`'s `reply_code`/
     `reply_text` (AMQP broker reply). Both are `@property`s reading
     `self.args`, not `__dict__` entries -- `vars(exc)` alone would
     show nothing, use normal attribute access. The two classes are
     siblings under `AMQPError`, not one a subclass of the other, so
     both needed separate `register_from_plugin()` calls.
   - **`kubernetes`**: `ApiException`'s `.status`/`.reason`/`.body`.
     `.reason` is the *HTTP* reason phrase ("Not Found"), not the k8s
     `Status` object's own `reason` field ("NotFound", inside `.body`).
     Direct construction (`ApiException(status=, reason=)`) leaves
     `.body` as `None` -- confirmed this directly before writing the
     test, so the contract test uses a real local-HTTP-server round
     trip instead, the only way to get `.body` actually populated.
   - **`azure-core`**: `HttpResponseError`'s `.status_code`/`.reason`/
     `.error` (parsed `ODataV4Format`, `.error.code`/`.error.message`)
     -- shared base of every Azure SDK client (blob, identity, cosmos,
     etc.), so one registration covers all of them.
   - **`kafka-python` rejected**: checked directly against a live
     Kafka container -- `errno`/`message`/`description` are
     class-level constants from a static protocol-error-code table,
     not per-instance data, and no topic/partition/offset attribute
     exists on the exception itself. Same verdict as `redis-py`. Also
     confirmed via PyPI: `kafka-python-ng` is superseded, `kafka-python`
     itself resumed releases (now 3.0.8) -- target that name, not the
     fork.
   All three new floors are still **guesses** (`pika>=1.1`,
   `kubernetes>=18.20`, `azure-core>=1.24`), not yet bisected against
   real CI the way batch 1's were -- **do this next**.
   All 3 new integrations' tests passed on the first try locally (13
   new tests, 281 total; `mypy --strict` clean) -- no repeat of the
   `_BUILTIN_EXPLAINERS`-omission bug this time, the checklist below
   was followed exactly.
10. A background process has been actively and rapidly adding its own
    plugin batches in parallel throughout the session, independent of
    this conversation's own work (`ci.yml`, `pyproject.toml`,
    `CHANGELOG.md`, `docs/plugin-guide.md`, `registry.py` have all
    been edited by something other than direct action here -- treat
    concurrent file changes as intentional and build on them, don't
    revert). It bumped `pyproject.toml` to `0.2.1`, consolidated
    `CHANGELOG.md` under a `[0.2.1]` heading, and independently shipped
    its own "batch 3" (`sendgrid`, `websockets`, `opensearch`,
    `pyodbc` -- different libraries than this conversation's originally
    planned batch 3 of falcon/lxml/protobuf/authlib/tomllib, though it
    also researched and rejected `tomllib` using the same discipline).
    As of the last check it had also started an uncommitted, unverified
    "batch 4" (`google-genai`, `oracledb`, `confluent-kafka` -- files
    exist on disk but nothing is tested, committed, or wired into CI
    yet). **A new session should run `git status`/`git diff` and check
    the actual integration count in `pyproject.toml` before assuming
    any file or count matches what this memory file describes -- it
    moves fast.**
11. **Fixed batch-2b's azure-core floor** (found already fixed,
    identically, by the concurrent process when I went to push my own
    bisection -- `azure-core==1.24.0` imports the stdlib `cgi` module,
    removed in Python 3.13 (PEP 594); floor moved to `1.27.0`). `pika`
    and `kubernetes`' guessed floors both passed real CI on the first
    try -- no bug, breaking batch 1's 100% floor-bug-hit-rate streak.
12. **Fixed the concurrent process's batch-3 floors**: `sendgrid==6.0.0`
    imports PyYAML without declaring it as a dependency (floor moved to
    `6.1.0`, same category as paramiko's missing `six`); `pyodbc==4.0.0`
    has no Python 3.13 wheel anywhere in the 4.0.x/5.0.x/5.1.x line
    (floor moved to `5.2.0`, the first version with a cp313 wheel --
    confirmed the unixODBC *runtime* library itself is already present
    on `ubuntu-latest`, since that job's `latest` entry already passed).
    `websockets` and `opensearch`'s guessed floors both passed on the
    first try. Commit `c3157f1`, pushed; CI run `29583375691` not yet
    confirmed at time of writing -- **check that first in a new
    session**, and if a "batch 4" (google-genai/oracledb/confluent-kafka)
    has since been committed by the concurrent process, its floors will
    need the same real-CI verification treatment once they land.

## Established conventions (do not relitigate these)

- **New plugin checklist** (skipping any step has caused a real bug
  already):
  1. Inspect a real object from the real library first -- may
     downgrade a "plugin" candidate to gloss-table-only if there's no
     structured data beyond the exception's own message.
  2. Write the explainer under `src/whytrail/integrations/<name>.py`.
  3. Add the extra to `pyproject.toml` (`optional-dependencies`, and
     to the `all` meta-extra).
  4. **Add the name to `registry._BUILTIN_EXPLAINERS`** in
     `src/whytrail/registry.py` -- this is the actual discovery list;
     steps 2-3 alone are not enough. Forgetting this is the exact
     failure `test_plugin_is_discovered()` in every plugin's contract
     test exists to catch.
  5. Add contract tests under `tests/plugin_contract/`.
  6. Wire into `.github/workflows/ci.yml`'s two matrices:
     `plugin-contract-tests` (one entry) and `plugin-version-matrix`
     (two entries: floor + latest).
  7. Verify locally (`mypy`, `pytest`), push, then treat the stated
     floor as a *guess* until real CI confirms it -- expect roughly a
     1-in-3 chance of a real floor bug, and fix it via WSL2+`uv`
     bisection on real Linux, never by reasoning about version numbers
     abstractly.
- **`pyproject.toml` floors are never edited after a CI-floor
  correction** -- only `ci.yml`'s tested floor moves, with an
  explanatory comment matching the style already established for
  stripe/alembic/paramiko/etc. (see `ci.yml` around line 290 onward
  for the full worked-example log of every bug found this way).
- **Real Linux testing** happens via WSL2 + `uv`, not Docker (Docker
  Desktop isn't running in this sandbox): `git archive <ref> | wsl -d
  Ubuntu -e bash -c "cd ~/DIR && tar -x"`, then `uv venv --python
  VERSION PATH --clear`, `uv pip install --python PATH/bin/python -e
  ".[dev]"`, then pin/bisect specific dependency versions.
- **`git push` sometimes hangs** on Git Credential Manager
  re-authentication in this non-interactive sandbox -- just retry, it
  has succeeded on retry (1-2 attempts) every single time this
  session.
- **Redaction philosophy** (ADR 0002 §3 item 5): sensitive detail goes
  in `ExplanationStep.locals`, never `description`, so `.redacted()`
  can strip it before crossing a process boundary. Followed for
  stripe's `json_body`, paramiko's key fingerprints, etc.
- **Two fronts where technical pushback held, correctly, against user
  pressure** -- worth remembering the reasoning if it comes up again:
  - "Challenge numpy": category mismatch (numpy is a numerical
    computing library, whytrail is a debugging tool) -- reconfirmed
    "Rich/httpx-tier ecosystem ambition" as the honest target instead.
  - "Merge pip with npm/yarn to explain JS/TS/React errors from inside
    Python": live cross-process, cross-runtime introspection isn't
    possible -- process/runtime boundary is real. Offered a genuinely
    buildable alternative instead: a **separate npm/TS companion
    package sharing whytrail's JSON schema** (not built, not yet
    confirmed by the user as a roadmap item -- see Open Questions).

## Current numbers

Moving fast and partly out of this conversation's direct control (see
item 10 above) -- **verify against `pyproject.toml` directly, this
will already be stale**. Last confirmed count: 41 bundled integrations
(sendgrid/websockets/opensearch/pyodbc batch complete and floor-fixed;
a further google-genai/oracledb/confluent-kafka batch exists on disk
but is uncommitted and unverified as of the last check). 297+ tests.

## Pending / next steps

1. **Check whether the concurrent process's "batch 4"
   (google-genai/oracledb/confluent-kafka) has been committed.** If so,
   it needs the same treatment every prior batch got: confirm it
   actually followed the checklist above (real-object verification,
   `_BUILTIN_EXPLAINERS` registration, tests, CI wiring), run it
   locally, push if not already pushed, and treat its floors as
   guesses until real CI confirms them.
2. **This conversation's originally planned batch 3** (unresearched,
   still open, different from the concurrent process's own batch 3):
   `falcon`, `lxml`, `protobuf`, `authlib`. (`tomllib` was already
   researched and rejected by the concurrent process -- no per-instance
   structured data on `TOMLDecodeError`, same verdict independently
   reachable.)
3. **Batch 4 candidates** (unresearched): Django ORM enhancement,
   `gql`, `cohere`, `twilio`, `sendgrid`.
4. **Batch 5 candidates** (unresearched): `websockets`, `avro`,
   `opensearch`, `google-generativeai`, `pyodbc`/`oracledb`.
5. **Batch 6 candidates** (unresearched): `playwright`, `selenium`
   (revisit -- earlier excluded only for lack of browser binaries in
   this sandbox; WSL may solve that now), plus whatever's needed to
   reach 60.
6. Longer-standing gaps noted in `docs/testing-maturity.md`, not
   touched this session: version-matrix CI beyond Python 3.13 (full
   3.10-3.12 range), concurrency tests beyond the three web
   frameworks, full exception-surface breadth per integration.

## Open questions (not yet answered by the user)

- Whether to actually pursue the **separate npm/TS companion package**
  idea (shares whytrail's JSON schema, would let a Node/TS/React
  project get whytrail-style explanations for its own errors) as a
  real roadmap item, or stay focused on the 60-plugin push for now.
- Whether/when to cut the next real release (`0.2.1`) -- current
  `pyproject.toml` still says `0.2.0`; all work above is unreleased.

## Where to look for more detail

- `CHANGELOG.md` -- full, dated account of every change, including the
  exact bugs found and how.
- `docs/adr/` -- architecture decisions, especially `0003` (ecosystem
  scale triage -- what earns a plugin and what doesn't) and `0006`
  (why extras instead of separate packages).
- `docs/plugin-guide.md` -- full integration table, bundled-vs-external
  authoring split.
- `docs/testing-maturity.md` -- explicit list of what test coverage
  does and doesn't claim.
- `.github/workflows/ci.yml` -- every floor-version bug found this
  project's whole history is documented inline as a comment above the
  matrix entry it applies to.
