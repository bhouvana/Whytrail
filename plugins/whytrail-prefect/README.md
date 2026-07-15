# whytrail-prefect

Logs a `whytrail` explanation on task/flow failure via Prefect's own
`on_failure` state-change hook.

```python
from prefect import flow, task
from whytrail_prefect import on_failure_hook

@task(on_failure=[on_failure_hook()], retries=0)
def my_task(...):
    ...
```

Unlike `whytrail-celery`/`whytrail-rq`/`whytrail-dramatiq`, this does not capture
task arguments -- Prefect's hook signature doesn't expose bound parameters
directly, and fetching them would mean a network call to Prefect's API
inside a failure handler. Left out rather than built on a shakier
foundation.
