"""Validates whytrail-langchain against real LangChain Expression
Language (LCEL) chains built from RunnableLambda -- no API keys or
network calls needed, but a real callback dispatch through LangChain's
actual runtime, not a hand-constructed event sequence."""

from __future__ import annotations

import pytest

langchain_core = pytest.importorskip("langchain_core")
pytest.importorskip("whytrail.integrations.langchain")

import whytrail  # noqa: E402
from whytrail.integrations.langchain import WhytrailCallbackHandler  # noqa: E402
from langchain_core.runnables import RunnableLambda  # noqa: E402


def _retrieve(q: str) -> dict:
    return {"question": q, "docs": ["doc about refunds"]}


def _answer(d: dict) -> str:
    return f"Based on {d['docs']}, refunds are allowed within 30 days."


def _explode(d: dict) -> str:
    raise ValueError("LLM call failed")


def _make_chain():
    return RunnableLambda(_retrieve).with_config(run_name="retrieve") | RunnableLambda(_answer).with_config(
        run_name="answer"
    )


def test_handler_why_explains_the_chain_output():
    chain = _make_chain()
    handler = WhytrailCallbackHandler()
    with whytrail.trace():
        result = chain.invoke("what is the refund policy", config={"callbacks": [handler]})

    explanation = handler.why()
    assert explanation.known
    assert result in explanation.subject


def test_full_graph_includes_every_step_even_though_text_shows_one_path():
    chain = _make_chain()
    handler = WhytrailCallbackHandler()
    with whytrail.trace():
        chain.invoke("what is the refund policy", config={"callbacks": [handler]})

    explanation = handler.why()
    labels = " ".join(n.label for n in explanation.nodes)
    assert "retrieve" in labels
    assert "answer" in labels
    graph = explanation.graph()
    assert "occurred_during" in graph
    assert "derived_from" in graph


def test_why_on_result_object_also_works_via_identity():
    """Best-effort path: since RunnableLambda passes the answer
    function's return value straight through as the chain's final
    output with no further transformation, object identity survives
    and plain whytrail.why(result) resolves too, not just handler.why()."""
    chain = _make_chain()
    handler = WhytrailCallbackHandler()
    with whytrail.trace():
        result = chain.invoke("what is the refund policy", config={"callbacks": [handler]})

    explanation = whytrail.why(result)
    assert explanation.known


def test_chain_error_is_still_explained_with_graph_context():
    chain = RunnableLambda(_retrieve).with_config(run_name="retrieve") | RunnableLambda(_explode).with_config(
        run_name="explode"
    )
    handler = WhytrailCallbackHandler()
    with whytrail.trace():
        with pytest.raises(ValueError):
            chain.invoke("what is the refund policy", config={"callbacks": [handler]})

    explanation = handler.why()
    assert explanation.known
    labels = " ".join(n.label for n in explanation.nodes)
    assert "retrieve" in labels


def test_handler_with_no_run_observed_is_honestly_unknown():
    handler = WhytrailCallbackHandler()
    explanation = handler.why()
    assert explanation.known is False
