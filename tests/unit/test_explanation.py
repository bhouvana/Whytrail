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
