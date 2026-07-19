"""Validates whytrail's slack-sdk plugin against a real
slack_sdk.errors.SlackApiError wrapping a real SlackResponse -- no live
Slack API calls or tokens needed."""

from __future__ import annotations

import pytest

slack_sdk = pytest.importorskip("slack_sdk")
pytest.importorskip("whytrail.integrations.slack_sdk")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402
from slack_sdk.errors import SlackApiError  # noqa: E402
from slack_sdk.web.slack_response import SlackResponse  # noqa: E402

SECRET_CHANNEL = "C0SECRETCHANNEL"


def _api_error(data=None):
    response = SlackResponse(
        client=None,
        http_verb="POST",
        api_url="https://slack.com/api/chat.postMessage",
        req_args={},
        data=data if data is not None else {"ok": False, "error": "channel_not_found", "channel": SECRET_CHANNEL},
        headers={},
        status_code=404,
    )
    return SlackApiError("failed to post message", response)


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(SlackApiError) is not None


def test_why_on_api_error_shows_status_and_error_code():
    explanation = whytrail.why(_api_error())
    assert explanation.known
    assert "404" in explanation.text
    assert "channel_not_found" in explanation.text


def test_response_data_is_in_locals_and_strippable_via_redacted():
    explanation = whytrail.why(_api_error())
    data_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_CHANNEL in data_step.locals["data"]
    assert SECRET_CHANNEL not in data_step.description

    redacted = explanation.redacted()
    assert SECRET_CHANNEL not in redacted.text
    assert "404" in redacted.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(SlackApiError, lambda exc: "overridden by the user")
    explanation = whytrail.why(_api_error())
    assert "overridden by the user" in explanation.text
