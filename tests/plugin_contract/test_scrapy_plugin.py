"""Validates whytrail-scrapy against a real Scrapy spider_error signal,
sent through a real scrapy.signalmanager.SignalManager -- Scrapy's own
documented way to use signals outside a full crawl, avoiding the need
to run Twisted's reactor for a test."""

from __future__ import annotations

import logging

import pytest

scrapy = pytest.importorskip("scrapy")
pytest.importorskip("whytrail_scrapy")

from scrapy.signalmanager import SignalManager  # noqa: E402
from twisted.python.failure import Failure  # noqa: E402

import whytrail_scrapy  # noqa: E402


class _Spider(scrapy.Spider):
    name = "test-spider"


def _fire_spider_error(exc: Exception):
    spider = _Spider()
    sm = SignalManager(spider)
    logger = logging.getLogger("whytrail.scrapy")

    records = []

    class _Handler(logging.Handler):
        def emit(self, record):
            records.append(self.format(record))

    handler = _Handler()
    logger.addHandler(handler)
    logger.setLevel(logging.ERROR)
    try:
        whytrail_scrapy.install(sm)
        try:
            raise exc
        except Exception:
            failure = Failure()
        response = scrapy.http.HtmlResponse(url="https://example.com/page", body=b"<html></html>")
        sm.send_catch_log(signal=scrapy.signals.spider_error, failure=failure, response=response, spider=spider)
    finally:
        logger.removeHandler(handler)
    return "\n".join(records)


def test_spider_error_is_logged_with_explanation():
    log_text = _fire_spider_error(ValueError("parse failed"))
    assert "parse failed" in log_text
    assert "test-spider" in log_text


def test_spider_error_includes_the_url():
    log_text = _fire_spider_error(ValueError("parse failed"))
    assert "https://example.com/page" in log_text
