# Contributing to whytrail

whytrail is currently solo-maintained and pre-1.0; `docs/roadmap.md`
Phase K names "a second maintainer and a real plugin backlog" as the
trigger for a fuller governance process (issue templates, a formal
review process, and so on), and that trigger hasn't fired yet. This
file exists anyway, ahead of that trigger, because one piece of it --
how bugs get turned into permanent regression tests -- is a real,
already-followed rule worth writing down rather than only living in
`CHANGELOG.md`'s narrative. Treat everything below as the current
state of a living document, not a complete governance process.

## The one rule that matters most: regression test first

**When you find a bug in whytrail's own code (not a test bug), write
the test that fails without the fix before you write the fix.**

This is not a new policy invented for this file -- it's a description
of what every real bug fix in this project's `CHANGELOG.md` already
did: the eager `importlib.metadata` import cutting ~30ms off every
`import whytrail`, the `NameError` silently swallowed by
`_load_builtin_explainers()`'s own broad `except Exception`,
`Explanation.redacted()` never touching `NodeKind.VALUE` labels, async/
generator/async-generator `@tracked` tracking the wrong object, the
`argparse.REMAINDER` flag-swallowing in `whytrail run` -- every one of
these was caught by a test failing first, not by code review or
reasoning about the code in advance. Two more turned up building the
redaction-fuzz and version-matrix widening in this same document's own
history (see `docs/testing-maturity.md`): a `requests.Response.text`
charset-detection mismatch and a `except ... as exc` variable-scoping
bug, both real, both caught by running the new test and reading the
failure, not by inspection.

**Why this matters more here than "good practice" generalities:**
whytrail's whole reason to exist is trust in a causal claim ("this is
why"). A bug that ships silently and gets patched without a permanent
test is exactly the kind of regression this project can least afford
to reintroduce later -- the test is what makes the fix permanent
instead of a one-time correction that quietly erodes the next time
someone touches nearby code.

**How to apply it:**
1. Reproduce the bug as a failing test in the relevant `tests/` subtree
   (`tests/unit/`, `tests/integration/`, or `tests/plugin_contract/` --
   see the layout below).
2. Confirm it actually fails, for the reason you think it fails
   (read the traceback; don't assume).
3. Fix the bug.
4. Confirm the same test now passes, and the full suite still does
   (`pytest tests -q` and, for anything under `src/whytrail/` outside
   `integrations/`, `mypy`).
5. Add a `CHANGELOG.md` entry under `## [Unreleased]` describing what
   broke and what the fix was -- future readers should be able to
   reconstruct the failure from the changelog alone, the same way
   every existing entry does.
6. If the bug reveals a real architectural gap (not just a local
   mistake), update the relevant ADR or `docs/explanation-engine.md`
   invariant rather than leaving the reasoning only in the fix's
   commit message.

This does not mean writing tests for hypothetical bugs that haven't
happened -- see the next section.

## What this project deliberately does not do

`docs/roadmap.md`'s own opening line sets the standard this repo holds
itself to: don't claim more than is actually true, and don't pad out
work "to look complete." That standard applies to testing effort the
same way it applies to feature claims and roadmap phases:

- Every test in this repo should trace to something real: an actual
  bug found, a gap a plugin's own docstring names, or a documented
  claim (a stated dependency floor, a redaction guarantee) that hasn't
  actually been checked. "This is the kind of thing that could
  theoretically break" is not, by itself, justification for a test --
  check the actual code and constructor first (several redaction-fuzz
  candidates turned out not to apply once checked: `boto3`, `aiohttp`,
  and `marshmallow` all have plugin-source docstrings explaining why
  there's no redaction-critical field to fuzz in the first place).
- Speculative test *infrastructure* (mutation testing, memory-leak
  instrumentation, and similar) needs the same evidence bar as a new
  feature would: a real, named gap it would close, not "industrial
  libraries have this so we should too." `docs/testing-maturity.md`'s
  own "What still isn't verified" section is the actual, current list
  of named gaps -- work from that list before inventing a new one.
- If you're not sure whether a test earns its place, say so in the
  PR description rather than padding a batch to a round number.

## Running the suite locally

```
pip install -e ".[dev]"       # core + dev tooling (hypothesis, pytest-benchmark, mypy, rich)
pytest tests -q                # core suite + every bundled integration's contract tests you have installed
mypy                            # strict, src/whytrail only (integrations/ is checked per-module in CI instead)
```

Most `tests/plugin_contract/test_*_plugin.py` files use
`pytest.importorskip(...)` and silently skip if that integration's
extra isn't installed -- install `whytrail[extra]` for whichever one
you're touching (see `pyproject.toml`'s `[project.optional-dependencies]`)
rather than trying to install all 60+ locally. `.github/workflows/ci.yml`
runs the full matrix; it's the source of truth for what "actually
supported" means for any given extra/Python-version combination, not
local intuition about what "should" work.

## Adding or changing a plugin

Read `docs/plugin-guide.md` first, in full -- it names the three bars
a library has to clear before it's worth a plugin at all (structured
error data a bare traceback discards, a security-sensitive boundary,
or a non-standard capture mechanism), and most libraries don't clear
any of them. If you can't point to which bar your idea clears, per
that guide, it probably shouldn't be a plugin.

## Architectural changes

Anything touching the core engine (`src/whytrail/core/`), a public
top-level name in `whytrail/__init__.py`, or an existing invariant
documented in `docs/explanation-engine.md`, should have an ADR under
`docs/adr/` before or alongside the code -- not instead of it (see
`docs/roadmap.md`'s own framing: implementation and rationale ship
together, code first when the two are in tension). Read the existing
ADRs before proposing a new one; several plausible-sounding ideas
(a VS Code/LSP integration, AST-based assertion rewriting, distributed
provenance) have already been considered and declined for reasons
that still hold -- check before re-proposing rather than assuming
they haven't been thought about.
