"""whytrail plugin for the Docker SDK (docker-py) (ADR 0003).

`APIError` carries the HTTP status code from the Docker daemon's own
`requests.Response`, plus a separate `.explanation` string the daemon
returns describing exactly what went wrong (e.g. "No such image",
"port is already allocated") -- detail `str(exc)` folds into one
generic "Client/Server Error" line.

`.explanation` goes through `locals`, not `description` (ADR 0002 §3
item 5): it routinely names the specific container, image, volume, or
port involved.
"""

from __future__ import annotations

import docker.errors

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_api_error(exc: "docker.errors.APIError") -> Explanation:
    subject = f"{type(exc).__name__}: HTTP {exc.status_code}" if exc.status_code else type(exc).__name__
    steps = [
        ExplanationStep(description=subject, confidence=Confidence.EXPLICIT.value, kind="external"),
    ]
    if exc.explanation:
        steps.append(
            ExplanationStep(
                description="daemon explanation",
                confidence=Confidence.EXPLICIT.value,
                kind="external",
                locals={"explanation": exc.explanation},
            )
        )
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(docker.errors.APIError, _explain_api_error)
