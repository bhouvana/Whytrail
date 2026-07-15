"""whytrail plugin for pandas (ADR 0002 §7, Tier B).

Two things worth being honest about before anything else:

Pandas retains no history of the transformations that produced a
DataFrame or Series -- "why is this cell NaN" cannot be answered for
an *untracked* object. There is no free lunch here; the constraint
ADR 0001 §1 established for plain Python values applies identically to
pandas ones, and this plugin does not pretend otherwise. What it
actually provides for an untracked DataFrame/Series is a rich, honest
diagnostic of its *current state* (shape, dtypes, null counts) --
closer to routing `df.info()` through `why()` than to real provenance,
and the returned Explanation says so explicitly.

For a *tracked* DataFrame/Series -- wrapped with `whytrail.track()`, or
produced inside a `@whytrail.tracked` pipeline step -- `why()` already
works via the generic provenance graph without this plugin's help:
pandas objects support `weakref` and `id()`-based identity tracking
like any other Python object, nothing pandas-specific was needed for
that to work. So this plugin steps out of the way (returns None) the
moment it sees a tracked object, rather than shadowing the real answer
with a generic diagnostic -- registered explainers resolve before the
provenance graph (ADR 0001 §6), so without this check a tracked
DataFrame would only ever get the diagnostic, never its real lineage.
"""

from __future__ import annotations

import typing as t

import pandas as pd

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin
from whytrail.runtime.context import current_scope, default_graph

_DIAGNOSTIC_NOTE = (
    "this is a diagnostic of the current state, not provenance -- pandas "
    "doesn't retain transform history, so whytrail can't say what produced "
    "this unless it was tracked (whytrail.track() or a @whytrail.tracked "
    "pipeline step)"
)


def _is_tracked(obj: t.Any) -> bool:
    scope = current_scope()
    graph = scope.graph if scope is not None else default_graph()
    return graph.node_for(obj) is not None


def _explain_dataframe(df: "pd.DataFrame") -> Explanation | None:
    if _is_tracked(df):
        return None  # step aside, let the real provenance graph answer

    steps = [
        ExplanationStep(
            description=f"DataFrame: {len(df)} rows x {len(df.columns)} columns",
            confidence=Confidence.EXPLICIT.value,
        )
    ]
    null_counts = df.isna().sum()
    with_nulls = null_counts[null_counts > 0]
    if not with_nulls.empty:
        parts = ", ".join(f"{col}={int(count)}/{len(df)}" for col, count in with_nulls.items())
        steps.append(
            ExplanationStep(description=f"columns with null values: {parts}", confidence=Confidence.EXPLICIT.value)
        )
    dtypes = ", ".join(f"{col}={dtype}" for col, dtype in df.dtypes.items())
    steps.append(ExplanationStep(description=f"dtypes: {dtypes}", confidence=Confidence.EXPLICIT.value))
    steps.append(ExplanationStep(description=_DIAGNOSTIC_NOTE, confidence=Confidence.EXPLICIT.value))

    return Explanation(subject=f"DataFrame({len(df)}x{len(df.columns)})", steps=steps, tracked=True)


def _explain_series(series: "pd.Series") -> Explanation | None:
    if _is_tracked(series):
        return None

    na_count = int(series.isna().sum())
    steps = [
        ExplanationStep(
            description=f"Series {series.name!r}: {len(series)} values, dtype={series.dtype}",
            confidence=Confidence.EXPLICIT.value,
        )
    ]
    if na_count:
        steps.append(
            ExplanationStep(
                description=f"{na_count}/{len(series)} values are null", confidence=Confidence.EXPLICIT.value
            )
        )
    steps.append(ExplanationStep(description=_DIAGNOSTIC_NOTE, confidence=Confidence.EXPLICIT.value))

    return Explanation(subject=f"Series({series.name!r})", steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(pd.DataFrame, _explain_dataframe)
    register_from_plugin(pd.Series, _explain_series)
