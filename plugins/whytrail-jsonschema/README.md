# whytrail-jsonschema

`why()` on a `jsonschema.ValidationError` shows the document path and
which schema rule failed, without the offending value baked into
unredactable text.

```python
try:
    jsonschema.validate(payload, schema)
except jsonschema.ValidationError as exc:
    print(whytrail.why(exc))
```

```
why(age: failed 'type'):
  == age: failed 'type' (expected 'integer')
      locals: message="'not a number' is not of type 'integer'", instance="'not a number'"
```

**Neither `.message` nor `.instance` is used in `description`.**
jsonschema's own `.message` text embeds the offending value directly
("'not a number' is not of type 'integer'") -- there's no
driver-provided string here that's safe to use as-is, the same finding
`whytrail-pymongo` made for MongoDB's error text. Both go through the
redactable `locals` mechanism (ADR 0002 §3 item 5); call `.redacted()`
before sending an `Explanation` anywhere off-box.
