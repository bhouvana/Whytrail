# ADR 0005: VS Code extension -- scope assessment, not a build

## Status

Assessed, not started. This ADR exists to make the assessment itself a
citable artifact rather than leave "we should build a VS Code extension"
as an unexamined idea that resurfaces every few months with no more
information attached than it had the first time.

## Context

A VS Code extension was flagged during the category-strategy review as
the single highest-visibility adoption lever available -- more
developers would see `whytrail` inside their editor in a week than would
find it via PyPI search in a year. That claim was never scoped: no MVP
definition, no feasibility check against what the VS Code extension API
actually allows, no effort estimate, no answer to "now or later."

## What VS Code's extension API actually allows here

Two integration depths exist, with very different cost:

1. **Deep**: hook the debugger itself -- show `why()` inline when
   stopped at an exception in the debug adapter, hover a variable to see
   its provenance. This needs either a fork/wrapper of `debugpy` (the
   Python extension's debug adapter) or the Debug Adapter Protocol's
   narrow extension points, neither of which whytrail controls. Real
   engineering, real maintenance burden tied to `debugpy`'s own release
   cycle, and not attempted by this assessment.
2. **Shallow**: drive the CLI that already exists. `whytrail run
   script.py --json` (`src/whytrail/cli/__main__.py`) already runs a
   script and returns a structured `Explanation.json()` payload on an
   uncaught exception. An extension needs only to: add a "Run with
   whytrail" command/CodeLens on the active Python file, shell out to
   the CLI, and render the JSON in a webview instead of a terminal --
   syntax-highlighted locations, click-to-jump to the source line,
   collapsible `locals`, and `Explanation.graph()`'s Mermaid output
   rendered as an actual diagram instead of text.

Depth 2 is the only one worth scoping now: it reuses 100% of existing
whytrail code (the CLI, `Explanation.json()`, `.graph()`), needs no
`debugpy` coordination, and is a contained TypeScript project independent
of whytrail's own release cadence apart from the JSON contract below.

## A real gap this assessment found: `location` isn't structured

`ExplanationStep.location` (and therefore `Explanation.json()`'s
`steps[].location`) is a single formatted string:
`"{filename}:{lineno}, in {funcname}"` (see `_location()` in
`runtime/capture.py`, `explainers/builtin.py`, `runtime/monitoring.py`).
Nothing in whytrail today parses this string back apart -- confirmed
while auditing for Windows/Linux portability gaps -- so the format has
been free to stay a human-readable string with no cost.

A "click to jump to source" webview command is exactly the kind of
consumer that *would* need to parse it back into a file path and line
number, and a naive `location.split(":")` breaks on Windows paths
(`C:\foo.py:12, in bar` contains two colons, not one). This isn't a bug
today -- nothing in this repository does that split -- but it's a
concrete prerequisite the extension would create: either a structured
companion (`{"location": "...", "file": "...", "line": 12}` in the JSON
payload) or a documented, colon-safe parsing convention, decided and
shipped *before* an extension depends on it, not discovered after
external code already parses the fragile format.

## Effort estimate (depth-2 MVP)

Command registration, `child_process` invocation of the CLI, JSON
parsing, and a webview panel with basic styling and click-to-jump is
roughly a 1-2 week build for one developer already familiar with the VS
Code extension API, plus Marketplace packaging/listing overhead. Small
by itself. Scoped here, not started, because of the question below.

## Decision: not now

Publishing a VS Code extension for a library with zero published
releases and zero users inverts the adoption funnel it's meant to serve:
an extension only creates value once someone already has `whytrail`
installed in a project, and nobody discovers a library through its
editor extension before discovering the library. The same reasoning
already applied to the hosted/company question in ADR 0002 ("multi-year
outcome, not a 1.0 workstream") applies here at a smaller scale: this is
a post-launch lever, not a pre-launch one.

What would need to be true before starting the build, whenever that is:

1. **whytrail is actually published on PyPI.** The GitHub side of this
   is done (`github.com/bhouvana/Whytrail`) but a GitHub repo alone isn't
   installable via `pip install whytrail` -- an extension for a library
   nobody can `pip install` has nothing to shell out to.
2. **The CLI's `--json` output has its own frozen contract**, the same
   way `EXPLAINER_PROTOCOL_VERSION` freezes the explainer plugin
   contract independent of whytrail's release number (ADR 0002 §3 item
   6) -- otherwise every whytrail release is a potential silent break
   for the extension, discovered by users, not by CI.
3. **`location` gets a structured companion field or a documented
   parsing convention** (above), decided deliberately rather than
   reverse-engineered from whatever the extension's first version
   happened to assume.
4. **Real signal that the shallow (depth-2) integration is worth
   building at all** -- e.g., users actually reaching for `whytrail run`
   from a terminal today, which this assessment cannot manufacture
   before whytrail has any users.

## Consequences

- No code changes from this ADR. The `location` field stays an
  unstructured string until item 3 above is actually acted on.
- This assessment is citable the next time "what about a VS Code
  extension" comes up, so the answer is "scoped in ADR 0005, blocked on
  publish + a frozen CLI JSON contract + a structured location field,"
  not a re-litigation from zero.
