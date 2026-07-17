"""Validates the influxdb integration against a real
influxdb_client.rest.ApiException."""

from __future__ import annotations

import pytest

influx_rest = pytest.importorskip("influxdb_client.rest")
pytest.importorskip("whytrail.integrations.influxdb")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402

SECRET_MEASUREMENT = "secret_measurement_name"


def test_plugin_is_discovered():
    assert registry.resolve_explainer(influx_rest.ApiException) is not None


def test_why_on_api_exception_shows_status_and_reason():
    exc = influx_rest.ApiException(status=404, reason="Not Found")
    explanation = whytrail.why(exc)
    assert explanation.known
    assert "404" in explanation.text
    assert "Not Found" in explanation.text


def test_body_is_in_locals_and_strippable_via_redacted():
    exc = influx_rest.ApiException(status=400, reason="Bad Request")
    exc.body = f'{{"message":"field {SECRET_MEASUREMENT} not found"}}'
    explanation = whytrail.why(exc)
    body_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_MEASUREMENT in body_step.locals["body"]
    assert SECRET_MEASUREMENT not in body_step.description

    redacted = explanation.redacted()
    assert SECRET_MEASUREMENT not in redacted.text
    assert "400" in redacted.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(influx_rest.ApiException, lambda exc: "overridden by the user")
    exc = influx_rest.ApiException(status=404, reason="Not Found")
    explanation = whytrail.why(exc)
    assert "overridden by the user" in explanation.text
