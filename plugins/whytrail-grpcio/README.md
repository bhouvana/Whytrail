# whytrail-grpcio

`why()` on a `grpc.RpcError` shows the status code, with server-supplied
`.details()` text available via the redactable `locals` mechanism used
throughout this ecosystem (ADR 0002 §3 item 5) -- `.details()` is
free-form text the server author wrote, and can contain anything.

```python
try:
    stub.GetOrder(request)
except grpc.RpcError as exc:
    print(whytrail.why(exc))
```
