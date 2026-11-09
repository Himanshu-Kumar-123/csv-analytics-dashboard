"""Column type ("kind") detection and dataset schema."""

from __future__ import annotations

from typing import Any, Literal

import pandas as pd
from pandas.api import types as ptypes

ColumnKind = Literal["numeric", "categorical", "datetime", "boolean", "text"]

CATEGORICAL_MAX_UNIQUE = 50
CATEGORICAL_MAX_RATIO = 0.5


def column_kind(series: pd.Series) -> ColumnKind:
    if ptypes.is_bool_dtype(series):
        return "boolean"
    if ptypes.is_numeric_dtype(series):
        return "numeric"
    if ptypes.is_datetime64_any_dtype(series):
        return "datetime"
    non_null = series.dropna()
    if non_null.empty:
        return "categorical"
    unique = non_null.nunique()
    if unique <= CATEGORICAL_MAX_UNIQUE or unique / len(non_null) <= CATEGORICAL_MAX_RATIO:
        return "categorical"
    return "text"


def column_kinds(df: pd.DataFrame) -> dict[str, ColumnKind]:
    return {str(col): column_kind(df[col]) for col in df.columns}


def build_schema(df: pd.DataFrame) -> list[dict[str, Any]]:
    schema: list[dict[str, Any]] = []
    total = len(df)
    for col in df.columns:
        series = df[col]
        nulls = int(series.isna().sum())
        schema.append(
            {
                "name": str(col),
                "dtype": str(series.dtype),
                "kind": column_kind(series),
                "non_null": total - nulls,
                "null_count": nulls,
                "unique": int(series.nunique(dropna=True)),
            }
        )
    return schema
