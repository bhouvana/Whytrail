# whytrail-marshmallow

`why()` on a `marshmallow.ValidationError` shows one step per failing
field instead of the schema's own nested `messages` dict.

```python
try:
    UserSchema().load({"name": "a", "age": "not a number", "email": "bad"})
except marshmallow.ValidationError as exc:
    print(whytrail.why(exc))
```

```
why(2 field(s) failed validation):
  == 2 field(s) failed validation
  == field 'age': Not a valid integer.
  == field 'email': Not a valid email address.
```
