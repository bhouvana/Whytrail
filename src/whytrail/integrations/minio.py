"""whytrail plugin for the MinIO SDK (ADR 0003).

`S3Error` carries the fully-parsed S3-compatible XML error response --
`.code`/`.message`/`.resource`/`.request_id`/`.host_id`/`.bucket_name`/
`.object_name` -- structured fields a bare `str(exc)` folds into one
line. Same S3-error shape as `whytrail[boto3]`'s `ClientError`, for the
self-hosted/S3-compatible-storage audience `boto3` doesn't cover
(MinIO, and any other S3-API-compatible object store).

`.resource`/`.bucket_name`/`.object_name` go through `locals`, not
`description` (ADR 0002 §3 item 5): they identify the specific bucket
and object path involved, not just an error classification.
"""

from __future__ import annotations

import minio.error

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_s3_error(exc: "minio.error.S3Error") -> Explanation:
    subject = f"{type(exc).__name__}: {exc.code}"
    steps = [ExplanationStep(description=subject, confidence=Confidence.EXPLICIT.value, kind="external")]
    locals_ = {
        k: v
        for k, v in {
            "message": exc.message,
            "bucket_name": exc.bucket_name,
            "object_name": exc.object_name,
            "resource": exc.resource,
            "request_id": exc.request_id,
        }.items()
        if v
    }
    if locals_:
        steps.append(
            ExplanationStep(
                description="response detail",
                confidence=Confidence.EXPLICIT.value,
                kind="external",
                locals=locals_,
            )
        )
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(minio.error.S3Error, _explain_s3_error)
