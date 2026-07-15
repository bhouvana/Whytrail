# whytrail-rq

Logs a `whytrail` explanation -- including the failing job's arguments -- on
every RQ job failure.

```python
from rq import Worker
import whytrail_rq

worker = Worker(["default"], connection=redis_conn)
whytrail_rq.install(worker)
worker.work()
```

Job arguments are redacted by default, the same posture as every other
integration in this ecosystem (`whytrail-celery` in particular): a job
payload can carry a customer record or a token just as easily as a stack
frame's locals can.

```python
whytrail_rq.install(worker, log_locals=True)  # opt in explicitly if your log destination is safe for that
```
