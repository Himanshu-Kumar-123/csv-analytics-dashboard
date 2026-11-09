"""Descriptive statistics and correlations (framework-agnostic)."""

from __future__ import annotations

import math
from typing import Any, Literal

import numpy as np
import pandas as pd

from app.core.exceptions import InvalidParameterError
from app.core.profiling import ColumnKind

CorrelationMethod = Literal["pearson", "spearman"]
CORRELATION_METHODS: tuple[CorrelationMethod, ...] = ("pearson", "spearman")
MAX_CORRELATION_COLUMNS = 50
MIN_CORRELATION_OBSERVATIONS = 3


def _pct(part: int, whole: int) -> float:
    return round(100.0 * part / whole, 2) if whole else 0.0


def _base(series: pd.Series) -> dict[str, Any]:
    n = len(series)
    missing = int(series.isna().sum())
    return {
        "column": str(series.name),
        "count": n - missing,
        "missing": missing,
        "missing_pct": _pct(missing, n),
    }


def _round(value: Any, digits: int = 6) -> float | None:
    if value is None:
        return None
    f = float(value)
    return None if math.isnan(f) or math.isinf(f) else round(f, digits)


def numeric_stats(series: pd.Series) -> dict[str, Any]:
    out = _base(series)
    values = pd.to_numeric(series, errors="coerce").dropna().astype("float64")
    if values.empty:
        keys = ("mean", "std", "variance", "min", "p05", "q1", "median", "q3", "p95", "max")
        out.update({k: None for k in keys})
        out.update({"iqr": None, "range": None, "sum": None, "skewness": None, "kurtosis": None})
        out.update({"unique": 0, "zeros": 0, "negatives": 0, "outliers": 0})
        return out
    q = values.quantile([0.05, 0.25, 0.5, 0.75, 0.95]).to_numpy()
    iqr = q[3] - q[1]
    lower, upper = q[1] - 1.5 * iqr, q[3] + 1.5 * iqr
    out.update(
        {
            "mean": _round(values.mean()),
            "std": _round(values.std()),
            "variance": _round(values.var()),
            "min": _round(values.min()),
            "p05": _round(q[0]),
            "q1": _round(q[1]),
            "median": _round(q[2]),
            "q3": _round(q[3]),
            "p95": _round(q[4]),
            "max": _round(values.max()),
            "iqr": _round(iqr),
            "range": _round(values.max() - values.min()),
            "sum": _round(values.sum()),
            "skewness": _round(values.skew()),
            "kurtosis": _round(values.kurt()),
            "unique": int(values.nunique()),
            "zeros": int((values == 0).sum()),
            "negatives": int((values < 0).sum()),
            "outliers": int(((values < lower) | (values > upper)).sum()),
        }
    )
    return out


def categorical_stats(series: pd.Series, top: int = 5) -> dict[str, Any]:
    out = _base(series)
    values = series.dropna()
    counts = values.astype(str).value_counts()
    lengths = counts.index.str.len().to_numpy()
    n = len(values)
    out["unique"] = len(counts)
    out["top_values"] = [
        {"value": str(v), "count": int(c), "percent": _pct(int(c), n)}
        for v, c in counts.head(top).items()
    ]
    out["mode"] = str(counts.index[0]) if n else None
    out["mode_count"] = int(counts.iloc[0]) if n else 0
    if n:
        weights = counts.to_numpy()
        out["min_length"] = int(lengths.min())
        out["max_length"] = int(lengths.max())
        out["mean_length"] = _round(np.average(lengths, weights=weights), 2)
        probs = weights / n
        out["entropy"] = _round(float(-(probs * np.log2(probs)).sum()), 4)
    else:
        out.update({"min_length": None, "max_length": None, "mean_length": None, "entropy": None})
    return out


def datetime_stats(series: pd.Series) -> dict[str, Any]:
    out = _base(series)
    values = pd.to_datetime(series, errors="coerce").dropna()
    if values.empty:
        out.update({"min": None, "max": None, "median": None, "range_days": None, "unique": 0})
        return out
    lo, hi = values.min(), values.max()
    fmt = "%Y-%m-%d" if (values.dt.normalize() == values).all() else "%Y-%m-%d %H:%M:%S"
    ordered = values.sort_values()
    mid = len(ordered) // 2
    median = ordered.iloc[mid]
    if len(ordered) % 2 == 0:
        median = ordered.iloc[mid - 1] + (median - ordered.iloc[mid - 1]) / 2
    out.update(
        {
            "min": lo.strftime(fmt),
            "max": hi.strftime(fmt),
            "median": median.strftime(fmt if median == median.normalize() else "%Y-%m-%d %H:%M:%S"),
            "range_days": _round((hi - lo).total_seconds() / 86400, 2),
            "unique": int(values.nunique()),
        }
    )
    return out


def boolean_stats(series: pd.Series) -> dict[str, Any]:
    out = _base(series)
    values = series.dropna().astype(bool)
    true_count = int(values.sum())
    out.update(
        {
            "true_count": true_count,
            "false_count": int(len(values) - true_count),
            "true_pct": _pct(true_count, len(values)),
        }
    )
    return out


def dataset_summary(df: pd.DataFrame, kinds: dict[str, ColumnKind]) -> dict[str, Any]:
    rows, cols = df.shape
    missing = int(df.isna().sum().sum())
    kind_counts: dict[str, int] = {}
    for kind in kinds.values():
        kind_counts[kind] = kind_counts.get(kind, 0) + 1
    return {
        "rows": rows,
        "columns": cols,
        "cells": rows * cols,
        "missing_cells": missing,
        "missing_pct": _pct(missing, rows * cols),
        "kinds": kind_counts,
        "memory_bytes": int(df.memory_usage(deep=False, index=False).sum()),
    }


def describe(df: pd.DataFrame, kinds: dict[str, ColumnKind]) -> dict[str, Any]:
    """Statistics for every column, grouped by column kind."""
    result: dict[str, Any] = {
        "summary": dataset_summary(df, kinds),
        "numeric": [],
        "categorical": [],
        "datetime": [],
        "boolean": [],
    }
    for name in df.columns:
        kind = kinds.get(name, "text")
        series = df[name]
        if kind == "numeric":
            result["numeric"].append(numeric_stats(series))
        elif kind == "datetime":
            result["datetime"].append(datetime_stats(series))
        elif kind == "boolean":
            result["boolean"].append(boolean_stats(series))
        else:
            entry = categorical_stats(series)
            entry["kind"] = kind
            result["categorical"].append(entry)
    return result


def correlations(
    df: pd.DataFrame,
    kinds: dict[str, ColumnKind],
    method: str = "pearson",
    columns: list[str] | None = None,
    top_pairs: int = 10,
) -> dict[str, Any]:
    """Pairwise correlation matrix for numeric columns (pairwise-complete observations)."""
    if method not in CORRELATION_METHODS:
        raise InvalidParameterError(
            f"Unknown correlation method {method!r}.",
            details={"allowed": list(CORRELATION_METHODS)},
        )
    numeric = [c for c in df.columns if kinds.get(c) == "numeric"]
    if columns:
        unknown = [c for c in columns if c not in numeric]
        if unknown:
            raise InvalidParameterError(
                "Correlations require numeric columns.", details={"invalid": unknown}
            )
        numeric = [c for c in numeric if c in set(columns)]
    numeric = [c for c in numeric if df[c].nunique(dropna=True) > 1]
    truncated = len(numeric) > MAX_CORRELATION_COLUMNS
    numeric = numeric[:MAX_CORRELATION_COLUMNS]
    result: dict[str, Any] = {
        "method": method,
        "columns": numeric,
        "matrix": [],
        "pairs": [],
        "truncated": truncated,
        "rows": len(df),
    }
    if len(numeric) < 2:
        result["message"] = "At least two non-constant numeric columns are required."
        return result
    data = df[numeric].astype("float64")
    corr = data.corr(method=method, min_periods=MIN_CORRELATION_OBSERVATIONS)
    result["matrix"] = [[_round(v, 4) for v in row] for row in corr.to_numpy()]
    pairs: list[dict[str, Any]] = []
    for i, a in enumerate(numeric):
        for j in range(i + 1, len(numeric)):
            r = _round(corr.iat[i, j], 4)
            if r is not None:
                pairs.append({"a": a, "b": numeric[j], "r": r})
    pairs.sort(key=lambda p: abs(p["r"]), reverse=True)
    result["pairs"] = pairs[:top_pairs]
    return result
