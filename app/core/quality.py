"""Data-quality checks: missing values and duplicate rows (framework-agnostic)."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

from app.core.exceptions import InvalidParameterError
from app.core.profiling import ColumnKind
from app.core.serialization import format_datetimes, frame_to_records

MAX_PATTERNS = 10
MAX_GROUP_ROWS = 10


def _pct(part: int, whole: int) -> float:
    return round(100.0 * part / whole, 2) if whole else 0.0


def missing_summary(df: pd.DataFrame, kinds: dict[str, ColumnKind]) -> dict[str, Any]:
    """Per-column and per-row missing-value counts plus the most common missing patterns."""
    rows, cols = df.shape
    mask = df.isna()
    per_column = mask.sum()
    per_row = mask.sum(axis=1)
    rows_with_missing = int((per_row > 0).sum())
    total_missing = int(per_column.sum())

    columns = [
        {
            "column": str(name),
            "kind": kinds.get(name, "text"),
            "missing": int(per_column[name]),
            "missing_pct": _pct(int(per_column[name]), rows),
            "present": rows - int(per_column[name]),
        }
        for name in df.columns
    ]

    distribution = per_row.value_counts().sort_index()
    patterns: list[dict[str, Any]] = []
    with_missing = [c for c in df.columns if per_column[c] > 0]
    if with_missing:
        sub = mask.loc[per_row > 0, with_missing]
        for combo, count in sub.value_counts().head(MAX_PATTERNS).items():
            flags = combo if isinstance(combo, tuple) else (combo,)
            patterns.append(
                {
                    "columns": [
                        str(c) for c, flag in zip(with_missing, flags, strict=True) if flag
                    ],
                    "rows": int(count),
                    "percent": _pct(int(count), rows),
                }
            )

    return {
        "rows": rows,
        "columns_count": cols,
        "cells": rows * cols,
        "missing_cells": total_missing,
        "missing_pct": _pct(total_missing, rows * cols),
        "rows_with_missing": rows_with_missing,
        "rows_with_missing_pct": _pct(rows_with_missing, rows),
        "complete_rows": rows - rows_with_missing,
        "complete_rows_pct": _pct(rows - rows_with_missing, rows),
        "columns_with_missing": len(with_missing),
        "fully_missing_columns": [str(c) for c in df.columns if rows and per_column[c] == rows],
        "columns": columns,
        "patterns": patterns,
        "rows_by_missing_count": [
            {"missing": int(k), "rows": int(v)}
            for k, v in zip(distribution.index.to_numpy(), distribution.to_numpy(), strict=True)
        ],
    }


def parse_columns_param(raw: Any, df: pd.DataFrame) -> list[str] | None:
    """Parse an optional JSON list of column names and validate them against ``df``."""
    if raw is None or raw == "" or raw == []:
        return None
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise InvalidParameterError("columns must be a JSON array of column names.") from exc
    if not isinstance(raw, list) or not all(isinstance(c, str) for c in raw):
        raise InvalidParameterError("columns must be a JSON array of column names.")
    unknown = [c for c in raw if c not in df.columns]
    if unknown:
        raise InvalidParameterError("Unknown column(s).", details={"unknown": unknown})
    return list(dict.fromkeys(raw)) or None


def _normalize(series: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series) or pd.api.types.is_datetime64_any_dtype(series):
        return series
    text = series.astype("string").str.strip().str.lower().str.replace(r"\s+", " ", regex=True)
    return text.where(series.notna())


def duplicates(
    df: pd.DataFrame,
    columns: list[str] | None = None,
    *,
    normalize: bool = False,
    max_groups: int = 20,
) -> dict[str, Any]:
    """Find rows that repeat across ``columns`` (all columns by default).

    With ``normalize`` text is compared case-insensitively with collapsed whitespace,
    which surfaces near-duplicates such as ``"Delhi "`` vs ``"delhi"``.
    Row numbers are 1-based positions in the stored dataset.
    """
    subset = columns or [str(c) for c in df.columns]
    rows = len(df)
    key = df[subset]
    if normalize:
        key = key.apply(_normalize)
    in_group = key.duplicated(keep=False)
    extra = int(key.duplicated(keep="first").sum())
    result: dict[str, Any] = {
        "columns": subset,
        "all_columns": columns is None,
        "normalized": normalize,
        "rows": rows,
        "duplicate_rows": extra,
        "duplicate_pct": _pct(extra, rows),
        "rows_in_groups": int(in_group.sum()),
        "unique_rows": rows - extra,
        "groups_count": 0,
        "groups": [],
        "truncated": False,
    }
    if not extra:
        return result

    hashes = pd.util.hash_pandas_object(key[in_group], index=False)
    sizes = hashes.value_counts()
    result["groups_count"] = len(sizes)
    result["truncated"] = len(sizes) > max_groups
    firsts: list[Any] = []
    for h, size in sizes.head(max_groups).items():
        members = hashes.index[hashes.to_numpy() == h]
        firsts.append(members[0])
        result["groups"].append(
            {"size": int(size), "row_numbers": [int(i) + 1 for i in members[:MAX_GROUP_ROWS]]}
        )
    for group, values in zip(
        result["groups"], frame_to_records(format_datetimes(df.loc[firsts, subset])), strict=True
    ):
        group["values"] = values
    return result
