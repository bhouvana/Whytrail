"""Validates whytrail's simple-salesforce plugin against a real
simple_salesforce.exceptions.SalesforceError -- no live Salesforce org
needed."""

from __future__ import annotations

import pytest

simple_salesforce = pytest.importorskip("simple_salesforce")
pytest.importorskip("whytrail.integrations.simple_salesforce")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402
from simple_salesforce.exceptions import SalesforceError  # noqa: E402

SECRET_RECORD = "0031x00000SecretId"


def _salesforce_error(content=None):
    return SalesforceError(
        url="https://example.my.salesforce.com/services/data/v58.0/sobjects/Contact/" + SECRET_RECORD,
        status=404,
        resource_name="Contact",
        content=content if content is not None else b'[{"errorCode": "NOT_FOUND"}]',
    )


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(SalesforceError) is not None


def test_why_on_salesforce_error_shows_status_and_resource():
    explanation = whytrail.why(_salesforce_error())
    assert explanation.known
    assert "404" in explanation.text
    assert "Contact" in explanation.text


def test_url_is_in_locals_and_strippable_via_redacted():
    explanation = whytrail.why(_salesforce_error())
    detail_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_RECORD in detail_step.locals["url"]
    assert SECRET_RECORD not in detail_step.description

    redacted = explanation.redacted()
    assert SECRET_RECORD not in redacted.text
    assert "404" in redacted.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(SalesforceError, lambda exc: "overridden by the user")
    explanation = whytrail.why(_salesforce_error())
    assert "overridden by the user" in explanation.text
