"""Validates whytrail's hvac plugin against real hvac.exceptions.VaultError
objects (and its per-status subclasses) -- no live Vault instance
needed."""

from __future__ import annotations

import pytest

hvac = pytest.importorskip("hvac")
pytest.importorskip("whytrail.integrations.hvac")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402
from hvac.exceptions import VaultError, Forbidden  # noqa: E402

SECRET_PATH = "secret/data/prod/db-password"


def _vault_error(errors=None):
    return VaultError(
        errors=errors if errors is not None else ["permission denied"],
        method="GET",
        url=f"https://vault.example.com/v1/{SECRET_PATH}",
    )


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(VaultError) is not None


def test_why_on_vault_error_shows_type_name():
    explanation = whytrail.why(_vault_error())
    assert explanation.known
    assert "VaultError" in explanation.text


def test_url_and_errors_are_in_locals_and_strippable_via_redacted():
    explanation = whytrail.why(_vault_error())
    detail_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_PATH in detail_step.locals["url"]
    assert SECRET_PATH not in detail_step.description

    redacted = explanation.redacted()
    assert SECRET_PATH not in redacted.text


def test_why_on_subclass_still_resolves_via_base_registration():
    exc = Forbidden(errors=["not authorized"], method="GET", url="https://vault.example.com/v1/secret/x")
    explanation = whytrail.why(exc)
    assert explanation.known
    assert "Forbidden" in explanation.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(VaultError, lambda exc: "overridden by the user")
    explanation = whytrail.why(_vault_error())
    assert "overridden by the user" in explanation.text
