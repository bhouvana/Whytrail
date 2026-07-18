"""Django: safe-by-default exception explanations via WhytrailMiddleware.

Run: python examples/ex_django.py
Needs: pip install whytrail[django]

Uses django.conf.settings.configure() directly rather than a full
Django project layout -- the minimum needed to exercise real Django
request/middleware machinery (RequestFactory, process_exception)
without settings.py/manage.py boilerplate a debugging-library example
doesn't need.
"""

from __future__ import annotations

import json

import django.conf

if not django.conf.settings.configured:
    django.conf.settings.configure(DEBUG=False, ALLOWED_HOSTS=["testserver"])
    django.setup()

from django.test import RequestFactory  # noqa: E402
from django.test.utils import override_settings  # noqa: E402

from whytrail.integrations import django as whytrail_django  # noqa: E402


def charge() -> None:
    api_key = "sk-super-secret-token"  # noqa: F841 -- deliberately never leaked, see below
    raise ValueError("payment failed: card declined")


def main() -> None:
    middleware = whytrail_django.WhytrailMiddleware(get_response=lambda request: None)
    request = RequestFactory().get("/charge")

    # Production default: settings.DEBUG=False (set above) -> nothing
    # whytrail-specific reaches the client.
    with override_settings(DEBUG=False):
        try:
            charge()
        except ValueError as exc:
            prod_response = middleware.process_exception(request, exc)
    print("production default (DEBUG=False) response:")
    print(f"  status={prod_response.status_code} body={prod_response.content.decode()}")
    print()

    # settings.DEBUG=True adds the explanation; locals still need their
    # own separate opt-in (WHYTRAIL_INCLUDE_LOCALS_IN_RESPONSE) to show.
    with override_settings(DEBUG=True):
        try:
            charge()
        except ValueError as exc:
            dev_response = middleware.process_exception(request, exc)
    body = json.loads(dev_response.content.decode())
    why_step = body["why"]["steps"][0]
    print("DEBUG=True response (explanation, no locals):")
    print(f"  status={dev_response.status_code}")
    print(f"  why: {why_step['description']}  [{why_step['confidence_label']}]")
    secret_leaked = "sk-super-secret-token" in dev_response.content.decode()
    print(f"  secret leaked into response: {secret_leaked}")


if __name__ == "__main__":
    main()
