"""Row preview (pagination / sorting) and value counts."""

from __future__ import annotations

import math
from typing import Any

import pandas as pd
from pandas.api import types as ptypes

from app.core.exceptions import InvalidParameterError
from app.core.serialization import frame_to_records, to_jsonable


def _format_datetimes(page: pd.DataFrame) -> pd.DataFrame:
    page = page.copy()
    for col in page.columns:
        series = page[col]
        if ptypes.is_datetime64_any_dtype(series):
            non_null = series.dropna()
            date_only = non_null.empty or bool((non_null.dt.normalize() == non_null).all())
            fmt = "%Y-%m-%d" if date_only else "%Y-%m-%d %H:%M:%S"
            page[col] = series.dt.strftime(fmt).where(series.notna(), None)
    return page


def preview(
    df: pd.DataFrame,
    *,
    page: int,
    page_size: int,
    sort: str | None = None,
    order: str = "asc",
) -> dict[str, Any]:
    if sort is not None:
        if sort not in df.columns:
            raise InvalidParameterError(f"Unknown sort column: {sort!r}.")
        df = df.sort_values(sort, ascending=order != "desc", kind="stable", na_position="last")
    matched = len(df)
    total_pages = max(1, math.ceil(matched / page_size))
    page = min(page, total_pages)
    start = (page - 1) * page_size
    window = _format_datetimes(df.iloc[start : start + page_size])
    return {
        "rows": frame_to_records(window),
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "matched_rows": matched,
        "first_row": start + 1 if matched else 0,
    }


def value_counts(series: pd.Series, top: int) -> dict[str, Any]:
    counts = series.value_counts(dropna=True)
    total = int(series.notna().sum())
    head = counts.head(top)
    if ptypes.is_datetime64_any_dtype(series):
        labels = [ts.isoformat() for ts in head.index]
    else:
        labels = [to_jsonable(v) for v in head.index]
    return {
        "values": [
            {"value": label, "count": int(c), "percent": round(100 * int(c) / total, 2)}
            for label, c in zip(labels, head.tolist(), strict=True)
        ],
        "distinct": int(counts.size),
        "non_null": total,
        "null": int(series.isna().sum()),
        "other_count": int(counts.iloc[top:].sum()) if counts.size > top else 0,
    }
