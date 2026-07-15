# whytrail-celery

Logs a `whytrail` explanation -- including the failing task's arguments --
on every Celery `task_failure`.

```python
import whytrail_celery
whytrail_celery.install()
```

Task arguments are redacted by default, the same posture as every other
integration in this ecosystem: a task payload can carry a customer record
or a token just as easily as a stack frame's locals can.

```python
whytrail_celery.install(log_locals=True)  # opt in explicitly if your log destination is safe for that
```
