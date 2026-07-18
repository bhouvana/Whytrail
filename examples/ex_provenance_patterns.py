"""Four provenance patterns, all built from existing primitives
(`track()`, `@tracked`, `trace()`, `why()`, `whytrail.config.env()`) --
no new vocabulary. See `docs/adr/0011-provenance-vocabulary-is-already-sufficient.md`
for the analysis this demonstrates.

Run: python examples/ex_provenance_patterns.py
Needs: nothing extra -- built entirely on core whytrail.
"""

from __future__ import annotations

import whytrail
import whytrail.config


def transformation_sequence() -> None:
    """"A was validated, then normalized, then clamped" -- a named
    sequence of operations, not just "A became B." Decorating each
    step with @tracked is enough; the call node's label is the
    function's own name."""

    @whytrail.tracked
    def validate(x: str) -> str:
        return x

    @whytrail.tracked
    def normalize(x: str) -> str:
        return x.strip().lower()

    @whytrail.tracked
    def clamp(x: str) -> str:
        return x[:5]

    with whytrail.trace():
        step1 = validate("  Hello World  ")
        step2 = normalize(step1)
        final = clamp(step2)

    print("=== Transformation sequence ===")
    print(whytrail.why(final).text)
    print()


def branching() -> None:
    """One config value affecting two independent downstream systems.
    Each system's own why() correctly traces back to the shared
    source -- there's just no single "what does this affect" query
    yet (see the ADR: named, deliberately deferred, roadmap Phase F)."""
    with whytrail.trace():
        timeout = whytrail.track(30, label="config.timeout")
        http_client = whytrail.track({"timeout": 30}, derived_from=timeout, label="HTTP client config")
        retry_policy = whytrail.track({"max_wait": 30}, derived_from=timeout, label="Retry policy")

    print("=== Branching: one value, two independent consumers ===")
    print(whytrail.why(http_client).text)
    print()
    print(whytrail.why(retry_policy).text)
    print()


def merge_and_override() -> None:
    """"Why did the final value win, not just where it came from" --
    whytrail.config.env() already names why the losing sources didn't
    apply, across all three priority levels."""
    dotenv = {"REGION": "eu-west-1"}

    print("=== Merge/override: env > dotenv > default ===")
    with whytrail.trace():
        # REGION isn't set in the real environment for this demo, so
        # it falls through to dotenv -- the explanation says why.
        region = whytrail.config.env("REGION", "us-east-1", dotenv=dotenv)
    print(whytrail.why(region).text)
    print()


def composition_algebra() -> None:
    """The example that motivated this whole file: a value composed
    from two *independent* provenances (two separately-resolved config
    values) should be explained as a real join, not two disconnected
    facts. Already true: @tracked links every argument's own node to
    the call node, and the existing "+N other paths converge here"
    note (built for an unrelated diamond case) fires here too."""

    class Policy:
        def __init__(self, timeout: int, retries: int) -> None:
            self.timeout = timeout
            self.retries = retries

    @whytrail.tracked
    def make_policy(timeout: int, retries: int) -> Policy:
        return Policy(timeout, retries)

    with whytrail.trace():
        timeout = whytrail.config.env("DEMO_TIMEOUT", 30, cast=int)
        retries = whytrail.config.env("DEMO_RETRIES", 3, cast=int)
        policy = make_policy(timeout, retries)

    print("=== Composition: a value derived from two independent provenances ===")
    print(whytrail.why(policy).text)
    print()
    print("Full join, both branches (Explanation.graph()):")
    print(whytrail.why(policy).graph())


if __name__ == "__main__":
    transformation_sequence()
    branching()
    merge_and_override()
    composition_algebra()
