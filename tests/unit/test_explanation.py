from __future__ import annotations

import pytest

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
    explicit_line = next(line for line in lines if "explicit one" in line)
    inferred_line = next(line for line in lines if "inferred one" in line)
    heuristic_line = next(line for line in lines if "heuristic one" in line)
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
    # redacted() strips `locals` unconditionally, and `description`
    # only for kind == "value" steps (see test_redacted_* below) -- an
    # exception-kind step's description (the message itself) is the
    # explanation, not incidental capture, so it survives redaction.
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


def test_redacted_strips_value_step_descriptions_from_graph_traversal_but_not_exception_ones():
    # nodes= non-empty is what marks this as a graph-traversal answer
    # (_explain_from_graph's territory) rather than a plugin's own
    # Explanation -- see the next test for why that gate matters.
    steps = [
        ExplanationStep(description="value: raw-secret-content", confidence=1.0, kind="value"),
        ExplanationStep(description="ValueError: bad input", confidence=1.0, kind="exception"),
    ]
    nodes = [Node(id=1, kind=NodeKind.VALUE, label="raw-secret-content")]
    explanation = Explanation(subject="x", steps=steps, tracked=True, nodes=nodes, edges=[])
    redacted = explanation.redacted()
    assert redacted.steps[0].description == "value: [redacted]"
    assert redacted.steps[1].description == "ValueError: bad input"  # untouched


def test_redacted_leaves_plugin_authored_value_kind_steps_alone():
    """Regression test: a first version of the fix above redacted any
    step with kind=="value" regardless of where it came from, and
    broke whytrail-pydantic -- its explainer reuses kind="value" for
    an unrelated, already-safe purpose (field name + error type, with
    the actual bad input properly quarantined in `.locals` already,
    per its own module docstring citing ADR 0002 SS3 item 5). A
    plugin-authored Explanation never populates `.nodes` (confirmed:
    no bundled plugin does), so gating on that distinguishes "this
    came from graph traversal" from "this is a plugin's own content"
    without needing to trust `kind` alone."""
    steps = [
        ExplanationStep(
            description="field 'age': value is not a valid integer (int_parsing)",
            confidence=1.0,
            kind="value",
            locals={"input": "'not a number'"},
        ),
    ]
    explanation = Explanation(subject="2 validation errors", steps=steps, tracked=True)  # no nodes=
    redacted = explanation.redacted()
    assert redacted.steps[0].description == "field 'age': value is not a valid integer (int_parsing)"
    assert redacted.steps[0].locals is None  # locals is still stripped unconditionally
    assert redacted.subject == "2 validation errors"  # no nodes -> subject untouched too


def test_redacted_strips_value_node_labels_and_all_node_metadata():
    nodes = [
        Node(id=1, kind=NodeKind.VALUE, label="raw-secret-content", metadata={"note": "also secret"}),
        Node(id=2, kind=NodeKind.EXTERNAL, label="environment variable 'X'", metadata={"note": "not secret"}),
    ]
    explanation = Explanation(subject="x", steps=[], tracked=True, nodes=nodes, edges=[])
    redacted = explanation.redacted()
    assert redacted.nodes[0].label == "[redacted]"
    assert redacted.nodes[0].metadata == {}
    assert redacted.nodes[1].label == "environment variable 'X'"  # not a VALUE node, label untouched
    assert redacted.nodes[1].metadata == {}  # metadata redacted regardless of node kind


def test_redacted_strips_subject_only_when_nodes_are_present():
    # Tier 2 (nodes present): subject = safe_repr(the tracked value) --
    # redact it, the same class of leak as a VALUE node's label.
    tier2 = Explanation(
        subject="'raw-secret-content'",
        steps=[],
        tracked=True,
        nodes=[Node(id=1, kind=NodeKind.VALUE, label="x")],
        edges=[],
    )
    assert tier2.redacted().subject == "[redacted]"

    # Tier 1 (no nodes, ADR 0008): subject is the exception's own
    # type/message -- that *is* the explanation, leave it alone.
    tier1 = Explanation(subject="ValueError: bad input", steps=[], tracked=True)
    assert tier1.redacted().subject == "ValueError: bad input"


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


def test_rich_default_return_type_is_still_a_tree():
    pytest.importorskip("rich")
    from rich.tree import Tree

    explanation = Explanation(subject="x", steps=[], tracked=False)
    assert isinstance(explanation.rich(), Tree)


def test_rich_renders_locals_as_a_table_not_a_flat_string():
    pytest.importorskip("rich")
    from rich.console import Console

    steps = [
        ExplanationStep(
            description="ValueError: bad",
            confidence=1.0,
            kind="exception",
            locals={"region": "'EU'", "table": "{}"},
        )
    ]
    explanation = Explanation(subject="x", steps=steps, tracked=True)
    console = Console(width=80, record=True)
    console.print(explanation.rich())
    output = console.export_text()
    assert "region" in output
    assert "'EU'" in output
    assert "table" in output


def test_rich_location_is_styled_as_a_file_link():
    pytest.importorskip("rich")
    steps = [
        ExplanationStep(
            description="ValueError: bad",
            confidence=1.0,
            location="C:\\project\\app.py:12, in load",
        )
    ]
    explanation = Explanation(subject="x", steps=steps, tracked=True)
    tree = explanation.rich()
    location_text = tree.children[0].label
    span_styles = [str(span.style) for span in location_text.spans]
    assert any("link file://C:\\project\\app.py" in style for style in span_styles)


def test_rich_falls_back_to_plain_text_for_an_unparseable_location():
    pytest.importorskip("rich")
    steps = [ExplanationStep(description="x", confidence=1.0, location="not a real location string")]
    explanation = Explanation(subject="x", steps=steps, tracked=True)
    tree = explanation.rich()  # must not raise
    assert "not a real location string" in str(tree.children[0].label)


def test_rich_panel_true_wraps_the_tree_without_a_duplicate_title():
    pytest.importorskip("rich")
    from rich.panel import Panel
    from rich.tree import Tree

    explanation = Explanation(subject="x", steps=[], tracked=False)
    result = explanation.rich(panel=True)
    assert isinstance(result, Panel)
    assert result.title is None
    assert isinstance(result.renderable, Tree)


def test_repr_html_needs_no_extra():
    """Jupyter display support is pure stdlib -- core's zero-required-
    dependencies contract holds even for this, no rich/IPython import
    anywhere in the implementation."""
    explanation = Explanation(subject="x", steps=[], tracked=False)
    html = explanation._repr_html_()
    assert isinstance(html, str)
    assert "<div" in html


def test_repr_html_shows_unknown_honestly():
    explanation = Explanation(subject="x", steps=[], tracked=False)
    html = explanation._repr_html_()
    assert "unknown" in html
    assert "no provenance captured" in html


def test_repr_html_includes_each_step_and_escapes_html_special_characters():
    steps = [
        ExplanationStep(description="<script>alert(1)</script>", confidence=1.0, location="a.py:1"),
    ]
    explanation = Explanation(subject="x", steps=steps, tracked=True)
    html = explanation._repr_html_()
    assert "<script>alert(1)</script>" not in html  # must be escaped, not injected raw
    assert "&lt;script&gt;" in html
    assert "a.py:1" in html


def test_repr_html_includes_locals():
    steps = [
        ExplanationStep(
            description="ValueError: bad",
            confidence=1.0,
            kind="exception",
            locals={"region": "'EU'"},
        )
    ]
    explanation = Explanation(subject="x", steps=steps, tracked=True)
    html = explanation._repr_html_()
    assert "region" in html
    assert "&#x27;EU&#x27;" in html


def test_ipython_html_formatter_picks_up_repr_html():
    pytest.importorskip("IPython")
    from IPython.core.formatters import HTMLFormatter

    explanation = Explanation(subject="x", steps=[], tracked=False)
    result = HTMLFormatter()(explanation)
    assert result is not None
    assert "<div" in result


def test_from_json_round_trips_text_exactly():
    steps = [
        ExplanationStep(description="root cause", confidence=1.0, location="a.py:1", kind="value"),
        ExplanationStep(
            description="final effect", confidence=0.7, location="b.py:2", kind="value", locals={"x": "1"}
        ),
    ]
    original = Explanation(subject="boom", steps=steps, tracked=True)
    restored = Explanation.from_json(original.json())
    assert restored.text == original.text
    assert restored.known == original.known
    assert restored.confidence == original.confidence


def test_from_json_on_unknown_explanation():
    original = Explanation(subject="x", steps=[], tracked=False)
    restored = Explanation.from_json(original.json())
    assert restored.known is False
    assert restored.text == original.text


def test_from_json_does_not_fabricate_nodes_or_edges():
    """.json() never serialized nodes/edges -- from_json() must not
    pretend they survived the round trip."""
    steps = [ExplanationStep(description="x", confidence=1.0)]
    original = Explanation(
        subject="x",
        steps=steps,
        tracked=True,
        nodes=[Node(id=1, kind=NodeKind.VALUE, label="x")],
        edges=[],
    )
    restored = Explanation.from_json(original.json())
    assert restored.nodes == []
    assert "no provenance captured" in restored.graph()
