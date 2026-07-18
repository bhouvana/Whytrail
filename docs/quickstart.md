# Quickstart

Fifteen minutes from `pip install` to using whytrail for real. Every
command and output block below was actually run against this version
of the codebase -- copy-paste them and you should see the same thing.

## 1. Install

```bash
pip install whytrail
```

Zero required dependencies -- this installs only `whytrail` itself.
Everything below that needs an extra (`rich`, `cli`, a specific
integration) says so.

## 2. See it in 10 seconds, zero code

```bash
whytrail demo
```

```
A real exception, explained with zero setup -- this is why(exc):

why(KeyError: 'SUMMER'):
  [explicit] ValueError: discount code table missing region 'EU'  [<whytrail demo>:4, in load_codes]
      locals: region='EU', table={}
  [explicit] which explicitly caused KeyError: 'SUMMER'  [<whytrail demo>:11, in apply_discount]
      locals: price=12.5, code='SUMMER'

That's a Tier 1 answer: zero config, reconstructed entirely from data
CPython already retains for every exception (__traceback__, __cause__,
__context__). Add this near the top of your own program and every
uncaught exception shows this automatically, not just this demo:

    import whytrail
    whytrail.install()
```

No script to write -- `whytrail demo` really raises the exception shown
and really runs `why()` on it. `pip install whytrail[rich]` renders it
as a panel/tree instead of plain text (`whytrail demo --plain` forces
plain text either way). The next step shows how to get this
automatically on every exception in your own program, not just this one.

## 3. See it immediately

```python
import whytrail
whytrail.install()
```

Two lines, anywhere near the top of your program. From then on, every
uncaught exception -- main thread, a background thread, or the
interactive REPL -- prints the causal chain first, then the original
traceback, unchanged (nothing is removed, only added). This is the
fastest way to see what the rest of this page explains in detail; the
README's own opening section has a full worked example with real
output. `examples/ex_install_hook.py` is a runnable copy of it.

## 4. Tier 1: explain an exception, zero setup

Save this as `crash.py`:

```python
def load_codes(region):
    table = {}
    if region not in table:
        raise ValueError(f"discount code table missing region {region!r}")
    return table

def apply_discount(price, code):
    try:
        load_codes("EU")
    except ValueError as exc:
        raise KeyError(code) from exc

apply_discount(12.5, "SUMMER")
```

Run it two ways. Directly, you get a normal Python traceback. Through
whytrail's CLI (`pip install whytrail[cli]`), you get the causal chain
instead:

```bash
$ whytrail run crash.py
why(KeyError: 'SUMMER'):
  [explicit] ValueError: discount code table missing region 'EU'  [crash.py:4, in load_codes]
      locals: region='EU', table={}
  [explicit] which explicitly caused KeyError: 'SUMMER'  [crash.py:11, in apply_discount]
      locals: price=12.5, code='SUMMER'
```

Root cause first, ending at the exception you actually caught. No
`trace()` scope, no `track()` call, no configuration -- this comes
entirely from `__traceback__`/`__cause__`/`__context__`, data CPython
already keeps. This is why it's called Tier 1: it's the zero-cost
default every whytrail install gets for free.

In your own code (not through the CLI), the same thing is one call:

```python
import whytrail

try:
    apply_discount(12.5, "SUMMER")
except KeyError as exc:
    print(whytrail.why(exc))
```

## 5. Tier 2: track a value, not just an exception

Tier 1 only works on exceptions. For "why does this *value* look like
this" -- no exception involved -- opt into a small provenance graph
with `track()`:

```python
import whytrail

with whytrail.trace():
    raw = whytrail.track({"price": "12.50"}, label="raw CSV row")
    price = whytrail.track(float(raw["price"]), derived_from=raw)

print(whytrail.why(price))
```

```
why(12.5):
  [explicit] value: raw CSV row  [...]
  [explicit] value: 12.5  [...]
```

Outside a `with whytrail.trace():` block, `track()` is a complete
no-op (not even a graph write) -- this is the "no overhead when
unused" promise, not just a description of it. Something that was
never tracked gets an honest `unknown`, never a guessed-at answer:

```python
>>> whytrail.why(3.14).known
False
```

## 6. Reading the output

Every step carries a confidence marker: `[explicit]` (stated directly
by the data -- a `raise ... from ...`, a `track()` call),
`[inferred]`, or `[heuristic]`. Nothing is ever presented more
confidently than it was actually captured.

Four renderings of the same `Explanation`, pick whichever fits where
you're using it:

| Call | Output |
|---|---|
| `explanation.text` | The terse `[confidence] description` format above (the default) |
| `explanation.plain_text` | The same facts as prose, for someone who doesn't read tracebacks for a living |
| `explanation.json()` | A dict -- `subject`, `steps`, `confidence`, each step's `suggestion` if one exists |
| `explanation.graph()` | A Mermaid flowchart of the full causal graph, not just the summarized path |
| `explanation.rich()` | A `rich.tree.Tree` (needs `pip install whytrail[rich]`) |

## 7. Config-value provenance

Not just exceptions and tracked values -- `whytrail.config.env()`
answers "where did this setting come from" the same way, built on the
same graph:

```python
import whytrail
import whytrail.config

with whytrail.trace():
    timeout = whytrail.config.env("TIMEOUT", 30, cast=int)

print(whytrail.why(timeout))
```

```
why(30):
  [explicit] external: default value for 'TIMEOUT' (checked the environment, not found)
  [explicit] value: TIMEOUT=30
```

See [`docs/explanation-engine.md`](explanation-engine.md) for how this
fits together with `track()` under one general model, and what it
would take to add a similar producer of your own.

## 8. A real integration

63 libraries already have an integration bundled as an extra of this
same package -- see the full table in the [README](../README.md#ecosystem).
Installing one is enough; nothing else to configure:

```bash
pip install whytrail[requests]
```

```python
import requests
import whytrail

try:
    requests.get("http://this-host-does-not-resolve.invalid/", timeout=2).raise_for_status()
except requests.exceptions.RequestException as exc:
    print(whytrail.why(exc))
```

```
why(...):
  [explicit] GET http://this-host-does-not-resolve.invalid/ was sent
  [explicit] raised as ConnectionError: ...
```

The method and URL step comes from `whytrail-requests`, not Tier 1 --
a bare traceback only shows `raise_for_status()`'s own generic
message.

Run `whytrail plugins` any time to see which of the 63 are actually
active in your current environment -- what's installed vs. what would
need an extra.

## 9. Where to go next

- **Writing your own plugin**: [`docs/plugin-guide.md`](plugin-guide.md)
  -- a working example in under 20 minutes.
- **How the pieces fit together**: [`docs/explanation-engine.md`](explanation-engine.md)
  -- producers, consumers, traversal, extension points ranked by risk.
- **What's actually stable pre-1.0**: [`docs/api-stability.md`](api-stability.md).
- **Framework examples**: [`examples/`](../examples/) -- FastAPI, Flask,
  Django, pytest, and a plain data-pipeline walkthrough, all runnable
  as written.
