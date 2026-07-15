# whytrail-polars

`why()` on an untracked `DataFrame`/`Series` gives a diagnostic of its
current state (shape, schema, null counts) instead of "unknown" -- same
model as `whytrail-pandas`, verified independently for polars rather than
assumed. Once a frame is tracked (`whytrail.track()` or a `@whytrail.tracked`
pipeline step), this plugin steps aside and `why()` returns its real
provenance instead.

```python
import polars as pl
import whytrail

df = pl.read_csv("orders.csv")
print(whytrail.why(df))
```
