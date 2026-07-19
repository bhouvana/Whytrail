"""whytrail plugin for the Neo4j Python driver (ADR 0003).

`Neo4jError` carries a structured error taxonomy the server itself
assigns -- `.code` (e.g. `Neo.ClientError.Schema.
ConstraintValidationFailed`), decomposed into `.classification`,
`.category`, and `.title` -- plus `.gql_status`/`.gql_status_description`
(the newer GQLSTATUS-conformant fields, Neo4j 5.26+). None of that
structure survives a bare `str(exc)`, which is the Cypher engine's raw
message only.

`.message` goes through `locals`, not `description` (ADR 0002 §3 item
5): a constraint-violation message routinely echoes back the actual
property value that violated it (see the docstring example in
`Neo4jError._hydrate_neo4j`-produced errors upstream).
"""

from __future__ import annotations

import neo4j.exceptions

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_neo4j_error(exc: "neo4j.exceptions.Neo4jError") -> Explanation:
    subject = f"{type(exc).__name__}: {exc.code}"
    steps = [
        ExplanationStep(description=subject, confidence=Confidence.EXPLICIT.value, kind="external"),
        ExplanationStep(
            description=f"classification={exc.classification}, category={exc.category}, title={exc.title}",
            confidence=Confidence.EXPLICIT.value,
            kind="external",
            locals={"message": exc.message} if exc.message else None,
        ),
    ]
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(neo4j.exceptions.Neo4jError, _explain_neo4j_error)
