"""Validates the paramiko integration against real paramiko exception
objects, including real generated key pairs for BadHostKeyException --
not a mock of paramiko's own key/fingerprint logic."""

from __future__ import annotations

import pytest

paramiko = pytest.importorskip("paramiko")
pytest.importorskip("whytrail.integrations.paramiko")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402


@pytest.fixture(scope="module")
def keypair():
    return paramiko.RSAKey.generate(1024), paramiko.RSAKey.generate(1024)


def test_plugin_is_discovered():
    assert registry.resolve_explainer(paramiko.BadHostKeyException) is not None
    assert registry.resolve_explainer(paramiko.SSHException) is not None


def test_why_on_bad_host_key_shows_fingerprints_not_raw_keys(keypair):
    expected_key, got_key = keypair
    exc = paramiko.BadHostKeyException("example.com", got_key, expected_key)
    explanation = whytrail.why(exc)
    assert explanation.known
    assert "example.com" in explanation.text
    assert "expected ssh-rsa" in explanation.text
    assert "got ssh-rsa" in explanation.text
    # the raw base64 key material must never appear -- only fingerprints
    assert expected_key.get_base64() not in explanation.text
    assert got_key.get_base64() not in explanation.text


def test_why_on_authentication_exception():
    exc = paramiko.AuthenticationException("Authentication failed.")
    explanation = whytrail.why(exc)
    assert explanation.known
    assert "Authentication failed" in explanation.text


def test_manual_registration_still_overrides_the_plugin(keypair):
    expected_key, got_key = keypair
    whytrail.register(paramiko.BadHostKeyException, lambda exc: "overridden by the user")
    exc = paramiko.BadHostKeyException("example.com", got_key, expected_key)
    explanation = whytrail.why(exc)
    assert "overridden by the user" in explanation.text
