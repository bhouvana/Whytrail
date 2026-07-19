"""Validates whytrail's discord-py plugin against a real
discord.errors.HTTPException -- no live Discord gateway connection or
bot token needed.

`HTTPException.__init__` reads `response.status` (and `response.reason`
via its own `str.format`), a shape shared by `aiohttp.ClientResponse`
and (per the library's own docstring) `requests.Response` -- but
`requests.Response` has no `.status` attribute, only `.status_code`, so
that docstring claim doesn't hold for direct construction; a minimal
duck-typed stand-in with just `.status`/`.reason` is what the
constructor actually needs, confirmed by reading its source rather than
assumed from the docstring.
"""

from __future__ import annotations

import pytest

discord = pytest.importorskip("discord")
pytest.importorskip("whytrail.integrations.discord")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402
from discord.errors import HTTPException  # noqa: E402

SECRET_CONTENT = "message content: my secret plan"


class _FakeResponse:
    def __init__(self, status: int, reason: str) -> None:
        self.status = status
        self.reason = reason


def _http_exception(message=None):
    response = _FakeResponse(status=400, reason="Bad Request")
    return HTTPException(
        response, message if message is not None else {"code": 50035, "message": SECRET_CONTENT}
    )


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(HTTPException) is not None


def test_why_on_http_exception_shows_status_and_discord_code():
    explanation = whytrail.why(_http_exception())
    assert explanation.known
    assert "400" in explanation.text
    assert "50035" in explanation.text


def test_text_is_in_locals_and_strippable_via_redacted():
    explanation = whytrail.why(_http_exception())
    detail_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_CONTENT in detail_step.locals["text"]
    assert SECRET_CONTENT not in detail_step.description

    redacted = explanation.redacted()
    assert SECRET_CONTENT not in redacted.text
    assert "400" in redacted.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(HTTPException, lambda exc: "overridden by the user")
    explanation = whytrail.why(_http_exception())
    assert "overridden by the user" in explanation.text
