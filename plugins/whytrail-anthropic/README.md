# whytrail-anthropic

`why()` on an `anthropic.APIStatusError` (`RateLimitError`,
`AuthenticationError`, `OverloadedError`, ...) shows the HTTP status,
request ID, and error type instead of the SDK's one-line summary. The
response body is attached via the redactable `locals` mechanism used
throughout this ecosystem (ADR 0002 §3 item 5), since it can echo back
request content.

```python
try:
    client.messages.create(...)
except anthropic.RateLimitError as exc:
    print(whytrail.why(exc))
```
