"""Validates whytrail-polars end to end against real DataFrame/Series
instances -- the same test shape as whytrail-pandas, since the
underlying claim (generic tracking already works, the plugin only
covers the untracked case) needed independent verification for
polars, not an assumption carried over from pandas."""

from __future__ import annotations

import pytest

pl = pytest.importorskip("polars")
pytest.importorskip("whytrail.integrations.polars")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(pl.DataFrame) is not None
    assert registry.resolve_explainer(pl.Series) is not None


def test_why_on_untracked_dataframe_gives_diagnostic_not_unknown():
    df = pl.DataFrame({"price": [1.0, None, 3.0], "region": ["EU", "US", None]})
    explanation = whytrail.why(df)
    assert explanation.known
    assert "3 rows x 2 columns" in explanation.text
    assert "price=1/3" in explanation.text
    assert "not provenance" in explanation.text


def test_why_on_untracked_series_gives_diagnostic():
    series = pl.Series("price", [1.0, None, 3.0])
    explanation = whytrail.why(series)
    assert explanation.known
    assert "1/3 values are null" in explanation.text


def test_tracked_dataframe_gets_real_provenance_not_the_diagnostic():
    @whytrail.tracked
    def build() -> "pl.DataFrame":
        return pl.DataFrame({"a": [1, 2]})

    with whytrail.trace():
        df = build()

    explanation = whytrail.why(df)
    assert explanation.known
    assert "build(...)" in " ".join(s.description for s in explanation.steps)
    assert "not provenance" not in explanation.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(pl.DataFrame, lambda df: "overridden by the user")
    df = pl.DataFrame({"a": [1]})
    explanation = whytrail.why(df)
    assert "overridden by the user" in explanation.text
