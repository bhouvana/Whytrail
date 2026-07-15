"""whytrail plugin for grpcio (ADR 0003).

`RpcError` instances raised by a real client call also implement
`grpc.Call` (`.code()`, `.details()`) -- structured detail `str(exc)`
doesn't surface cleanly. `.details()` is server-supplied free text and
can contain anything the server author put there (verified directly:
a NOT_FOUND status with a message embedding an email address), so it
goes through `locals`, the same as every other "the server told us
something, and that something might not be safe to export" case in
this ecosystem (ADR 0002 §3 item 5). `.code()` (an enum, e.g.
`NOT_FOUND`) is schema, not data, and stays in `description`.
"""

from __future__ import annotations

import typing as t

import grpc

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin

__version__ = "0.1.0"


def _explain_rpc_error(exc: "grpc.RpcError") -> Explanation:
    code = exc.code() if hasattr(exc, "code") else None
    details = exc.details() if hasattr(exc, "details") else None

    subject = f"{type(exc).__name__}: {code.name if code else 'unknown status'}"
    steps = [
        ExplanationStep(
            description=subject,
            confidence=Confidence.EXPLICIT.value,
            kind="external",
            locals={"details": details} if details else None,
        )
    ]
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(grpc.RpcError, _explain_rpc_error)
