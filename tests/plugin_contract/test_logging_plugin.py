"""Validates whytrail's stdlib `logging` integration end to end via a
real logging.Logger and a real logging.Handler capturing output --
no mocking of the logging module itself."""

from __future__ import annotations

import logging

import pytest

pytest.importorskip("whytrail.integrations.logging")

import whytrail.integrations.logging as whytrail_logging  # noqa: E402

SECRET = "sk-super-secret-token"


def _make_logger(name: str, **install_kwargs: object) -> tuple[logging.Logger, list[str]]:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.filters.clear()
    logger.handlers.clear()
    logger.propagate = False
    records: list[str] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(self.format(record))

    handler = _Capture()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    whytrail_logging.install(logger, **install_kwargs)
    return logger, records


def test_plain_log_without_exception_is_unaffected():
    logger, records = _make_logger("whytrail-test-plain")
    logger.info("just a normal message")
    assert records == ["just a normal message"]


def test_exception_log_gains_a_whytrail_explanation():
    logger, records = _make_logger("whytrail-test-exc")

    def load_codes(region):
        table = {}
        if region not in table:
            raise ValueError(f"missing region {region!r}")
        return table

    try:
        load_codes("EU")
    except ValueError:
        logger.exception("request failed")

    assert len(records) == 1
    assert "request failed" in records[0]
    assert "why(ValueError: missing region 'EU')" in records[0]


def test_percent_style_args_still_interpolate_correctly():
    logger, records = _make_logger("whytrail-test-args")
    try:
        raise ValueError("boom")
    except ValueError:
        logger.error("processing item %s failed", 42, exc_info=True)
    assert records[0].startswith("processing item 42 failed\n")


def test_locals_are_redacted_by_default():
    logger, records = _make_logger("whytrail-test-redact")

    def charge():
        api_key = SECRET  # noqa: F841
        raise ValueError("payment failed")

    try:
        charge()
    except ValueError:
        logger.exception("charge failed")

    assert SECRET not in records[0]
    assert "payment failed" in records[0]


def test_log_locals_true_includes_locals():
    logger, records = _make_logger("whytrail-test-log-locals", log_locals=True)

    def charge():
        api_key = SECRET  # noqa: F841
        raise ValueError("payment failed")

    try:
        charge()
    except ValueError:
        logger.exception("charge failed")

    assert SECRET in records[0]
