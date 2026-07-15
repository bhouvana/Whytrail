# whytrail-openai

`why()` on an `openai.APIStatusError` (`RateLimitError`,
`AuthenticationError`, `BadRequestError`, ...) shows the HTTP status,
error code, and request ID instead of the SDK's one-line summary. The
response body -- which can echo back request content -- is redacted by
default via the same `locals`/`Explanation.redacted()` mechanism used
throughout this ecosystem (ADR 0002 §3 item 5).

```python
try:
    client.chat.completions.create(...)
except openai.RateLimitError as exc:
    print(whytrail.why(exc))
```
