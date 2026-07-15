# whytrail-pandas

`why()` on an untracked `DataFrame`/`Series` gives you a rich diagnostic
of its current state (shape, dtypes, null counts) instead of "unknown."

```python
import pandas as pd
import whytrail

df = pd.read_csv("orders.csv")
print(whytrail.why(df))
```

```
why(DataFrame(1204x6)):
  == DataFrame: 1204 rows x 6 columns
  == columns with null values: discount_code=340/1204, region=12/1204
  == dtypes: order_id=int64, price=float64, discount_code=object, region=object, ...
  == this is a diagnostic of the current state, not provenance -- pandas
      doesn't retain transform history, so whytrail can't say what produced
      this unless it was tracked (whytrail.track() or a @whytrail.tracked
      pipeline step)
```

**Read the last line.** This plugin does not, and cannot, tell you *why*
those 340 rows are missing a discount code -- pandas doesn't retain
transform history. For real provenance, track the pipeline:

```python
@whytrail.tracked
def apply_discounts(df):
    ...

with whytrail.trace():
    result = apply_discounts(df)

print(whytrail.why(result))  # the actual call chain, not the diagnostic
```

Once a DataFrame is tracked, this plugin steps aside automatically and
`why()` returns its real provenance instead of the diagnostic.
