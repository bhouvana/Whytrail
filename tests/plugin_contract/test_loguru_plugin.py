"""Validates whytrail's loguru integration end to end via a real
loguru logger with a list-capturing sink -- no mocking of loguru
itself. Uses backtrace=False/diagnose=False on the sink: unrelated to
this integration's own logic, but loguru's default colorized
traceback formatting fails to encode on a Windows console (cp1252),
same as it would for any loguru user on that platform without this
integration installed at all."""

from __future__ import annotations

import pytest

pytest.importorskip("loguru")
pytest.importorskip("whytrail.integrations.loguru")

import whytrail.integrations.loguru as whytrail_loguru  # noqa: E402

SECRET = "sk-super-secret-token"


def _make_logger(**install_kwargs: object) -> tuple[object, list[str]]:
    logger = whytrail_loguru.install(**install_kwargs)
    logger.remove()
    captured: list[str] = []
    logger.add(lambda msg: captured.append(str(msg)), format="{message}", backtrace=False, diagnose=False)
    return logger, captured


def test_plain_log_without_exception_is_unaffected():
    logger, captured = _make_logger()
    logger.info("just a normal message")
    assert captured[0].strip() == "just a normal message"


def test_exception_log_gains_a_whytrail_explanation():
    logger, captured = _make_logger()

    def load_codes(region):
        table = {}
        if region not in table:
            raise ValueError(f"missing region {region!r}")
        return table

    try:
        load_codes("EU")
    except ValueError:
        logger.exception("request failed")

    assert "request failed" in captured[0]
    assert "why(ValueError: missing region 'EU')" in captured[0]


def test_locals_are_redacted_by_default():
    logger, captured = _make_logger()

    def charge():
        api_key = SECRET  # noqa: F841
        raise ValueError("payment failed")

    try:
        charge()
    except ValueError:
        logger.exception("charge failed")

    assert SECRET not in captured[0]
    assert "payment failed" in captured[0]


def test_log_locals_true_includes_locals():
    logger, captured = _make_logger(log_locals=True)

    def charge():
        api_key = SECRET  # noqa: F841
        raise ValueError("payment failed")

    try:
        charge()
    except ValueError:
        logger.exception("charge failed")

    assert SECRET in captured[0]
