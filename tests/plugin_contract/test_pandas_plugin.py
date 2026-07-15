"""Validates whytrail-pandas end to end via real importlib.metadata
entry-point discovery, against real DataFrame/Series instances."""

from __future__ import annotations

import pytest

pd = pytest.importorskip("pandas")
pytest.importorskip("whytrail.integrations.pandas")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(pd.DataFrame) is not None
    assert registry.resolve_explainer(pd.Series) is not None


def test_why_on_untracked_dataframe_gives_diagnostic_not_unknown():
    df = pd.DataFrame({"price": [1.0, None, 3.0], "region": ["EU", "US", None]})
    explanation = whytrail.why(df)
    assert explanation.known
    assert "3 rows x 2 columns" in explanation.text
    assert "price=1/3" in explanation.text
    assert "not provenance" in explanation.text  # the honesty disclaimer


def test_why_on_untracked_series_gives_diagnostic():
    series = pd.Series([1.0, None, 3.0], name="price")
    explanation = whytrail.why(series)
    assert explanation.known
    assert "1/3 values are null" in explanation.text


def test_why_on_dataframe_with_no_nulls_has_no_null_step():
    df = pd.DataFrame({"a": [1, 2, 3]})
    explanation = whytrail.why(df)
    assert "null" not in explanation.text.split("dtypes:")[0].split("rows x")[1]


def test_tracked_dataframe_gets_real_provenance_not_the_diagnostic():
    @whytrail.tracked
    def build() -> "pd.DataFrame":
        return pd.DataFrame({"a": [1, 2]})

    with whytrail.trace():
        df = build()

    explanation = whytrail.why(df)
    assert explanation.known
    # the diagnostic explainer stepped aside -- this is graph provenance
    assert "build(...)" in " ".join(s.description for s in explanation.steps)
    assert "not provenance" not in explanation.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(pd.DataFrame, lambda df: "overridden by the user")
    df = pd.DataFrame({"a": [1]})
    explanation = whytrail.why(df)
    assert "overridden by the user" in explanation.text
