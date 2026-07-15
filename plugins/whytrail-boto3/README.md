# whytrail-boto3

`why()` on a `botocore.exceptions.ClientError` (or any of its
dynamically-generated per-service subclasses -- `NoSuchKey`,
`AccessDenied`, `ThrottlingException`, ...) shows AWS's own structured
error response instead of botocore's single-line summary.

```python
try:
    s3.get_object(Bucket="my-bucket", Key="missing.txt")
except botocore.exceptions.ClientError as exc:
    print(whytrail.why(exc))
```

```
why(GetObject: NoSuchKey):
  == GetObject failed: NoSuchKey -- The specified key does not exist.
  == HTTP 404, request id ABCD1234
```

Registered against the base `ClientError`, so it resolves for every
service's dynamically generated error subclass via whytrail's MRO walk --
no per-service error vocabulary needed.
