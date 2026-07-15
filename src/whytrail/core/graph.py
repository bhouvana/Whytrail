"""The provenance graph store (ADR §08, §12).

An append-only, bounded-retention DAG. Nodes never hold a strong reference
to the object they describe -- only an id() and a bounded repr snapshot --
so the graph can never be the reason an object outlives its natural
lifetime. When a tracked object is garbage collected its node is
tombstoned rather than silently disappearing (ADR §11's honesty
principle applied to memory management).
"""

from __future__ import annotations

import collections
import threading
import weakref
import typing as t

from .node import Confidence, Edge, EdgeKind, Node, NodeKind

DEFAULT_MAX_NODES = 10_000


class ProvenanceGraph:
    def __init__(self, *, max_nodes: int = DEFAULT_MAX_NODES) -> None:
        self.max_nodes = max_nodes
        self._lock = threading.RLock()
        self._nodes: "collections.OrderedDict[int, Node]" = collections.OrderedDict()
        self._edges: list[Edge] = []
        self._edges_by_target: dict[int, list[Edge]] = collections.defaultdict(list)
        self._edges_by_source: dict[int, list[Edge]] = collections.defaultdict(list)
        # id(obj) -> node id. Never holds a strong reference to obj itself.
        self._object_to_node: dict[int, int] = {}
        # weakref.finalize isn't usefully genericizable here (its type
        # parameter tracks the finalized object's type, which varies
        # per call site) -- t.Any is the correct escape hatch, not a
        # laziness shortcut.
        self._finalizers: dict[int, t.Any] = {}

    # -- writing ---------------------------------------------------------

    def add_node(
        self,
        kind: NodeKind,
        label: str,
        *,
        obj: t.Any = None,
        location: str | None = None,
        thread: str | None = None,
        metadata: dict[str, t.Any] | None = None,
    ) -> Node:
        node = Node.create(kind, label, location=location, thread=thread, metadata=metadata)
        with self._lock:
            self._nodes[node.id] = node
            if obj is not None:
                self._track_identity(obj, node.id)
            self._evict_if_needed()
        return node

    def add_edge(
        self,
        source: Node | int,
        target: Node | int,
        kind: EdgeKind,
        *,
        confidence: float = Confidence.EXPLICIT.value,
        note: str | None = None,
    ) -> Edge:
        source_id = source.id if isinstance(source, Node) else source
        target_id = target.id if isinstance(target, Node) else target
        edge = Edge(source=source_id, target=target_id, kind=kind, confidence=confidence, note=note)
        with self._lock:
            self._edges.append(edge)
            self._edges_by_target[target_id].append(edge)
            self._edges_by_source[source_id].append(edge)
        return edge

    def _track_identity(self, obj: t.Any, node_id: int) -> None:
        key = id(obj)
        self._object_to_node[key] = node_id
        try:
            fin = weakref.finalize(obj, self._on_collected, key, node_id)
            # atexit is a real, documented, settable property on
            # weakref.finalize at runtime; typeshed's stub omits it
            # from __slots__, which is a stub gap, not a real error.
            fin.atexit = False  # type: ignore[misc]
            self._finalizers[node_id] = fin
        except TypeError:
            # Object doesn't support weak references (e.g. plain int, str,
            # tuple). We keep the id()->node mapping without a collection
            # hook; it may go stale under id() reuse in long-running
            # processes. Documented limitation, not silently pretended away.
            pass

    def _on_collected(self, key: int, node_id: int) -> None:
        with self._lock:
            if self._object_to_node.get(key) == node_id:
                del self._object_to_node[key]
            node = self._nodes.get(node_id)
            if node is not None:
                node.tombstone()
            self._finalizers.pop(node_id, None)

    def _evict_if_needed(self) -> None:
        while len(self._nodes) > self.max_nodes:
            oldest_id, _ = self._nodes.popitem(last=False)
            self._edges_by_target.pop(oldest_id, None)
            self._edges_by_source.pop(oldest_id, None)
            self._edges = [e for e in self._edges if oldest_id not in (e.source, e.target)]

    # -- reading -----------------------------------------------------------

    def node_for(self, obj: t.Any) -> Node | None:
        with self._lock:
            node_id = self._object_to_node.get(id(obj))
            if node_id is None:
                return None
            return self._nodes.get(node_id)

    def get(self, node_id: int) -> Node | None:
        return self._nodes.get(node_id)

    def ancestors(self, node_id: int, *, max_depth: int = 8) -> tuple[list[Node], list[Edge]]:
        """Walk causal edges backward from node_id, breadth-first, bounded
        by max_depth. Returns the visited nodes and the edges connecting
        them, in traversal order."""
        visited_nodes: dict[int, Node] = {}
        visited_edges: list[Edge] = []
        frontier = [node_id]
        depth = 0
        with self._lock:
            start = self._nodes.get(node_id)
            if start is not None:
                visited_nodes[node_id] = start
            while frontier and depth < max_depth:
                next_frontier: list[int] = []
                for nid in frontier:
                    for edge in self._edges_by_target.get(nid, ()):
                        visited_edges.append(edge)
                        if edge.source not in visited_nodes:
                            src = self._nodes.get(edge.source)
                            if src is not None:
                                visited_nodes[edge.source] = src
                                next_frontier.append(edge.source)
                frontier = next_frontier
                depth += 1
        return list(visited_nodes.values()), visited_edges

    def __len__(self) -> int:
        return len(self._nodes)

    def clear(self) -> None:
        """Drop all nodes and edges. Mainly a test/notebook convenience;
        production code should rely on max_nodes retention instead."""
        with self._lock:
            self._nodes.clear()
            self._edges.clear()
            self._edges_by_target.clear()
            self._edges_by_source.clear()
            self._object_to_node.clear()
            self._finalizers.clear()
