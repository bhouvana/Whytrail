"""The result type every why() call returns -- one model, several
renderings (ADR §05)."""

from __future__ import annotations

import dataclasses
import typing as t

from .node import Confidence, Edge, Node

_STYLES = {
    Confidence.EXPLICIT.value: "bold",
    Confidence.INFERRED.value: "yellow",
    Confidence.HEURISTIC.value: "dim yellow",
}


def _confidence_label(confidence: float) -> str:
    if confidence >= Confidence.EXPLICIT.value:
        return "explicit"
    if confidence >= Confidence.INFERRED.value:
        return "inferred"
    if confidence >= Confidence.HEURISTIC.value:
        return "heuristic"
    return "unknown"


def _confidence_marker(confidence: float) -> str:
    # Spelled out, not a symbol: an earlier version used ASCII markers
    # (==/~~/..) that were legible only after reading the docs -- see
    # ADR 0002 §3 item 2. Still plain ASCII deliberately: box-drawing
    # or bracket-free glyphs have crashed stdout on a default Windows
    # console (cp1252) before, and a debugging tool that crashes
    # trying to print its own output would be absurd.
    return f"[{_confidence_label(confidence)}]"


def _confidence_style(confidence: float) -> str:
    return _STYLES.get(confidence, "dim")


@dataclasses.dataclass(slots=True)
class ExplanationStep:
    """One causal hop in the chain, ordered root-cause first.

    `locals` is a separate field from `description` on purpose: local
    variables at an exception's origin frame are exactly the kind of
    thing that can hold a password, an API key, or a customer record,
    and anything that exports an Explanation off-box (Sentry, OTel, a
    PR comment, an HTTP error response) needs a way to drop them
    without hand-parsing text out of a human-readable string. See
    Explanation.redacted() and ADR 0002 §3 item 5.
    """

    description: str
    confidence: float = Confidence.EXPLICIT.value
    location: str | None = None
    kind: str = "value"
    locals: dict[str, str] | None = None


@dataclasses.dataclass(slots=True)
class Explanation:
    """Returned by every why() call. Honest by construction: an
    Explanation with no steps says so plainly rather than fabricating a
    chain (ADR §11)."""

    subject: str
    steps: list[ExplanationStep] = dataclasses.field(default_factory=list)
    tracked: bool = True
    nodes: list[Node] = dataclasses.field(default_factory=list)
    edges: list[Edge] = dataclasses.field(default_factory=list)

    @property
    def confidence(self) -> float:
        if not self.steps:
            return Confidence.UNKNOWN.value
        return min(step.confidence for step in self.steps)

    @property
    def known(self) -> bool:
        return bool(self.steps)

    @property
    def text(self) -> str:
        if not self.steps:
            return (
                f"why({self.subject}): unknown -- no provenance captured.\n"
                f"  This value was never tracked. Wrap it with whytrail.track(), "
                f"@whytrail.tracked, or raise it as an exception to get an answer."
            )
        lines = [f"why({self.subject}):"]
        for step in self.steps:
            marker = _confidence_marker(step.confidence)
            loc = f"  [{step.location}]" if step.location else ""
            lines.append(f"  {marker} {step.description}{loc}")
            if step.locals:
                lines.append(f"      locals: {_format_locals(step.locals)}")
        return "\n".join(lines)

    def __str__(self) -> str:
        return self.text

    def __repr__(self) -> str:
        return (
            f"<Explanation subject={self.subject!r} steps={len(self.steps)} "
            f"confidence={_confidence_label(self.confidence)} tracked={self.tracked}>"
        )

    def rich(self) -> t.Any:
        """Render as a rich.tree.Tree. Requires the 'rich' extra."""
        try:
            from rich.text import Text
            from rich.tree import Tree
        except ImportError as exc:  # pragma: no cover - exercised via extras test
            raise ImportError(
                "Rich rendering needs the 'rich' extra: pip install whytrail[rich]"
            ) from exc

        tree = Tree(f"why({self.subject})")
        if not self.steps:
            tree.add(Text("unknown -- no provenance captured", style="dim italic"))
            return tree
        for step in self.steps:
            label = Text(step.description, style=_confidence_style(step.confidence))
            if step.location:
                label.append(f"  {step.location}", style="dim")
            label.append(f"  ({_confidence_label(step.confidence)})", style="dim italic")
            if step.locals:
                label.append(f"\n      locals: {_format_locals(step.locals)}", style="dim")
            tree.add(label)
        return tree

    def json(self) -> dict[str, t.Any]:
        return {
            "subject": self.subject,
            "tracked": self.tracked,
            "known": self.known,
            "confidence": self.confidence,
            "steps": [
                {
                    "description": s.description,
                    "confidence": s.confidence,
                    "confidence_label": _confidence_label(s.confidence),
                    "location": s.location,
                    "kind": s.kind,
                    "locals": s.locals,
                }
                for s in self.steps
            ],
        }

    def redacted(self) -> "Explanation":
        """A copy with every step's locals stripped -- the one-line
        way for any integration that exports off-box (Sentry, OTel, a
        CI comment, an HTTP error response) to get a safe-to-share
        version. Everything else (description, location, confidence,
        the causal chain itself) is preserved; only the raw local
        variable values are dropped, since those are the one thing
        that can plausibly contain a secret.
        """
        return dataclasses.replace(
            self,
            steps=[dataclasses.replace(step, locals=None) for step in self.steps],
        )

    def graph(self) -> str:
        """Render the traversed provenance subgraph as a Mermaid
        flowchart (ADR §12, Fig. 1)."""
        if not self.nodes:
            return f'graph TD\n    A["{_escape(self.subject)} -- no provenance captured"]'
        lines = ["graph TD"]
        for node in self.nodes:
            marker = " (tombstoned)" if node.tombstoned else ""
            lines.append(f'    N{node.id}["{node.kind.value}: {_escape(node.label)}{marker}"]')
        for edge in self.edges:
            arrow = "-->" if edge.confidence >= Confidence.EXPLICIT.value else "-.->"
            lines.append(f"    N{edge.source} {arrow}|{edge.kind.value}| N{edge.target}")
        return "\n".join(lines)


def _escape(label: str) -> str:
    return label.replace('"', "'").replace("\n", " ")


def _format_locals(locals_: dict[str, str]) -> str:
    return ", ".join(f"{name}={value}" for name, value in locals_.items())
