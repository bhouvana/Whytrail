# whytrail-pydantic

`why()` on a `pydantic.ValidationError` shows every field that failed, one
step per field, instead of pydantic's own concatenated wall of text.

```python
try:
    User(name="a", age="not a number", email="bad")
except pydantic.ValidationError as exc:
    print(whytrail.why(exc))
```

```
why(2 validation error(s) for User):
  == 2 validation error(s) for User
  == field 'age': Input should be a valid integer, unable to parse string as an integer (int_parsing)
      locals: input="'not a number'"
  == field 'email': String should match pattern '^[^@]+@[^@]+$' (string_pattern_mismatch)
      locals: input="'bad'"
```

The failing input value for each field is attached via the same `locals`
mechanism (and the same `Explanation.redacted()` opt-out) as everything
else in this ecosystem -- a field that fails validation is disproportionately
likely to be exactly the kind of thing (a password, a token) that
shouldn't cross a process boundary unredacted.
