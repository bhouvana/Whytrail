# whytrail-sqlalchemy

`why()` on a `StatementError` (`IntegrityError`, `OperationalError`,
`ProgrammingError`, `DataError`) shows the statement and bound parameters
that caused it, not just the driver's bare message.

```python
try:
    session.commit()
except sqlalchemy.exc.IntegrityError as exc:
    print(whytrail.why(exc))
```

```
why(IntegrityError: UNIQUE constraint failed: users.email):
  == IntegrityError: IntegrityError('UNIQUE constraint failed: users.email')
  == statement: INSERT INTO users (id, email) VALUES (?, ?)
      locals: 0='2', 1="'a@example.com'"
```

Bound parameters are attached via the same `locals` mechanism (and the
same `Explanation.redacted()` opt-out) as tier-1's frame-locals capture --
a parameter set can contain exactly the kind of data that shouldn't cross
a process boundary by default. If you pipe this through `whytrail-sentry`
or `whytrail.otel`, params are redacted unless you explicitly opt in there.
