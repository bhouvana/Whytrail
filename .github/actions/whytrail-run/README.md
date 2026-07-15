# whytrail run (GitHub Action)

Wraps `whytrail run` (see `src/whytrail/cli/__main__.py`) so a CI job's failure
output shows a causal explanation instead of a bare traceback -- the same
CLI a developer would run locally, packaged for a workflow step.

```yaml
- uses: <owner>/whytrail/.github/actions/whytrail-run@main
  with:
    script: scripts/nightly_import.py
    graph: "true"                          # optional: include a Mermaid graph
    extra-packages: whytrail-requests         # optional: plugin distributions the script needs
```

On an uncaught exception, the step fails (matching `whytrail run`'s own exit
code) and the explanation appears in the job log at the point of failure --
no extra step needed to surface it.

Inputs: `script` (required), `args`, `python-version` (default `3.x`),
`graph` (default `false`), `extra-packages`.
