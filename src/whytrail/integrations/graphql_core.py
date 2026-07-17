"""whytrail plugin for graphql-core (ADR 0003).

`graphql-core` is the execution engine underneath strawberry-graphql,
Ariadne, and graphene -- registering against its `GraphQLError` covers
all three without needing a plugin per framework. `GraphQLError.path`
is the resolver path where the error occurred (e.g.
`["user", "profile", "ssn"]`), structured detail a bare `str(exc)`
(just `.message`) drops entirely.

`.message` goes through `locals`, not `description` (ADR 0002 §3 item
5): resolver error messages routinely echo back the offending field
value. `.path` -- the shape of the query, never the data in it -- is
safe in `description`.
"""

from __future__ import annotations

import graphql

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_graphql_error(exc: "graphql.GraphQLError") -> Explanation:
    path = exc.path
    subject = f"{type(exc).__name__} at {'.'.join(str(p) for p in path)}" if path else type(exc).__name__
    steps = [
        ExplanationStep(
            description=subject,
            confidence=Confidence.EXPLICIT.value,
            kind="exception",
        )
    ]
    if exc.message:
        steps.append(
            ExplanationStep(
                description="resolver message",
                confidence=Confidence.EXPLICIT.value,
                kind="external",
                locals={"message": exc.message},
            )
        )
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(graphql.GraphQLError, _explain_graphql_error)
