# whytrail-dramatiq

Logs a `whytrail` explanation -- including the failing actor's arguments --
via dramatiq's own `Middleware.after_process_message` hook.

```python
import whytrail_dramatiq

broker = RabbitmqBroker(...)
dramatiq.set_broker(broker)
whytrail_dramatiq.install(broker)
```

Message arguments are redacted by default, the same posture as
`whytrail-celery`/`whytrail-rq`: a message payload can carry a customer
record or a token just as easily as a stack frame's locals can.

```python
whytrail_dramatiq.install(broker, log_locals=True)  # opt in explicitly if your log destination is safe for that
```
