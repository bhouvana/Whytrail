"""Validates whytrail's structlog integration end to end via a real
structlog logger configured with a capturing renderer -- no mocking
of structlog itself."""

from __future__ import annotations

import pytest

structlog = pytest.importorskip("structlog")
pytest.importorskip("whytrail.integrations.structlog")

import whytrail.integrations.structlog as whytrail_structlog  # noqa: E402

SECRET = "sk-super-secret-token"


def _configure(**processor_kwargs: object) -> list[dict]:
    captured: list[dict] = []

    def _capture(logger, method_name, event_dict):
        captured.append(dict(event_dict))
        return event_dict

    structlog.configure(
        processors=[
            whytrail_structlog.add_whytrail_explanation(**processor_kwargs),
            structlog.processors.format_exc_info,
            _capture,
        ],
        logger_factory=structlog.ReturnLoggerFactory(),
    )
    return captured


def test_plain_log_without_exception_has_no_why_key():
    captured = _configure()
    log = structlog.get_logger()
    log.info("just a normal message")
    assert "why" not in captured[0]


def test_exception_log_gains_a_structured_why_key():
    captured = _configure()
    log = structlog.get_logger()
    try:
        raise ValueError("boom")
    except ValueError:
        log.exception("request failed")

    assert "why" in captured[0]
    assert captured[0]["why"]["subject"] == "ValueError: boom"
    assert captured[0]["why"]["known"] is True


def test_locals_are_redacted_by_default():
    captured = _configure()
    log = structlog.get_logger()

    def charge():
        api_key = SECRET  # noqa: F841
        raise ValueError("payment failed")

    try:
        charge()
    except ValueError:
        log.exception("charge failed")

    assert SECRET not in str(captured[0]["why"])


def test_log_locals_true_includes_locals():
    captured = _configure(log_locals=True)
    log = structlog.get_logger()

    def charge():
        api_key = SECRET  # noqa: F841
        raise ValueError("payment failed")

    try:
        charge()
    except ValueError:
        log.exception("charge failed")

    assert SECRET in str(captured[0]["why"])
