from __future__ import annotations

from whytrail.core.explanation import Explanation, ExplanationStep
from whytrail.core.node import Confidence, Edge, EdgeKind, Node, NodeKind


def test_unknown_explanation_is_honest_not_fabricated():
    explanation = Explanation(subject="x", steps=[], tracked=False)
    assert explanation.known is False
    assert explanation.confidence == Confidence.UNKNOWN.value
    assert "unknown" in explanation.text
    assert "no provenance captured" in explanation.text


def test_known_explanation_confidence_is_the_weakest_link():
    steps = [
        ExplanationStep(description="a", confidence=Confidence.EXPLICIT.value),
        ExplanationStep(description="b", confidence=Confidence.INFERRED.value),
    ]
    explanation = Explanation(subject="x", steps=steps, tracked=True)
    assert explanation.known is True
    assert explanation.confidence == Confidence.INFERRED.value


def test_text_includes_every_step():
    steps = [
        ExplanationStep(description="root cause", confidence=Confidence.EXPLICIT.value, location="a.py:1"),
        ExplanationStep(description="final effect", confidence=Confidence.INFERRED.value, location="b.py:2"),
    ]
    explanation = Explanation(subject="boom", steps=steps, tracked=True)
    text = explanation.text
    assert "root cause" in text
    assert "final effect" in text
    assert "a.py:1" in text
    assert "b.py:2" in text


def test_str_matches_text():
    explanation = Explanation(subject="x", steps=[], tracked=False)
    assert str(explanation) == explanation.text


def test_json_round_trips_structure():
    steps = [ExplanationStep(description="a", confidence=Confidence.EXPLICIT.value, location="a.py:1")]
    explanation = Explanation(subject="x", steps=steps, tracked=True)
    payload = explanation.json()
    assert payload["subject"] == "x"
    assert payload["known"] is True
    assert payload["steps"][0]["description"] == "a"
    assert payload["steps"][0]["confidence_label"] == "explicit"


def test_graph_mermaid_for_untracked_subject():
    explanation = Explanation(subject="x", steps=[], tracked=False)
    output = explanation.graph()
    assert output.startswith("graph TD")
    assert "no provenance captured" in output


def test_graph_mermaid_renders_nodes_and_edges():
    a = Node.create(NodeKind.VALUE, "a")
    b = Node.create(NodeKind.VALUE, "b")
    edge = Edge(source=a.id, target=b.id, kind=EdgeKind.DERIVED_FROM)
    explanation = Explanation(subject="b", steps=[], tracked=True, nodes=[a, b], edges=[edge])
    output = explanation.graph()
    assert f"N{a.id}" in output
    assert f"N{b.id}" in output
    assert "derived_from" in output


def test_graph_mermaid_escapes_quotes_in_labels():
    node = Node.create(NodeKind.VALUE, 'has "quotes" in it')
    explanation = Explanation(subject="x", steps=[], tracked=True, nodes=[node], edges=[])
    output = explanation.graph()
    label_line = next(line for line in output.splitlines() if f"N{node.id}" in line)
    # exactly the two quotes delimiting the mermaid node label survive;
    # the quotes that were part of the original label got escaped away
    assert label_line.count('"') == 2
    assert "'quotes'" in label_line


def test_plain_text_unknown_matches_text_message():
    explanation = Explanation(subject="3.14", steps=[], tracked=False)
    assert "No explanation available for 3.14" in explanation.plain_text
    assert "never tracked" in explanation.plain_text


def test_plain_text_glosses_known_exception_types():
    steps = [
        ExplanationStep(
            description="KeyError: 'SUMMER'",
            confidence=Confidence.EXPLICIT.value,
            location="pricing.py:31, in apply_discount",
            kind="exception",
        )
    ]
    explanation = Explanation(subject="KeyError: 'SUMMER'", steps=steps, tracked=True)
    text = explanation.plain_text
    assert "tried to look up something that wasn't there" in text
    assert "'SUMMER'" in text
    assert "in apply_discount(), line 31 of pricing.py" in text
    # the real path is dropped in favor of just the filename
    assert "pricing.py:31" not in text


def test_plain_text_includes_fix_suggestion_for_known_exception_types():
    steps = [ExplanationStep(description="KeyError: 'SUMMER'", confidence=1.0, kind="exception")]
    explanation = Explanation(subject="x", steps=steps, tracked=True)
    text = explanation.plain_text
    assert "How to avoid this:" in text
    assert "d.get(key, default)" in text


def test_plain_text_omits_fix_line_for_unglossed_exception_type():
    # no guidance for a type outside the table -- absence, not a guess.
    steps = [ExplanationStep(description="MyCustomError: odd", confidence=1.0, kind="exception")]
    explanation = Explanation(subject="x", steps=steps, tracked=True)
    assert "How to avoid this:" not in explanation.plain_text


def test_plain_text_omits_fix_line_for_non_exception_steps():
    steps = [ExplanationStep(description="value: raw CSV row", confidence=1.0, kind="value")]
    explanation = Explanation(subject="x", steps=steps, tracked=True)
    assert "How to avoid this:" not in explanation.plain_text


def test_json_includes_suggestion_field():
    known_type_step = ExplanationStep(description="KeyError: 'x'", confidence=1.0, kind="exception")
    unknown_type_step = ExplanationStep(description="MyCustomError: odd", confidence=1.0, kind="exception")
    explanation = Explanation(subject="x", steps=[known_type_step, unknown_type_step], tracked=True)
    payload = explanation.json()
    assert payload["steps"][0]["suggestion"] is not None
    assert "d.get(key, default)" in payload["steps"][0]["suggestion"]
    assert payload["steps"][1]["suggestion"] is None


def test_plain_text_falls_back_for_unglossed_exception_type():
    # MyCustomError isn't in the gloss table -- must not invent a
    # description for it (ADR §11 applies to prose too), just keep the
    # exception's own message as-is.
    steps = [ExplanationStep(description="MyCustomError: something odd", confidence=1.0, kind="exception")]
    explanation = Explanation(subject="x", steps=steps, tracked=True)
    assert "MyCustomError: something odd" in explanation.plain_text


def test_plain_text_uses_non_exception_descriptions_as_is():
    # tracked-value and plugin-authored steps are already free-form
    # prose; plain_text shouldn't try to reparse them.
    steps = [ExplanationStep(description="value: raw CSV row", confidence=1.0, kind="value")]
    explanation = Explanation(subject="12.5", steps=steps, tracked=True)
    assert "value: raw CSV row" in explanation.plain_text


def test_plain_text_notes_non_explicit_confidence():
    explicit_step = ExplanationStep(description="a: explicit one", confidence=Confidence.EXPLICIT.value, kind="exception")
    inferred_step = ExplanationStep(description="b: inferred one", confidence=Confidence.INFERRED.value, kind="exception")
    heuristic_step = ExplanationStep(description="c: heuristic one", confidence=Confidence.HEURISTIC.value, kind="exception")
    explanation = Explanation(subject="x", steps=[explicit_step, inferred_step, heuristic_step], tracked=True)
    text = explanation.plain_text
    lines = text.splitlines()
    explicit_line = next(l for l in lines if "explicit one" in l)
    inferred_line = next(l for l in lines if "inferred one" in l)
    heuristic_line = next(l for l in lines if "heuristic one" in l)
    assert "(" not in explicit_line.split("--")[0]  # no confidence hedge for explicit
    assert "inferred from context" in inferred_line
    assert "best guess" in heuristic_line


def test_plain_text_includes_locals_in_plain_phrasing():
    steps = [
        ExplanationStep(
            description="ValueError: bad",
            confidence=1.0,
            kind="exception",
            locals={"region": "'EU'", "table": "{}"},
        )
    ]
    explanation = Explanation(subject="x", steps=steps, tracked=True)
    text = explanation.plain_text
    assert "region was 'EU'" in text
    assert "table was {}" in text


def test_plain_text_respects_redaction():
    # redacted() only strips `locals` (never `description`, consistent
    # with .text) -- so the "At that point: ..." line disappears
    # entirely after redaction, the same way it does for .text.
    steps = [
        ExplanationStep(
            description="ValueError: bad input",
            confidence=1.0,
            kind="exception",
            locals={"token": "'abc123-secret'"},
        )
    ]
    explanation = Explanation(subject="x", steps=steps, tracked=True)
    assert "abc123-secret" in explanation.plain_text
    assert "abc123-secret" not in explanation.redacted().plain_text
    assert "At that point" not in explanation.redacted().plain_text


def test_rich_requires_extra_or_renders(monkeypatch):
    explanation = Explanation(subject="x", steps=[], tracked=False)
    try:
        import rich  # noqa: F401
    except ImportError:
        import pytest

        with pytest.raises(ImportError):
            explanation.rich()
    else:
        tree = explanation.rich()
        assert tree is not None
