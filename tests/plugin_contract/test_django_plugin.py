"""Validates whytrail-django's safety boundaries against Django's real
middleware protocol (process_exception), via RequestFactory -- no
mocking of Django internals. Uses Django's own override_settings
rather than pytest-django, to avoid adding a second test-integration
dependency just for one plugin's contract tests."""

from __future__ import annotations

import logging

import pytest

django = pytest.importorskip("django")
pytest.importorskip("whytrail_django")

import django.conf  # noqa: E402

if not django.conf.settings.configured:
    django.conf.settings.configure(DEBUG=False, ALLOWED_HOSTS=["testserver"])
    django.setup()

from django.test import RequestFactory  # noqa: E402
from django.test.utils import override_settings  # noqa: E402

import whytrail_django  # noqa: E402

SECRET = "sk-super-secret-token"


def _raise_with_secret():
    api_key = SECRET  # noqa: F841
    raise ValueError("payment failed")


def _middleware():
    return whytrail_django.WhytrailMiddleware(get_response=lambda request: None)


def test_production_default_response_has_no_explanation_at_all():
    with override_settings(DEBUG=False):
        request = RequestFactory().get("/boom")
        try:
            _raise_with_secret()
        except ValueError as exc:
            response = _middleware().process_exception(request, exc)

    assert response.status_code == 500
    body = response.content.decode()
    assert body == '{"detail": "Internal Server Error"}'
    assert SECRET not in body


def test_production_default_log_is_redacted(caplog):
    with override_settings(DEBUG=False):
        request = RequestFactory().get("/boom")
        with caplog.at_level(logging.ERROR, logger="whytrail.django"):
            try:
                _raise_with_secret()
            except ValueError as exc:
                _middleware().process_exception(request, exc)

    assert SECRET not in caplog.text
    assert "payment failed" in caplog.text


def test_settings_debug_true_includes_explanation_but_redacts_locals():
    with override_settings(DEBUG=True):
        request = RequestFactory().get("/boom")
        try:
            _raise_with_secret()
        except ValueError as exc:
            response = _middleware().process_exception(request, exc)

    body = response.content.decode()
    assert "payment failed" in body
    assert SECRET not in body


def test_whytrail_debug_overrides_settings_debug():
    with override_settings(DEBUG=False, WHYTRAIL_DEBUG=True):
        request = RequestFactory().get("/boom")
        try:
            _raise_with_secret()
        except ValueError as exc:
            response = _middleware().process_exception(request, exc)

    assert "payment failed" in response.content.decode()


def test_include_locals_in_response_requires_explicit_opt_in_even_under_debug():
    with override_settings(DEBUG=True, WHYTRAIL_INCLUDE_LOCALS_IN_RESPONSE=True):
        request = RequestFactory().get("/boom")
        try:
            _raise_with_secret()
        except ValueError as exc:
            response = _middleware().process_exception(request, exc)

    assert SECRET in response.content.decode()


def test_log_locals_setting_is_independent_of_response_setting(caplog):
    with override_settings(DEBUG=False, WHYTRAIL_LOG_LOCALS=True):
        request = RequestFactory().get("/boom")
        with caplog.at_level(logging.ERROR, logger="whytrail.django"):
            try:
                _raise_with_secret()
            except ValueError as exc:
                response = _middleware().process_exception(request, exc)

    assert SECRET in caplog.text
    assert response.content.decode() == '{"detail": "Internal Server Error"}'
