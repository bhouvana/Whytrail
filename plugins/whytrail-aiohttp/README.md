# whytrail-aiohttp

`why()` on an `aiohttp.ClientResponseError`/`ClientConnectionError` shows
the method, URL, status, and message instead of aiohttp's one-line
summary.

```python
try:
    resp.raise_for_status()
except aiohttp.ClientResponseError as exc:
    print(whytrail.why(exc))
```

Unlike `whytrail-requests`/`whytrail-httpx`, there's no response-body step
here -- aiohttp doesn't keep the body accessible on the exception by the
time `raise_for_status()` raises.
