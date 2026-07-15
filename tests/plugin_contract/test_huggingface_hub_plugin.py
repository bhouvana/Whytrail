"""Validates whytrail-huggingface-hub against a real HfHubHTTPError,
raised through huggingface_hub's own hf_raise_for_status() helper
against a constructed httpx.Response -- the same code path the real
SDK uses internally, not a hand-built exception."""

from __future__ import annotations

import pytest

httpx = pytest.importorskip("httpx")
huggingface_hub = pytest.importorskip("huggingface_hub")
pytest.importorskip("whytrail.integrations.huggingface_hub")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402
from huggingface_hub.errors import HfHubHTTPError  # noqa: E402
from huggingface_hub.utils import hf_raise_for_status  # noqa: E402

REPO_NAME = "secret-org/secret-repo"


def _hf_error(message=f"Repository {REPO_NAME} not found"):
    req = httpx.Request("GET", "https://huggingface.co/api/models/x")
    resp = httpx.Response(404, request=req, json={"error": message})
    with pytest.raises(HfHubHTTPError) as excinfo:
        hf_raise_for_status(resp)
    return excinfo.value


def test_not_already_covered_by_httpx_plugin():
    """Sanity check on the premise: HfHubHTTPError subclasses
    httpx.HTTPError directly, not HTTPStatusError, so whytrail-httpx's
    registrations don't reach it via MRO -- this plugin is necessary,
    not redundant."""
    assert HfHubHTTPError.__mro__[1] is httpx.HTTPError
    assert not issubclass(HfHubHTTPError, httpx.HTTPStatusError)


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(HfHubHTTPError) is not None


def test_why_shows_method_url_status():
    exc = _hf_error()
    explanation = whytrail.why(exc)
    assert explanation.known
    assert "GET" in explanation.text
    assert "404" in explanation.text


def test_server_message_in_locals_and_strippable_via_redacted():
    exc = _hf_error()
    explanation = whytrail.why(exc)
    step = next(s for s in explanation.steps if s.locals)
    assert REPO_NAME in step.locals["server_message"]
    assert REPO_NAME not in step.description

    redacted = explanation.redacted()
    assert REPO_NAME not in redacted.text
    assert "404" in redacted.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(HfHubHTTPError, lambda exc: "overridden by the user")
    explanation = whytrail.why(_hf_error())
    assert "overridden by the user" in explanation.text
