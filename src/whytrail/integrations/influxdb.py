"""whytrail plugin for influxdb-client (ADR 0003).

`influxdb_client.rest.ApiException` carries `.status`/`.reason`/
`.body`/`.retry_after` -- the same structured HTTP-API-error shape
already proven for `whytrail-boto3`/`whytrail-elasticsearch`, squashed
by `str(exc)` into an unstructured multi-line dump.

`.body` goes through `locals`, not `description` (ADR 0002 §3 item 5):
an InfluxDB error body routinely echoes back the offending
measurement/field name from the write or query. `.status`/`.reason`/
`.retry_after` -- structural HTTP metadata, never request content --
are safe in `description`.
"""

from __future__ import annotations

from influxdb_client.rest import ApiException

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_api_exception(exc: "ApiException") -> Explanation:
    steps = [
        ExplanationStep(
            description=f"{type(exc).__name__}: HTTP {exc.status} {exc.reason}",
            confidence=Confidence.EXPLICIT.value,
            kind="external",
        )
    ]
    body = getattr(exc, "body", None)
    if body:
        body_str = body.decode("utf-8", errors="replace") if isinstance(body, bytes) else str(body)
        steps.append(
            ExplanationStep(
                description="response body",
                confidence=Confidence.EXPLICIT.value,
                kind="external",
                locals={"body": body_str},
            )
        )
    subject = f"{type(exc).__name__}: {exc.status} {exc.reason}"
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(ApiException, _explain_api_exception)
