"""whytrail plugin for Scrapy (ADR 0003).

Connects to Scrapy's own `spider_error` signal -- fired whenever a
spider callback raises -- and logs a whytrail explanation of the
underlying exception (unwrapped from Twisted's `Failure` via
`.value`), plus which URL's response triggered it. Same shape as
whytrail-celery/whytrail-rq/whytrail-dramatiq, adapted to Scrapy's
signal-manager protocol instead of a broker/queue hook.

The response URL is the target site's URL, not user data, so it's
safe in `description`; the response body itself is never touched by
this plugin at all (out of scope for explaining a parse failure, and
avoids the redaction question entirely by not capturing it).
"""

from __future__ import annotations

import logging
import typing as t

import whytrail

_logger = logging.getLogger("whytrail.scrapy")


def install(signal_manager: t.Any, *, logger: logging.Logger | None = None) -> None:
    """Connect to a spider_error signal. Takes anything with a
    pydispatch-style `.connect(receiver, signal=...)` -- a real
    Crawler's `.signals` attribute in production, or a standalone
    `scrapy.signalmanager.SignalManager` (Scrapy's own documented way
    to use signals outside a full crawl, and how this plugin's own
    tests exercise it without running Twisted's reactor).

        class MySpider(scrapy.Spider):
            @classmethod
            def from_crawler(cls, crawler, *args, **kwargs):
                spider = super().from_crawler(crawler, *args, **kwargs)
                from whytrail.integrations import scrapy as whytrail_scrapy
                whytrail_scrapy.install(crawler.signals)
                return spider
    """
    from scrapy import signals

    log = logger or _logger

    def _on_spider_error(failure: t.Any, response: t.Any, spider: t.Any) -> None:
        exc = failure.value
        explanation = whytrail.why(exc)
        url = getattr(response, "url", "<unknown url>")
        log.error("spider %r failed parsing %s\n%s", getattr(spider, "name", spider), url, explanation.text)

    # weak=False: pydispatch (which Scrapy's signal system is built on)
    # defaults to weak references for receivers. _on_spider_error is a
    # closure with nothing else holding a strong reference to it, so
    # with the default it was silently garbage-collected the moment
    # install() returned, and the signal fired to zero live receivers
    # -- found by checking send_catch_log's return value in this
    # plugin's own tests, not by reading pydispatch's docs in advance.
    signal_manager.connect(_on_spider_error, signal=signals.spider_error, weak=False)
