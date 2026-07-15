"""whytrail plugin for marshmallow (ADR 0003).

`ValidationError.messages` already carries a per-field breakdown --
the same structured detail Pydantic's `ValidationError.errors()`
provides (see whytrail-pydantic) -- that `str(exc)` doesn't surface
field-by-field. Unlike Pydantic, marshmallow's messages don't embed
the actual bad input value (only the generic message string, e.g. "Not
a valid integer."), so there's no locals-redaction concern here the
way there is for Pydantic's `input` or jsonschema's `instance`.
"""

from __future__ import annotations

import typing as t

import marshmallow

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_validation_error(exc: "marshmallow.ValidationError") -> Explanation:
    fields = list(_flatten(exc.messages, ()))
    field_count = len(fields)
    steps = [
        ExplanationStep(
            description=f"{field_count} field(s) failed validation",
            confidence=Confidence.EXPLICIT.value,
            kind="exception",
        )
    ]
    for path_parts, message in fields:
        field_path = ".".join(path_parts) if path_parts else "?"
        steps.append(
            ExplanationStep(
                description=f"field {field_path!r}: {message}",
                confidence=Confidence.EXPLICIT.value,
                kind="value",
            )
        )
    return Explanation(subject=f"{field_count} field(s) failed validation", steps=steps, tracked=True)


def _flatten(messages: t.Any, path: tuple[str, ...]) -> t.Iterator[tuple[tuple[str, ...], str]]:
    if isinstance(messages, dict):
        for key, value in messages.items():
            yield from _flatten(value, (*path, str(key)))
    elif isinstance(messages, list):
        for item in messages:
            if isinstance(item, (dict, list)):
                yield from _flatten(item, path)
            else:
                yield path, str(item)
    else:
        yield path, str(messages)


def register() -> None:
    register_from_plugin(marshmallow.ValidationError, _explain_validation_error)
