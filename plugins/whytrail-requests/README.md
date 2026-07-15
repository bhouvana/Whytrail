# whytrail-requests

A `whytrail` plugin that explains `requests.Response` and
`requests.exceptions.RequestException` with domain detail (method, URL,
status, response body) instead of the generic exception-chain fallback.

```python
import whytrail
import requests

try:
    requests.get("https://api.example.invalid/orders", timeout=1).raise_for_status()
except requests.exceptions.RequestException as exc:
    print(whytrail.why(exc))
```

Install alongside `whytrail`; no code changes required -- it registers itself
via the `whytrail.explainers` entry point on first `why()` call.

The response body is attached via the redactable `locals` mechanism used
throughout this ecosystem (ADR 0002 §3 item 5) -- a REST API's error
response can echo back request data, the same risk as an LLM API's
response body (`whytrail-openai`/`whytrail-anthropic`). Call
`.redacted()` on the `Explanation` before sending it anywhere off-box.
