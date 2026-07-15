"""Validates the alembic integration against real alembic exception
objects -- motivated by a real bug found in this project's own CI
debugging (a stale prefect.db causing a confusing "no such revision"
error), not a hypothetical."""

from __future__ import annotations

import pytest

alembic = pytest.importorskip("alembic")
pytest.importorskip("whytrail.integrations.alembic")

from alembic.script.revision import MultipleHeads, ResolutionError, RevisionError  # noqa: E402
from alembic.util.exc import CommandError  # noqa: E402

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402


def test_plugin_is_discovered():
    assert registry.resolve_explainer(ResolutionError) is not None
    assert registry.resolve_explainer(MultipleHeads) is not None
    assert registry.resolve_explainer(RevisionError) is not None
    assert registry.resolve_explainer(CommandError) is not None


def test_why_on_resolution_error_shows_the_bad_revision():
    exc = ResolutionError("No such revision or branch '79e7a60e43d8'", "79e7a60e43d8")
    explanation = whytrail.why(exc)
    assert explanation.known
    assert "'79e7a60e43d8'" in explanation.text
    assert "couldn't be resolved" in explanation.text


def test_why_on_multiple_heads_shows_all_heads():
    exc = MultipleHeads(["abc123", "def456"], "head")
    explanation = whytrail.why(exc)
    assert "abc123, def456" in explanation.text
    assert "2 head revisions" in explanation.text


def test_why_on_generic_command_error_still_gets_a_specific_answer():
    exc = CommandError("Path doesn't exist: 'migrations'.")
    explanation = whytrail.why(exc)
    assert explanation.known
    assert "migrations" in explanation.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(ResolutionError, lambda exc: "overridden by the user")
    exc = ResolutionError("No such revision 'x'", "x")
    explanation = whytrail.why(exc)
    assert "overridden by the user" in explanation.text
