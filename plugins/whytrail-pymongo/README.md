# whytrail-pymongo

`why()` on a `pymongo.errors.PyMongoError` (`OperationFailure`,
`DuplicateKeyError`, ...) shows MongoDB's structured error code, with
the driver's own message and `.details` available via the redactable
`locals` mechanism used throughout this ecosystem (ADR 0002 §3 item 5).

```python
try:
    users.insert_one({"email": "a@example.com"})
except pymongo.errors.DuplicateKeyError as exc:
    print(whytrail.why(exc))
```

**Unlike this ecosystem's other DB-driver plugins, no part of pymongo's
own message text is ever used in `description`.** pymongo bakes
`.details` straight into the exception's `args[0]` at construction time,
and MongoDB's own error text typically embeds the offending value inline
(`dup key: { email: "a@example.com" }`) -- there's no driver-provided
string here that's reliably value-free. `description` is built only from
the exception type and numeric code; everything else goes through
`locals`, so `Explanation.redacted()` reliably strips it. See the module
docstring in `whytrail_pymongo` and
`tests/plugin_contract/test_pymongo_plugin.py` for how this was verified,
not assumed.
