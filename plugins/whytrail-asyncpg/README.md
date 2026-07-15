# whytrail-asyncpg

`why()` on an `asyncpg.PostgresError` (`UniqueViolationError`,
`ForeignKeyViolationError`, ...) shows the SQLSTATE code, table/column/
constraint name, and detail instead of the driver's message alone.
`detail` can echo back an offending row's values, so it goes through the
redactable `locals` mechanism used throughout this ecosystem (ADR 0002 §3
item 5).

```python
try:
    await conn.execute("INSERT INTO users (email) VALUES ($1)", email)
except asyncpg.UniqueViolationError as exc:
    print(whytrail.why(exc))
```
