"""Server-side chart building: aggregate/downsample with pandas, emit Plotly figure JSON.

Only aggregated or sampled values ever leave the server, never the full dataset.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

from app.core.exceptions import InvalidParameterError
from app.core.profiling import ColumnKind
from app.core.quality import missing_summary
from app.core.statistics import correlations

CHART_TYPES = ("histogram", "bar", "line", "scatter", "box", "pie", "heatmap", "missing")
AGGREGATIONS = ("count", "sum", "mean", "median", "min", "max")
FREQUENCIES = {
    "auto": None,
    "hour": "h",
    "day": "D",
    "week": "W",
    "month": "MS",
    "quarter": "QS",
    "year": "YS",
}
MAX_COLOR_GROUPS = 10
SAMPLE_SEED = 42

CATEGORY_KINDS: tuple[ColumnKind, ...] = ("categorical", "boolean", "text")
PALETTE = ["#0d6efd", "#20c997", "#fd7e14", "#6f42c1", "#dc3545", "#198754", "#0dcaf0",
           "#ffc107", "#d63384", "#6c757d", "#adb5bd"]  # fmt: skip


@dataclass(frozen=True)
class ChartSpec:
    type: str
    x: str | None = None
    y: str | None = None
    color: str | None = None
    agg: str = "count"
    bins: int = 30
    top: int = 20
    freq: str = "auto"
    method: str = "pearson"


def _require(
    df: pd.DataFrame,
    kinds: dict[str, ColumnKind],
    column: str | None,
    allowed: tuple[ColumnKind, ...],
    role: str,
    *,
    optional: bool = False,
) -> str | None:
    if not column:
        if optional:
            return None
        raise InvalidParameterError(f"The {role} column is required for this chart.")
    if column not in df.columns:
        raise InvalidParameterError(f"Unknown {role} column {column!r}.")
    kind = kinds.get(column, "text")
    if kind not in allowed:
        raise InvalidParameterError(
            f"{role.capitalize()} column {column!r} is {kind}; expected {' or '.join(allowed)}.",
            details={"column": column, "allowed_kinds": list(allowed)},
        )
    return column


def _labels(series: pd.Series) -> pd.Series:
    return series.astype("string").fillna("(missing)")


def _layout(fig: go.Figure, title: str, x_title: str | None, y_title: str | None) -> None:
    fig.update_layout(
        title={"text": title, "x": 0.01, "xanchor": "left"},
        template="plotly_white",
        margin={"l": 60, "r": 30, "t": 60, "b": 60},
        height=480,
        colorway=PALETTE,
        xaxis_title=x_title,
        yaxis_title=y_title,
    )


def _agg_label(agg: str, y: str | None) -> str:
    return "Count" if agg == "count" or not y else f"{agg.capitalize()} of {y}"


def _aggregate(grouped: Any, agg: str, y: str | None) -> pd.Series:
    if agg == "count" or not y:
        return grouped.size() if not y else grouped[y].count()
    return grouped[y].agg(agg)


def _check_agg(agg: str, y: str | None) -> None:
    if agg not in AGGREGATIONS:
        raise InvalidParameterError(f"Unknown aggregation {agg!r}.")
    if agg != "count" and not y:
        raise InvalidParameterError(f"Aggregation {agg!r} requires a numeric Y column.")


def histogram(df: pd.DataFrame, kinds: dict[str, ColumnKind], spec: ChartSpec) -> tuple:
    x = _require(df, kinds, spec.x, ("numeric", "datetime"), "x")
    assert x is not None
    values = df[x].dropna()
    if values.empty:
        raise InvalidParameterError(f"Column {x!r} has no values to plot.")
    if kinds[x] == "datetime":
        ints = pd.to_datetime(values).astype("int64").to_numpy()
        counts, edges = np.histogram(ints, bins=spec.bins)
        edge_ts = pd.to_datetime(edges)
        centers = edge_ts[:-1] + (edge_ts[1:] - edge_ts[:-1]) / 2
        widths = np.diff(edges) / 1e6  # ns -> ms (Plotly date axis unit)
        trace = go.Bar(x=centers, y=counts, width=widths, hovertemplate="%{x}<br>Count: %{y}")
    else:
        numeric = values.astype("float64").to_numpy()
        counts, edges = np.histogram(numeric, bins=spec.bins)
        trace = go.Bar(
            x=(edges[:-1] + edges[1:]) / 2,
            y=counts,
            width=np.diff(edges),
            customdata=np.column_stack([edges[:-1], edges[1:]]),
            hovertemplate="%{customdata[0]:.4g} \u2013 %{customdata[1]:.4g}<br>Count: %{y}"
            "<extra></extra>",
        )
    fig = go.Figure(trace)
    fig.update_traces(marker_line_width=0.5, marker_line_color="white")
    _layout(fig, f"Distribution of {x}", x, "Count")
    fig.update_layout(bargap=0)
    return fig, {"rows_used": len(values), "points": len(counts)}


def bar(df: pd.DataFrame, kinds: dict[str, ColumnKind], spec: ChartSpec) -> tuple:
    x = _require(df, kinds, spec.x, (*CATEGORY_KINDS, "numeric"), "x")
    y = _require(df, kinds, spec.y, ("numeric",), "y", optional=True)
    _check_agg(spec.agg, y)
    assert x is not None
    data = df[[x] + ([y] if y and y != x else [])].copy()
    data["__key"] = _labels(data[x])
    result = _aggregate(data.groupby("__key", sort=False), spec.agg, y)
    result = result.dropna().sort_values(ascending=False)
    total_groups = len(result)
    result = result.head(spec.top)
    fig = go.Figure(go.Bar(x=result.index.tolist(), y=result.to_numpy()))
    _layout(fig, f"{_agg_label(spec.agg, y)} by {x}", x, _agg_label(spec.agg, y))
    fig.update_xaxes(type="category")
    return fig, {"rows_used": len(data), "points": len(result), "groups": total_groups}


def _auto_freq(series: pd.Series) -> str:
    span_days = (series.max() - series.min()).total_seconds() / 86400
    if span_days > 1500:
        return "MS"
    if span_days > 180:
        return "W"
    if span_days > 3:
        return "D"
    return "h"


def line(df: pd.DataFrame, kinds: dict[str, ColumnKind], spec: ChartSpec, max_points: int) -> tuple:
    x = _require(df, kinds, spec.x, ("datetime", "numeric"), "x")
    y = _require(df, kinds, spec.y, ("numeric",), "y", optional=True)
    _check_agg(spec.agg, y)
    if spec.freq not in FREQUENCIES:
        raise InvalidParameterError(f"Unknown interval {spec.freq!r}.")
    assert x is not None
    cols = [x] + ([y] if y and y != x else [])
    data = df[cols].dropna(subset=[x])
    if data.empty:
        raise InvalidParameterError(f"Column {x!r} has no values to plot.")
    meta: dict[str, Any] = {"rows_used": len(data)}
    if kinds[x] == "datetime":
        rule = FREQUENCIES[spec.freq] or _auto_freq(data[x])
        grouped = data.set_index(x).resample(rule)
        series = grouped.size() if not y else _aggregate(grouped, spec.agg, y)
        if spec.agg == "count" or not y:
            series = series.astype("float64")
        meta["interval"] = next(k for k, v in FREQUENCIES.items() if v == rule)
        if len(series) > max_points:
            raise InvalidParameterError(
                f"This interval produces {len(series):,} points (limit {max_points:,}). "
                "Choose a coarser interval."
            )
    else:
        if data[x].nunique() > max_points:
            data = data.assign(__bin=pd.cut(data[x], bins=max_points))
            series = _aggregate(data.groupby("__bin", observed=True), spec.agg, y)
            series.index = pd.Index([iv.mid for iv in series.index])
            meta["binned"] = True
        else:
            series = _aggregate(data.groupby(x), spec.agg, y)
        series = series.sort_index()
    fig = go.Figure(go.Scatter(x=series.index, y=series.to_numpy(), mode="lines+markers"))
    fig.update_traces(marker_size=4, connectgaps=False)
    _layout(fig, f"{_agg_label(spec.agg, y)} over {x}", x, _agg_label(spec.agg, y))
    meta["points"] = len(series)
    return fig, meta


def scatter(
    df: pd.DataFrame, kinds: dict[str, ColumnKind], spec: ChartSpec, max_points: int
) -> tuple:
    x = _require(df, kinds, spec.x, ("numeric",), "x")
    y = _require(df, kinds, spec.y, ("numeric",), "y")
    color = _require(df, kinds, spec.color, CATEGORY_KINDS, "color", optional=True)
    assert x is not None and y is not None
    cols = list(dict.fromkeys([x, y] + ([color] if color else [])))
    data = df[cols].dropna(subset=[x, y])
    total = len(data)
    sampled = total > max_points
    if sampled:
        data = data.sample(n=max_points, random_state=SAMPLE_SEED).sort_index()
    fig = go.Figure()
    hover = f"{x}: %{{x}}<br>{y}: %{{y}}<extra>%{{fullData.name}}</extra>"
    if color:
        labels = _labels(data[color])
        keep = labels.value_counts().head(MAX_COLOR_GROUPS).index
        labels = labels.where(labels.isin(keep), "Other")
        for name, group in data.groupby(labels, sort=False):
            fig.add_trace(go.Scatter(x=group[x], y=group[y], mode="markers", name=str(name)))
    else:
        fig.add_trace(go.Scatter(x=data[x], y=data[y], mode="markers", name=y))
    fig.update_traces(marker={"size": 5, "opacity": 0.65}, hovertemplate=hover)
    _layout(fig, f"{y} vs {x}", x, y)
    return fig, {"rows_used": total, "points": len(data), "sampled": sampled}


def box(df: pd.DataFrame, kinds: dict[str, ColumnKind], spec: ChartSpec) -> tuple:
    y = _require(df, kinds, spec.y, ("numeric",), "y")
    group = _require(df, kinds, spec.x, CATEGORY_KINDS, "group", optional=True)
    assert y is not None
    data = df[[y] + ([group] if group else [])].dropna(subset=[y])
    if data.empty:
        raise InvalidParameterError(f"Column {y!r} has no values to plot.")
    if group:
        labels = _labels(data[group])
        order = labels.value_counts().head(spec.top).index.tolist()
        groups = [(str(name), data.loc[labels == name, y]) for name in order]
    else:
        groups = [(y, data[y])]
    stats: dict[str, list[Any]] = {k: [] for k in ("x", "q1", "median", "q3", "lo", "hi", "mean")}
    outliers = 0
    for name, values in groups:
        v = values.astype("float64")
        q1, med, q3 = v.quantile([0.25, 0.5, 0.75]).to_numpy()
        iqr = q3 - q1
        inside = v[(v >= q1 - 1.5 * iqr) & (v <= q3 + 1.5 * iqr)]
        outliers += len(v) - len(inside)
        for key, val in zip(
            stats, (name, q1, med, q3, inside.min(), inside.max(), v.mean()), strict=True
        ):
            stats[key].append(val)
    fig = go.Figure(
        go.Box(
            x=stats["x"],
            q1=stats["q1"],
            median=stats["median"],
            q3=stats["q3"],
            lowerfence=stats["lo"],
            upperfence=stats["hi"],
            mean=stats["mean"],
            boxpoints=False,
            name=y,
        )
    )
    _layout(fig, f"Distribution of {y}" + (f" by {group}" if group else ""), group, y)
    fig.update_xaxes(type="category")
    return fig, {"rows_used": len(data), "points": len(groups), "outliers_hidden": outliers}


def pie(df: pd.DataFrame, kinds: dict[str, ColumnKind], spec: ChartSpec) -> tuple:
    names = _require(df, kinds, spec.x, CATEGORY_KINDS, "names")
    values = _require(df, kinds, spec.y, ("numeric",), "values", optional=True)
    assert names is not None
    data = df[[names] + ([values] if values else [])]
    labels = _labels(data[names])
    if values:
        result = data[values].groupby(labels).sum(min_count=1).dropna()
        result = result[result > 0]
    else:
        result = labels.value_counts()
    result = result.sort_values(ascending=False)
    groups = len(result)
    if groups > spec.top:
        other = result.iloc[spec.top - 1 :].sum()
        result = pd.concat([result.iloc[: spec.top - 1], pd.Series({"Other": other})])
    fig = go.Figure(
        go.Pie(labels=result.index.tolist(), values=result.to_numpy(), hole=0.35, sort=False)
    )
    title = f"Share of {values} by {names}" if values else f"Share of rows by {names}"
    _layout(fig, title, None, None)
    return fig, {"rows_used": len(data), "points": len(result), "groups": groups}


def heatmap(df: pd.DataFrame, kinds: dict[str, ColumnKind], spec: ChartSpec) -> tuple:
    corr = correlations(df, kinds, spec.method)
    if len(corr["columns"]) < 2:
        raise InvalidParameterError(corr.get("message", "Not enough numeric columns."))
    cols = corr["columns"]
    z = [[np.nan if v is None else v for v in row] for row in corr["matrix"]]
    trace = go.Heatmap(
        z=z, x=cols, y=cols, zmin=-1, zmax=1, colorscale="RdBu", colorbar={"title": "r"},
        hovertemplate="%{y} \u00d7 %{x}<br>r = %{z:.3f}<extra></extra>",
    )  # fmt: skip
    if len(cols) <= 15:
        trace.update(texttemplate="%{z:.2f}")
    fig = go.Figure(trace)
    _layout(fig, f"{spec.method.capitalize()} correlation", None, None)
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(height=max(480, 28 * len(cols) + 160))
    return fig, {"rows_used": len(df), "points": len(cols) ** 2}


def missing_chart(df: pd.DataFrame, kinds: dict[str, ColumnKind], spec: ChartSpec) -> tuple:
    summary = missing_summary(df, kinds)
    cols = sorted(summary["columns"], key=lambda c: c["missing_pct"], reverse=True)
    fig = go.Figure(
        go.Bar(
            x=[c["column"] for c in cols],
            y=[c["missing_pct"] for c in cols],
            customdata=[c["missing"] for c in cols],
            marker_color=[
                "#dc3545" if c["missing_pct"] > 20 else "#ffc107" if c["missing_pct"] > 5
                else "#20c997" for c in cols
            ],
            hovertemplate="%{x}<br>%{y:.2f}% missing (%{customdata:,} rows)<extra></extra>",
        )
    )  # fmt: skip
    _layout(fig, "Missing values by column", None, "% missing")
    fig.update_yaxes(range=[0, 100])
    fig.update_xaxes(type="category")
    return fig, {"rows_used": len(df), "points": len(cols)}


def build_chart(
    df: pd.DataFrame, kinds: dict[str, ColumnKind], spec: ChartSpec, *, max_points: int = 10_000
) -> dict[str, Any]:
    """Return ``{"figure": <Plotly JSON>, "meta": {...}}`` for ``spec``."""
    if spec.type not in CHART_TYPES:
        raise InvalidParameterError(
            f"Unknown chart type {spec.type!r}.", details={"allowed": list(CHART_TYPES)}
        )
    if df.empty and spec.type not in ("missing",):
        raise InvalidParameterError("No rows match the current filters.")
    builders = {
        "histogram": lambda: histogram(df, kinds, spec),
        "bar": lambda: bar(df, kinds, spec),
        "line": lambda: line(df, kinds, spec, max_points),
        "scatter": lambda: scatter(df, kinds, spec, max_points),
        "box": lambda: box(df, kinds, spec),
        "pie": lambda: pie(df, kinds, spec),
        "heatmap": lambda: heatmap(df, kinds, spec),
        "missing": lambda: missing_chart(df, kinds, spec),
    }
    fig, meta = builders[spec.type]()
    meta.update({"type": spec.type, "sampled": meta.get("sampled", False)})
    return {"figure": json.loads(pio.to_json(fig, validate=False)), "meta": meta}
