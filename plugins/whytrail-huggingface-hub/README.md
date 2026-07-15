# whytrail-huggingface-hub

`why()` on a `huggingface_hub.errors.HfHubHTTPError` shows the method,
URL, and status, with the Hub API's own error text available via the
redactable `locals` mechanism used throughout this ecosystem (ADR 0002
§3 item 5) -- it can mention repository or account details.

```python
try:
    hf_hub_download(repo_id="...", filename="...")
except HfHubHTTPError as exc:
    print(whytrail.why(exc))
```

Not already covered by `whytrail-httpx`: `HfHubHTTPError` subclasses
`httpx.HTTPError` directly, not `httpx.HTTPStatusError`.
