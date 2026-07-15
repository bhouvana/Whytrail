from __future__ import annotations

import sys

import pytest

import whytrail
from whytrail.core.node import Confidence


def test_why_on_plain_exception_has_one_step():
    try:
        raise ValueError("boom")
    except ValueError as exc:
        explanation = whytrail.why(exc)
    assert explanation.known
    assert "ValueError: boom" in explanation.text
    assert len(explanation.steps) == 1
    assert explanation.steps[0].confidence == Confidence.EXPLICIT.value


def test_why_follows_explicit_cause_chain():
    try:
        try:
            raise ValueError("root cause")
        except ValueError as root:
            raise KeyError("surface error") from root
    except KeyError as exc:
        explanation = whytrail.why(exc)

    assert len(explanation.steps) == 2
    assert "ValueError: root cause" in explanation.steps[0].description
    assert "KeyError" in explanation.steps[1].description
    # raise ... from ... is explicit, so the link is full confidence
    assert explanation.steps[1].confidence == Confidence.EXPLICIT.value


def test_why_follows_implicit_context_chain_with_lower_confidence():
    try:
        try:
            raise ValueError("during handling")
        except ValueError:
            raise KeyError("new error")  # no `from` -- implicit chaining
    except KeyError as exc:
        explanation = whytrail.why(exc)

    assert len(explanation.steps) == 2
    assert explanation.steps[1].confidence == Confidence.INFERRED.value


def test_why_respects_raise_from_none_suppression():
    try:
        try:
            raise ValueError("hidden")
        except ValueError:
            raise KeyError("visible") from None
    except KeyError as exc:
        explanation = whytrail.why(exc)

    assert len(explanation.steps) == 1
    assert "visible" in explanation.steps[0].description


def test_why_captures_locals_at_origin_frame():
    def raiser():
        secret_value = "findme"  # noqa: F841
        raise RuntimeError("failure")

    try:
        raiser()
    except RuntimeError as exc:
        explanation = whytrail.why(exc)

    # locals live in their own field, not smashed into description text
    # (ADR 0002 §3 item 5) -- so integrations that export off-box can
    # drop them via Explanation.redacted() without parsing prose.
    assert explanation.steps[0].locals is not None
    assert explanation.steps[0].locals["secret_value"] == "'findme'"
    assert "secret_value" not in explanation.steps[0].description
    # but they still show up in the human-readable .text for local dev
    assert "secret_value='findme'" in explanation.text


def test_explanation_redacted_strips_locals_but_keeps_everything_else():
    def raiser():
        api_key = "sk-super-secret"  # noqa: F841
        raise RuntimeError("failure")

    try:
        raiser()
    except RuntimeError as exc:
        explanation = whytrail.why(exc)

    safe = explanation.redacted()
    assert all(step.locals is None for step in safe.steps)
    assert "api_key" not in safe.text
    assert "sk-super-secret" not in safe.text
    assert "sk-super-secret" not in str(safe.json())
    # everything else survives redaction
    assert safe.subject == explanation.subject
    assert [s.description for s in safe.steps] == [s.description for s in explanation.steps]
    assert [s.location for s in safe.steps] == [s.location for s in explanation.steps]
    # the original Explanation is untouched
    assert explanation.steps[0].locals is not None


def test_why_never_raises_even_on_hostile_object():
    class Hostile:
        def __repr__(self):
            raise RuntimeError("nope")

    # why() must degrade to "unknown" rather than propagate the failure
    explanation = whytrail.why(Hostile())
    assert explanation.known is False


@pytest.mark.skipif(sys.version_info < (3, 11), reason="ExceptionGroup requires Python 3.11+")
def test_why_expands_exception_group_sub_exceptions():
    # ExceptionGroup (asyncio.TaskGroup and friends, PEP 654) bundles
    # multiple *independent* failures into one exception -- without this,
    # why() only saw the group's own generic wrapper message and hid the
    # real sub-exceptions entirely, found by actually raising one, not by
    # reasoning about the type in the abstract.
    try:
        raise ExceptionGroup(  # noqa: F821 - builtin as of 3.11, guarded by skipif above
            "multiple failures",
            [ValueError("task A failed"), KeyError("task B failed")],
        )
    except ExceptionGroup as exc:  # noqa: F821
        explanation = whytrail.why(exc)

    assert len(explanation.steps) == 3  # the group itself, plus both sub-exceptions
    assert "ExceptionGroup" in explanation.steps[0].description
    assert "ValueError: task A failed" in explanation.steps[1].description
    assert "sub-exception 1 of 2" in explanation.steps[1].description
    assert "KeyError" in explanation.steps[2].description
    assert "sub-exception 2 of 2" in explanation.steps[2].description
    # every step is explicit -- these are all directly-known facts, not inferred
    assert all(step.confidence == Confidence.EXPLICIT.value for step in explanation.steps)


@pytest.mark.skipif(sys.version_info < (3, 11), reason="ExceptionGroup requires Python 3.11+")
def test_why_caps_exception_group_expansion_at_max_group_exceptions():
    from whytrail.explainers.builtin import MAX_GROUP_EXCEPTIONS

    sub_exceptions = [ValueError(f"failure {i}") for i in range(MAX_GROUP_EXCEPTIONS + 3)]
    try:
        raise ExceptionGroup("many failures", sub_exceptions)  # noqa: F821
    except ExceptionGroup as exc:  # noqa: F821
        explanation = whytrail.why(exc)

    # group step + capped sub-exceptions + one "N more not shown" step
    assert len(explanation.steps) == 1 + MAX_GROUP_EXCEPTIONS + 1
    assert "more sub-exception" in explanation.steps[-1].description


@pytest.mark.skipif(sys.version_info < (3, 11), reason="ExceptionGroup requires Python 3.11+")
def test_why_plain_text_glosses_exception_group_and_its_sub_exceptions():
    try:
        raise ExceptionGroup("multiple failures", [ValueError("bad input")])  # noqa: F821
    except ExceptionGroup as exc:  # noqa: F821
        explanation = whytrail.why(exc)

    text = explanation.plain_text
    assert "several independent things failed at the same time" in text
    assert "got a value that didn't make sense" in text
