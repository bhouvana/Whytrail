"""Validates whytrail-boto3 against a real botocore ClientError, raised
via botocore's own Stubber (the standard way to test boto3 error
handling without live AWS calls or credentials) -- not a hand-built
mock exception."""

from __future__ import annotations

import pytest

boto3 = pytest.importorskip("boto3")
pytest.importorskip("whytrail.integrations.boto3")

import whytrail  # noqa: E402
from botocore.exceptions import ClientError  # noqa: E402
from botocore.stub import Stubber  # noqa: E402
from whytrail import registry  # noqa: E402


@pytest.fixture()
def s3_client():
    client = boto3.client(
        "s3", region_name="us-east-1", aws_access_key_id="x", aws_secret_access_key="y"
    )
    stubber = Stubber(client)
    stubber.add_client_error(
        "get_object",
        service_error_code="NoSuchKey",
        service_message="The specified key does not exist.",
        http_status_code=404,
    )
    stubber.activate()
    return client


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(ClientError) is not None


def test_why_on_dynamically_generated_subclass_resolves_via_base_class(s3_client):
    with pytest.raises(ClientError) as excinfo:
        s3_client.get_object(Bucket="my-bucket", Key="missing.txt")

    # botocore raises a dynamically generated subclass (NoSuchKey), not
    # ClientError itself -- confirms the MRO walk actually resolves it
    assert type(excinfo.value).__name__ == "NoSuchKey"
    assert isinstance(excinfo.value, ClientError)

    explanation = whytrail.why(excinfo.value)
    assert explanation.known
    assert "NoSuchKey" in explanation.text
    assert "GetObject" in explanation.text
    assert "404" in explanation.text


def test_manual_registration_still_overrides_the_plugin(s3_client):
    whytrail.register(ClientError, lambda exc: "overridden by the user")
    with pytest.raises(ClientError) as excinfo:
        s3_client.get_object(Bucket="my-bucket", Key="missing.txt")

    explanation = whytrail.why(excinfo.value)
    assert "overridden by the user" in explanation.text
