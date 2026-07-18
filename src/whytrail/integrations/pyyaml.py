"""whytrail plugin for PyYAML (ADR 0003).

`MarkedYAMLError` (the base of `ParserError`, `ScannerError`,
`ComposerError`, `ConstructorError`, ...) carries the line/column of
the failure, a snippet of the surrounding document, and a `.problem`
description -- detail `str(exc)` already prints, but not through
`why()`'s structured, redaction-aware model.

Neither `.problem`/`.context` nor the snippet is used in
`description`: the snippet is obviously document content (PyYAML
parses config files as often as data files, and a snippet can
legitimately contain a secret on an adjacent line to the syntax
error), but `.problem` isn't reliably safe either --
`ConstructorError.problem` embeds the actual tag string from the
document (e.g. "could not determine a constructor for the tag
'...'"), which follows the same shape of risk this ecosystem's
DB-driver plugins already found in pymongo's and asyncpg's own
message text. `description` here is built only from the exception
type and location; `.problem`/`.context`/the snippet all go through
`locals` (ADR 0002 §3 item 5).
"""

from __future__ import annotations


import yaml

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_yaml_error(exc: "yaml.MarkedYAMLError") -> Explanation:
    mark = exc.problem_mark
    location = f"{mark.name}:{mark.line + 1}:{mark.column + 1}" if mark is not None else None
    subject = f"{type(exc).__name__} at {location}" if location else type(exc).__name__

    detail: dict[str, str] = {}
    if exc.problem:
        detail["problem"] = exc.problem
    if exc.context:
        detail["context"] = exc.context
    if mark is not None:
        detail["snippet"] = mark.get_snippet()

    steps = [
        ExplanationStep(
            description=subject,
            confidence=Confidence.EXPLICIT.value,
            kind="external",
            location=location,
            locals=detail or None,
        )
    ]
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(yaml.MarkedYAMLError, _explain_yaml_error)
