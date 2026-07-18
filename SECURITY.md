# Security policy

## Supported versions

whytrail is pre-1.0 (see `docs/api-stability.md`). Only the latest
published release on PyPI is supported with security fixes -- there is
no LTS branch and no backport policy yet; that's named as a real gap,
not silently assumed away, in `docs/roadmap.md` Phase Q ("1.0 and
long-term support policy").

## Reporting a vulnerability

**Please don't open a public GitHub issue for a security report.**
Use [GitHub's private vulnerability reporting](https://github.com/bhouvana/Whytrail/security/advisories/new)
(the "Report a vulnerability" button under this repository's Security
tab) instead -- it reaches the maintainer directly without disclosing
the issue publicly first.

Include, if known:

- The affected version(s) and how you're using whytrail (core only,
  or which extras/integrations).
- A minimal reproduction.
- The impact you believe it has (e.g. does it affect `ExplanationStep.locals`
  redaction, `Explanation.redacted()`, or a specific integration's
  safe-by-default response handling -- see below for why those three
  are the areas most worth flagging specifically).

## What's actually security-sensitive in this codebase

Named directly, not left implicit:

- **Local variable capture.** `ExplanationStep.locals` and Tier 1's
  frame-locals capture (`explainers/builtin.py`) can plausibly contain
  a password, API key, or customer record from the frame where an
  exception originated. `Explanation.redacted()` exists specifically
  to strip this before an `Explanation` leaves a process boundary. A
  bug that leaked locals somewhere `.redacted()` should have covered
  is a real vulnerability, not a cosmetic one.
- **The FastAPI/Flask/Django integrations' safe-by-default response
  handling** (`whytrail/integrations/{fastapi,flask,django}.py`).
  Each requires two *separate* opt-ins (one for whether an explanation
  reaches the HTTP response at all, one for whether locals are
  included in it) specifically so a misconfiguration can't
  accidentally leak a secret into a production response. A way to
  reach locals-in-response with only one opt-in set, or in the
  production-default configuration, is a real vulnerability.
- **The provenance graph never holding a strong reference** to a
  tracked object (`core/graph.py`) -- a bug that caused `track()` to
  keep an object alive past its natural lifetime would be a real
  (if less severe) issue: a debugging tool changing the memory
  behavior of the code it's observing.

## What's out of scope

- Findings that require an attacker to already control the code being
  traced (whytrail explains what a process does; it isn't a sandbox
  and never claimed to be one).
- Third-party library CVEs in an optional extra's dependency (report
  those upstream) unless whytrail's own integration code makes the
  impact worse than using that library directly would.

## Response expectations

This is currently a single-maintainer project (`docs/roadmap.md` Phase
P names that directly as a real bus-factor risk). There's no formal
SLA to promise here that would actually be honest -- reports will be
read and acknowledged as soon as the maintainer sees them, with a fix
or a public advisory following once a report is confirmed, not before.
