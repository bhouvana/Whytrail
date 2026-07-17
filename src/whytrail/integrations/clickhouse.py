"""whytrail plugin for clickhouse-connect (ADR 0003).

`clickhouse_connect.driver.exceptions.ClickHouseError` subclasses
(`DatabaseError`, `OperationalError`, ...) carry `.code`/`.name` --
confirmed by reading the driver's own raise site
(`httpclient.py`/`asyncclient.py`'s `raise err_type(err_str, code=code,
name=name)`), not by hand-constructing an exception and assuming the
same fields would be populated: a bare `ClickHouseError(msg)` leaves
both `None`, they're only set when the driver itself parses a real
HTTP error response's `X-ClickHouse-Exception-Code` header and body.
`.code` is ClickHouse's numeric error code and `.name` is the matching
symbolic taxonomy string (e.g. `"UNKNOWN_TABLE"`), both dropped by
`str(exc)`, which only shows the formatted message.

The message goes through `locals`, not `description` (ADR 0002 §3 item
5): ClickHouse error text routinely embeds the offending table/column
name. `.code`/`.name` -- a stable taxonomy, never request content --
are safe in `description`.
"""

from __future__ import annotations

import clickhouse_connect.driver.exceptions as _ch_exceptions

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_clickhouse_error(exc: "_ch_exceptions.ClickHouseError") -> Explanation:
    code = getattr(exc, "code", None)
    name = getattr(exc, "name", None)
    subject = f"{type(exc).__name__} ({name})" if name else type(exc).__name__
    desc = f"{subject}, code={code}" if code is not None else subject
    steps = [
        ExplanationStep(
            description=desc,
            confidence=Confidence.EXPLICIT.value,
            kind="exception",
        )
    ]
    message = str(exc)
    if message:
        steps.append(
            ExplanationStep(
                description="driver message",
                confidence=Confidence.EXPLICIT.value,
                kind="external",
                locals={"message": message},
            )
        )
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(_ch_exceptions.ClickHouseError, _explain_clickhouse_error)
