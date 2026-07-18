"""Flask: safe-by-default exception explanations on a real endpoint.

Run: python examples/ex_flask.py
Needs: pip install whytrail[flask]
"""

from __future__ import annotations

from flask import Flask

from whytrail.integrations import flask as whytrail_flask


def make_app(**install_kwargs: object) -> Flask:
    app = Flask(__name__)
    whytrail_flask.install(app, **install_kwargs)

    @app.route("/charge")
    def charge() -> str:
        api_key = "sk-super-secret-token"  # noqa: F841 -- deliberately never leaked, see below
        raise ValueError("payment failed: card declined")

    return app


def main() -> None:
    # Production default: nothing whytrail-specific reaches the client.
    prod_response = make_app().test_client().get("/charge")
    print("production default response:")
    print(f"  status={prod_response.status_code} body={prod_response.get_json()}")
    print()

    # debug=True adds the explanation; locals still need their own
    # separate opt-in (include_locals_in_response=True) to be included.
    dev_response = make_app(debug=True).test_client().get("/charge")
    why_step = dev_response.get_json()["why"]["steps"][0]
    print("debug=True response (explanation, no locals):")
    print(f"  status={dev_response.status_code}")
    print(f"  why: {why_step['description']}  [{why_step['confidence_label']}]")
    secret_leaked = "sk-super-secret-token" in dev_response.get_data(as_text=True)
    print(f"  secret leaked into response: {secret_leaked}")


if __name__ == "__main__":
    main()
