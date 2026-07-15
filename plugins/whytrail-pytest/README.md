# whytrail-pytest

Attaches a `whytrail` explanation to every failing test's report -- most
useful exactly where a bare traceback is weakest: fixture-heavy failures
where the assertion line doesn't show which fixture value caused it.

Install alongside `pytest`; no configuration needed, it registers itself
via the standard `pytest11` entry point:

```
pip install whytrail-pytest
pytest                       # explanations appear under failing tests
pytest --whytrail-graph        # also include a Mermaid provenance graph
pytest --no-whytrail           # disable
```
