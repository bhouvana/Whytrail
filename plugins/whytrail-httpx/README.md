# whytrail-httpx

`why()` on an `httpx.HTTPStatusError` or `RequestError` shows the method,
URL, and response detail instead of httpx's one-line summary.

```python
try:
    response.raise_for_status()
except httpx.HTTPStatusError as exc:
    print(whytrail.why(exc))
```

The response body is attached via the redactable `locals` mechanism used
throughout this ecosystem (ADR 0002 §3 item 5). Call `.redacted()` on the
`Explanation` before sending it anywhere off-box.
