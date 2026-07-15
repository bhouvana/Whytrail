"""whytrail plugin for pymongo (ADR 0003).

`PyMongoError` subclasses (`OperationFailure`, `DuplicateKeyError`, ...)
carry MongoDB's own structured error response via `.code`/`.details`.

Unlike every other plugin in this ecosystem, the driver-provided
message itself is not safe to put in `description` at all: pymongo
bakes `.details` straight into `exc.args[0]` at construction time
("... full error: {details}"), and MongoDB's own `errmsg` text
typically embeds the offending value inline too (e.g. "E11000
duplicate key error ... dup key: { email: "a@example.com" }") -- there
is no driver-provided string here that's reliably value-free the way
asyncpg's exc.args[0] or SQLAlchemy's exc.orig are. So `description`
here is built from *only* the exception type and the numeric code,
never from `str(exc)`/`exc.args`/`.details`, all of which go through
`locals` instead (ADR 0002 §3 item 5). This was caught by testing the
redaction path against a value known to be in the message, not assumed
from reading the driver's docs -- see
tests/plugin_contract/test_pymongo_plugin.py.
"""

from __future__ import annotations

import typing as t

import pymongo.errors

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin

__version__ = "0.1.0"


def _explain_pymongo_error(exc: "pymongo.errors.PyMongoError") -> Explanation:
    code = getattr(exc, "code", None)
    details = getattr(exc, "details", None)
    subject = f"{type(exc).__name__} (code={code})" if code is not None else type(exc).__name__

    steps = [
        ExplanationStep(
            description=subject,
            confidence=Confidence.EXPLICIT.value,
            kind="exception",
            locals={"message": str(exc)},
        )
    ]
    if details:
        steps.append(
            ExplanationStep(
                description="error details",
                confidence=Confidence.EXPLICIT.value,
                kind="external",
                locals={"details": repr(details)},
            )
        )
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(pymongo.errors.PyMongoError, _explain_pymongo_error)
