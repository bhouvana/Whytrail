from __future__ import annotations

import whytrail
from whytrail import propagation


def test_inject_extract_round_trip():
    with whytrail.trace():
        price = whytrail.track(12.5, label="local price")
        headers: dict[str, str] = {}
        propagation.inject(headers, obj=price)

    assert propagation.HEADER_NAME in headers
    context = propagation.extract(headers)
    assert context is not None
    assert context.node_label == "local price"
    assert context.node_id is not None


def test_extract_on_carrier_without_header_returns_none():
    assert propagation.extract({}) is None


def test_extract_on_garbage_value_returns_none():
    assert propagation.extract({propagation.HEADER_NAME: "not-a-valid-context"}) is None


def test_inject_without_a_tracked_object_still_produces_a_context():
    headers: dict[str, str] = {}
    propagation.inject(headers)
    context = propagation.extract(headers)
    assert context is not None
    assert context.node_id is None


def test_continue_trace_links_into_local_provenance():
    with whytrail.trace():
        upstream = whytrail.track("order-42", label="incoming order id")
        headers: dict[str, str] = {}
        propagation.inject(headers, obj=upstream)

    # simulate a second process/request receiving `headers`
    with whytrail.trace():
        context = propagation.extract(headers)
        sentinel = propagation.continue_trace(context, label="received order request")
        total = whytrail.track(99.0, derived_from=sentinel, label="computed total")

    explanation = whytrail.why(total)
    assert "received order request" in explanation.text


def test_encode_decode_preserves_labels_with_special_characters():
    context = propagation.PropagationContext(trace_id="abc123", node_id=7, node_label="a:weird/label with spaces")
    round_tripped = propagation.PropagationContext.decode(context.encode())
    assert round_tripped == context
