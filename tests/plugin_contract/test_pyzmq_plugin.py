"""Validates the pyzmq integration against a real zmq.ZMQError."""

from __future__ import annotations

import pytest

zmq = pytest.importorskip("zmq")
pytest.importorskip("whytrail.integrations.pyzmq")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402


def test_plugin_is_discovered():
    assert registry.resolve_explainer(zmq.ZMQError) is not None


def test_why_shows_errno_that_bare_str_hides():
    exc = zmq.ZMQError(errno=98)
    explanation = whytrail.why(exc)
    assert explanation.known
    # str(exc) alone is just "Unknown error" -- the whole point of this
    # plugin is surfacing the errno a bare traceback would drop.
    assert "98" in explanation.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(zmq.ZMQError, lambda exc: "overridden by the user")
    exc = zmq.ZMQError(errno=98)
    explanation = whytrail.why(exc)
    assert "overridden by the user" in explanation.text
