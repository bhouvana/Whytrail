"""whytrail plugin for PyGithub, the GitHub REST API client (ADR 0003).

`GithubException` carries the HTTP status, the (decoded) response data
GitHub's API returned, and response headers -- properties, not public
attributes (name-mangled internally), confirmed by reading the class
rather than assumed. Detail a bare `str(exc)` folds into one JSON-
embedded line.

Found while building this: `github/__init__.py` does `from
.GithubException import GithubException`, which rebinds the
`github.GithubException` *attribute* to the class itself, shadowing
the submodule of the same name -- so `github.GithubException.
GithubException` (the chained-attribute form used by most of this
ecosystem's same-name modules, e.g. `requests.py`/`docker.py`) resolves
inconsistently depending on import order and raised `AttributeError`
here. A direct `from github.GithubException import GithubException`
sidesteps the ambiguity entirely.

`.data` goes through `locals`, not `description` (ADR 0002 §3 item 5):
GitHub's own API error bodies routinely reference the specific
repository, branch, or file path involved.
"""

from __future__ import annotations

from github.GithubException import GithubException

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_github_exception(exc: "GithubException") -> Explanation:
    subject = f"{type(exc).__name__}: HTTP {exc.status}"
    steps = [
        ExplanationStep(description=subject, confidence=Confidence.EXPLICIT.value, kind="external"),
    ]
    if exc.data is not None:
        steps.append(
            ExplanationStep(
                description="response data",
                confidence=Confidence.EXPLICIT.value,
                kind="external",
                locals={"data": repr(exc.data)},
            )
        )
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(GithubException, _explain_github_exception)
