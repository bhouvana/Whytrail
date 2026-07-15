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
"""

from __future__ import annotations

import typing as t

import pytest

import whytrail

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

    explanation = whytrail.why(call.excinfo.value)
    body = explanation.text
    if getattr(node.config.option, "whytrail_graph", False):
        body = f"{body}\n\n{explanation.graph()}"
    report.sections.append((_SECTION_TITLE, body))
