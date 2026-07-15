"""whytrail plugin for paramiko (ADR 0003).

`BadHostKeyException` (raised when a server's host key doesn't match
what's known/expected -- the classic "man in the middle or the host
was reinstalled" case) carries the actual key objects involved, which
a bare traceback collapses into an unhelpful one-liner. Shown as
fingerprints (the standard, safe way to identify an SSH key -- the
same hex string `ssh-keygen -lf` prints), never the raw key material:
a public key's fingerprint isn't sensitive the way a private key or a
password would be, so this doesn't need the locals/redaction treatment
whytrail-cryptography-adjacent data would.

`AuthenticationException` carries no structured fields beyond its
message -- registered anyway (via the shared SSHException base) so
`why()` gives a clean, specific answer instead of falling through to
the generic tier-1 fallback.
"""

from __future__ import annotations

import binascii

import paramiko

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _fingerprint(key: "paramiko.PKey") -> str:
    return f"{key.get_name()} {binascii.hexlify(key.get_fingerprint()).decode()}"


def _explain_bad_host_key(exc: "paramiko.BadHostKeyException") -> Explanation:
    steps = [
        ExplanationStep(
            description=f"{type(exc).__name__}: host key for {exc.hostname!r} didn't match what was expected",
            confidence=Confidence.EXPLICIT.value,
            kind="exception",
        ),
        ExplanationStep(
            description=f"expected {_fingerprint(exc.expected_key)}, got {_fingerprint(exc.key)}",
            confidence=Confidence.EXPLICIT.value,
            kind="value",
        ),
    ]
    subject = f"{type(exc).__name__}: host key mismatch for {exc.hostname!r}"
    return Explanation(subject=subject, steps=steps, tracked=True)


def _explain_ssh_exception(exc: "paramiko.SSHException") -> Explanation:
    steps = [
        ExplanationStep(
            description=f"{type(exc).__name__}: {exc}",
            confidence=Confidence.EXPLICIT.value,
            kind="exception",
        )
    ]
    return Explanation(subject=f"{type(exc).__name__}: {exc}", steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(paramiko.BadHostKeyException, _explain_bad_host_key)
    register_from_plugin(paramiko.SSHException, _explain_ssh_exception)
