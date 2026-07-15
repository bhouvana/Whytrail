"""whytrail plugin for polars (ADR 0003).

Same finding and same design as whytrail-pandas, verified independently
rather than assumed from the pandas result: polars `DataFrame`/`Series`
support `weakref` and `id()`-based identity like any other Python
object, so a *tracked* polars frame already gets real provenance from
the generic graph with zero polars-specific code. What this plugin
adds is a diagnostic for an *untracked* frame -- shape, schema, null
counts -- and steps aside (returns None) the moment it sees a tracked
one, for the same reason whytrail-pandas does: registered explainers
resolve before the provenance graph (ADR 0001 §6), so without this
check a tracked frame would only ever get the diagnostic, never its
real lineage.
"""

from __future__ import annotations

import typing as t

import polars as pl

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin
from whytrail.runtime.context import current_scope, default_graph

_DIAGNOSTIC_NOTE = (
    "this is a diagnostic of the current state, not provenance -- polars "
    "doesn't retain transform history, so whytrail can't say what produced "
    "this unless it was tracked (whytrail.track() or a @whytrail.tracked "
    "pipeline step)"
)


def _is_tracked(obj: t.Any) -> bool:
    scope = current_scope()
    graph = scope.graph if scope is not None else default_graph()
    return graph.node_for(obj) is not None


def _explain_dataframe(df: "pl.DataFrame") -> Explanation | None:
    if _is_tracked(df):
        return None

    height, width = df.shape
    steps = [
        ExplanationStep(
            description=f"DataFrame: {height} rows x {width} columns",
            confidence=Confidence.EXPLICIT.value,
        )
    ]
    null_counts = df.null_count().to_dicts()[0] if height or width else {}
    with_nulls = {col: count for col, count in null_counts.items() if count}
    if with_nulls:
        parts = ", ".join(f"{col}={count}/{height}" for col, count in with_nulls.items())
        steps.append(ExplanationStep(description=f"columns with null values: {parts}", confidence=Confidence.EXPLICIT.value))
    schema = ", ".join(f"{name}={dtype}" for name, dtype in df.schema.items())
    steps.append(ExplanationStep(description=f"schema: {schema}", confidence=Confidence.EXPLICIT.value))
    steps.append(ExplanationStep(description=_DIAGNOSTIC_NOTE, confidence=Confidence.EXPLICIT.value))

    return Explanation(subject=f"DataFrame({height}x{width})", steps=steps, tracked=True)


def _explain_series(series: "pl.Series") -> Explanation | None:
    if _is_tracked(series):
        return None

    null_count = series.null_count()
    steps = [
        ExplanationStep(
            description=f"Series {series.name!r}: {len(series)} values, dtype={series.dtype}",
            confidence=Confidence.EXPLICIT.value,
        )
    ]
    if null_count:
        steps.append(
            ExplanationStep(
                description=f"{null_count}/{len(series)} values are null", confidence=Confidence.EXPLICIT.value
            )
        )
    steps.append(ExplanationStep(description=_DIAGNOSTIC_NOTE, confidence=Confidence.EXPLICIT.value))

    return Explanation(subject=f"Series({series.name!r})", steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(pl.DataFrame, _explain_dataframe)
    register_from_plugin(pl.Series, _explain_series)
