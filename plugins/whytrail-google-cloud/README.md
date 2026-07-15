# whytrail-google-cloud

`why()` on a `google.api_core.exceptions.GoogleAPICallError` (`NotFound`,
`PermissionDenied`, `AlreadyExists`, ...) shows the status code, reason,
and message. Registered against the shared base every google-cloud-*
client library (storage, bigquery, pubsub, firestore, ...) raises from,
so one plugin covers the whole family.

```python
try:
    bucket.get_blob("missing.txt")
except google.api_core.exceptions.NotFound as exc:
    print(whytrail.why(exc))
```

`.details` (extra, more open-ended error detail) goes through the
redactable `locals` mechanism used throughout this ecosystem (ADR 0002 §3
item 5).
