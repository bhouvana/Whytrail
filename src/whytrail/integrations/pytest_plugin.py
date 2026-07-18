"""pytest integration (ADR 0002 §7, Tier A).

A different kind of integration than whytrail-requests: this doesn't
teach why() to explain a new type via the `whytrail.explainers` entry
point -- it *calls* why() at the one place pytest already has a fully
assembled exception (pytest's own `pytest11` plugin entry-point
group), and attaches the result to the failure report using pytest's
own supported extension point (`report.sections`), not by patching
`longrepr` or otherwise fighting pytest's rendering.

Most valuable exactly where a bare traceback is weakest: fixture-heavy
failures, where the traceback shows the assertion line but not which
fixture value produced the bad input three calls upstream.

Also surfaces Tier 2 provenance for any locals at the failing
assertion that were separately track()ed (0.3) -- Tier 1, which the
section above is built entirely from, never consults the provenance
graph by design (ADR 0008's invariant 4), so a value that failed an
assertion *and* was track()ed needs a second, explicit why() call to
show its own derivation history. Without this, a test like

    with whytrail.trace():
        price = whytrail.track(parse(raw), derived_from=raw)
        assert price == expected

only ever explains "AssertionError at this line" -- never "and here's
where `price` actually came from," even though that's exactly the
kind of upstream-cause question this plugin's own docstring above
already says a bare traceback is weakest at.
"""

from __future__ import annotations

import typing as t

import pytest

import whytrail
from whytrail.runtime.context import default_graph

_SECTION_TITLE = "whytrail"


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("whytrail")
    group.addoption(
        "--no-whytrail",
        action="store_true",
        default=False,
        help="disable the whytrail explanation section on failure reports",
    )
    group.addoption(
        "--whytrail-graph",
        action="store_true",
        default=False,
        help="also include a Mermaid provenance graph in the whytrail section",
    )


def pytest_exception_interact(node: t.Any, call: t.Any, report: t.Any) -> None:
    if getattr(node.config.option, "no_whytrail", False):
        return
    if not report.failed or call.excinfo is None:
        return

    exc = call.excinfo.value
    explanation = whytrail.why(exc)
    body = explanation.text
    if getattr(node.config.option, "whytrail_graph", False):
        body = f"{body}\n\n{explanation.graph()}"

    for name, tracked_text in _tracked_locals_sections(exc):
        body += f"\n\n--- {name!r} was separately track()ed ---\n{tracked_text}"

    report.sections.append((_SECTION_TITLE, body))


def _origin_frame(exc: BaseException) -> t.Any:
    """The innermost frame -- the same logic as
    explainers/builtin.py's private helper of the same name,
    duplicated rather than imported across modules: ADR 0008's
    invariant 1 keeps producers/consumers off each other's private
    internals, and four lines is cheaper than a new cross-module
    dependency for this."""
    tb = exc.__traceback__
    if tb is None:
        return None
    while tb.tb_next is not None:
        tb = tb.tb_next
    return tb.tb_frame


def _tracked_locals_sections(exc: BaseException) -> list[tuple[str, str]]:
    frame = _origin_frame(exc)
    if frame is None:
        return []
    graph = default_graph()
    sections = []
    for name, value in frame.f_locals.items():
        if name.startswith("__"):
            continue
        if graph.node_for(value) is None:
            continue
        explanation = whytrail.why(value)
        if explanation.known:
            sections.append((name, explanation.text))
    return sections
