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
- Current version in `pyproject.toml`: **0.2.0** (unreleased changes on
  top, not yet cut as 0.2.1)

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

- 34 bundled integrations (22 explainer-shaped, auto-registered; 12
  integration-shaped, need explicit user wiring).
- 268 tests passing, `mypy --strict` clean.
- Target: 60 integrations total (34 done, ~26 to go).

## Pending / next steps

1. **Batch 2 plugins toward 60** (in progress): `elasticsearch` is
   **done** -- `elasticsearch.ApiError`/`NotFoundError`, verified via a
   real request/response round trip against a throwaway local HTTP
   server (`.meta.status` + `.body`, `.body` fully redacted since
   `error.reason` can echo a raw query fragment). Still need the same
   real-object-inspection research for: `pika`, `kafka-python`,
   `kubernetes`, `azure-core` -- a background research agent was
   dispatched for these four; check its findings before writing code.
2. **Batch 3 candidates** (unresearched): `falcon`, `lxml`, `protobuf`,
   `authlib`, `tomllib`.
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
