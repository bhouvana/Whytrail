"""FastAPI: safe-by-default exception explanations on a real endpoint.

Run: python examples/ex_fastapi.py
Needs: pip install whytrail[fastapi]
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from whytrail.integrations import fastapi as whytrail_fastapi


def make_app(**install_kwargs: object) -> FastAPI:
    app = FastAPI()
    whytrail_fastapi.install(app, **install_kwargs)

    @app.get("/charge")
    def charge() -> dict[str, str]:
        api_key = "sk-super-secret-token"  # noqa: F841 -- deliberately never leaked, see below
        raise ValueError("payment failed: card declined")

    return app


def main() -> None:
    # Production default: install(app) with no kwargs. The client sees
    # nothing whytrail-specific at all -- no explanation, no secret.
    prod_client = TestClient(make_app(), raise_server_exceptions=False)
    prod_response = prod_client.get("/charge")
    print("production default response:")
    print(f"  status={prod_response.status_code} body={prod_response.json()}")
    print()

    # Local dev: debug=True adds the explanation to the response body,
    # but locals (the secret api_key) still need a *second*, separate
    # opt-in (include_locals_in_response=True) before they're included --
    # two independent switches for two independent questions.
    dev_client = TestClient(make_app(debug=True), raise_server_exceptions=False)
    dev_response = dev_client.get("/charge")
    why_step = dev_response.json()["why"]["steps"][0]
    print("debug=True response (explanation, no locals):")
    print(f"  status={dev_response.status_code}")
    print(f"  why: {why_step['description']}  [{why_step['confidence_label']}]")
    print(f"  suggestion: {why_step['suggestion']}")
    print(f"  secret leaked into response: {'sk-super-secret-token' in dev_response.text}")


if __name__ == "__main__":
    main()
