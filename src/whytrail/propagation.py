"""Cross-process propagation context (ADR §08, §14 -- the buildable
slice of v3.0).

What this is: a way to carry "which local causal chain led to this
outbound call" across a process boundary, shaped the same way
OpenTelemetry's context propagators work -- inject into outbound
headers, extract on the inbound side.

What this deliberately is NOT: a distributed provenance graph. There
is no transport, no remote graph store, no merge step here -- building
those for real needs a network service and a storage backend, which is
infrastructure, not a library feature, and was called out of scope in
the architecture report this was built from. What IS real: the
receiving process can record "this local chain continues a remote
one, trace_id=X, upstream node=Y" as an honestly-labeled external
node, rather than silently losing the cross-process link entirely or
pretending to have the upstream graph when it doesn't.
"""

from __future__ import annotations

import dataclasses
import typing as t
import urllib.parse
import uuid

from .core.node import NodeKind
from .runtime.context import active_graph

HEADER_NAME = "whytrail-trace"


@dataclasses.dataclass(frozen=True, slots=True)
class PropagationContext:
    trace_id: str
    node_id: int | None
    node_label: str | None

    def encode(self) -> str:
        label = urllib.parse.quote(self.node_label or "", safe="")
        node_id = "" if self.node_id is None else str(self.node_id)
        return f"{self.trace_id}:{node_id}:{label}"

    @classmethod
    def decode(cls, value: str) -> "PropagationContext | None":
        parts = value.split(":", 2)
        if len(parts) != 3:
            return None
        trace_id, node_id_raw, label_raw = parts
        if not trace_id:
            return None
        node_id = int(node_id_raw) if node_id_raw.isdigit() else None
        label = urllib.parse.unquote(label_raw) or None
        return cls(trace_id=trace_id, node_id=node_id, node_label=label)


def inject(carrier: dict[str, str], *, obj: t.Any = None, trace_id: str | None = None) -> dict[str, str]:
    """Attach the current causal context to an outbound carrier
    (typically HTTP headers) before a cross-process call.

        headers = {}
        whytrail.propagation.inject(headers, obj=price)
        requests.post(url, json=payload, headers=headers)
    """
    graph = active_graph()
    node = graph.node_for(obj) if obj is not None else None
    context = PropagationContext(
        trace_id=trace_id or uuid.uuid4().hex,
        node_id=node.id if node is not None else None,
        node_label=node.label if node is not None else None,
    )
    carrier[HEADER_NAME] = context.encode()
    return carrier


def extract(carrier: dict[str, str]) -> PropagationContext | None:
    """Read back a context injected by a caller. Returns None if the
    carrier has nothing recognizable -- most inbound requests won't
    have come from a whytrail-instrumented caller, and that's a normal,
    unremarkable case, not an error."""
    value = carrier.get(HEADER_NAME)
    if not value:
        return None
    return PropagationContext.decode(value)


def continue_trace(context: PropagationContext, *, label: str | None = None) -> t.Any:
    """On the receiving side: record an honestly-labeled external node
    marking where a remote causal chain re-enters local tracking, and
    return a sentinel object that subsequent track()/tracked() calls
    can pass as derived_from to link into it. The actual upstream
    graph is not available here -- that's the real distributed-tracing
    problem this module does not solve (see module docstring).
    """
    graph = active_graph()
    sentinel = object()
    description = label or f"upstream call (trace {context.trace_id[:8]}, remote node {context.node_label!r})"
    graph.add_node(
        NodeKind.EXTERNAL,
        description,
        obj=sentinel,
        metadata={"trace_id": context.trace_id, "upstream_node_id": context.node_id},
    )
    return sentinel
