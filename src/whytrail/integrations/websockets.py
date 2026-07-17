"""whytrail plugin for the websockets library (ADR 0003).

`websockets.exceptions.ConnectionClosed` (covering `ConnectionClosedOK`/
`ConnectionClosedError`) carries the WebSocket close frame's `.code`
(a stable, closed taxonomy per RFC 6455 -- 1000 normal, 1011 internal
error, ...) and `.reason` (free text set by whichever side closed the
connection), plus `.rcvd`/`.sent` showing which side actually sent a
close frame -- useful for diagnosing an asymmetric close (e.g. "we
never got a close frame back"). `str(exc)` folds all of this into one
prose sentence that's awkward to branch on programmatically.

`.reason` goes through `locals`, not `description` (ADR 0002 §3 item
5): a server's close reason routinely echoes back the specific error
that caused the disconnect (a failed query, an invalid token), whereas
`.code` is a small closed set of protocol-level integers, safe in
`description`.

Reads `.rcvd.code`/`.rcvd.reason` (the actual close frame received),
not the deprecated `exc.code`/`exc.reason` properties (deprecated
since websockets 13.1) -- confirmed directly, not assumed from a
changelog: constructing a real `ConnectionClosedError` and reading
`.code` triggers a live `DeprecationWarning`. Falls back to the
deprecated accessors only when `.rcvd` is `None` (the peer never sent
a close frame at all), which is still the only way to get a code in
that case.
"""

from __future__ import annotations

import websockets.exceptions

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_connection_closed(exc: "websockets.exceptions.ConnectionClosed") -> Explanation:
    # exc.code/.reason are deprecated since websockets 13.1 in favor of
    # exc.rcvd (the actual close frame received, or None if the peer
    # never sent one) -- fall back to the deprecated accessors only if
    # .rcvd isn't available, for compatibility with older floors.
    rcvd = getattr(exc, "rcvd", None)
    if rcvd is not None:
        code, reason = rcvd.code, rcvd.reason
    else:
        code, reason = exc.code, exc.reason
    steps = [
        ExplanationStep(
            description=f"{type(exc).__name__}: code={code}",
            confidence=Confidence.EXPLICIT.value,
            kind="external",
        )
    ]
    if reason:
        steps.append(
            ExplanationStep(
                description="close reason",
                confidence=Confidence.EXPLICIT.value,
                kind="external",
                locals={"reason": reason},
            )
        )
    return Explanation(subject=f"{type(exc).__name__}: code={code}", steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(websockets.exceptions.ConnectionClosed, _explain_connection_closed)
