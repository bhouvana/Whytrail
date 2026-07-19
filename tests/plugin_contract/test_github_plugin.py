"""Validates whytrail's github plugin against a real
github.GithubException.GithubException -- no live GitHub API calls or
tokens needed."""

from __future__ import annotations

import pytest

github = pytest.importorskip("github")
pytest.importorskip("whytrail.integrations.github")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402
from github.GithubException import GithubException  # noqa: E402

SECRET_REPO = "acme-corp/secret-internal-tools"


def _github_exception(data=None):
    return GithubException(
        status=404,
        data=data if data is not None else {"message": f"Not Found: {SECRET_REPO}"},
        headers={"x-github-request-id": "ABCD:1234"},
    )


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(GithubException) is not None


def test_why_on_github_exception_shows_status():
    explanation = whytrail.why(_github_exception())
    assert explanation.known
    assert "404" in explanation.text


def test_data_is_in_locals_and_strippable_via_redacted():
    explanation = whytrail.why(_github_exception())
    detail_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_REPO in detail_step.locals["data"]
    assert SECRET_REPO not in detail_step.description

    redacted = explanation.redacted()
    assert SECRET_REPO not in redacted.text
    assert "404" in redacted.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(GithubException, lambda exc: "overridden by the user")
    explanation = whytrail.why(_github_exception())
    assert "overridden by the user" in explanation.text
