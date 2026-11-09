"""Structured row filters applied with vectorised boolean masks.

Filters are a list of conditions combined with AND, e.g.
    [{"column": "age", "op": "between", "value": [18, 65]},
     {"column": "city", "op": "in", "value": ["Delhi", "Pune"]}]

Only whitelisted operators are supported and values are coerced to the column type.
User input is never evaluated as code (no DataFrame.query / eval).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pandas as pd
from pandas.api import types as ptypes

from app.core.exceptions import InvalidParameterError
from app.core.profiling import ColumnKind

MAX_CONDITIONS = 20
MAX_LIST_VALUES = 500
MAX_TEXT_LENGTH = 500

NULL_OPS = ("is_null", "not_null")
COMPARISON_OPS = ("eq", "ne", "gt", "gte", "lt", "lte", "between")
TEXT_OPS = ("eq", "ne", "in", "not_in", "contains", "starts_with")

OPERATORS_BY_KIND: dict[str, tuple[str, ...]] = {
    "numeric": COMPARISON_OPS + NULL_OPS,
    "datetime": COMPARISON_OPS + NULL_OPS,
    "boolean": ("eq", "ne", *NULL_OPS),
    "categorical": TEXT_OPS + NULL_OPS,
    "text": TEXT_OPS + NULL_OPS,
}


@dataclass(frozen=True)
class Condition:
    column: str
    op: str
    value: Any = None

    def to_dict(self) -> dict[str, Any]:
        value = self.value
        if isinstance(value, pd.Timestamp):
            value = value.isoformat()
        elif isinstance(value, tuple | list):
            value = [v.isoformat() if isinstance(v, pd.Timestamp) else v for v in value]
        return {"column": self.column, "op": self.op, "value": value}


def parse_filter_param(raw: Any) -> list[dict[str, Any]]:
    """Accept a JSON string (query parameter), a list (JSON body) or nothing."""
    if raw is None or raw == "" or raw == []:
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise InvalidParameterError("'filters' must be valid JSON.") from exc
    if not isinstance(raw, list) or not all(isinstance(c, dict) for c in raw):
        raise InvalidParameterError("'filters' must be a list of condition objects.")
    if len(raw) > MAX_CONDITIONS:
        raise InvalidParameterError(f"At most {MAX_CONDITIONS} filter conditions are allowed.")
    return raw


def _to_number(value: Any, column: str) -> int | float:
    if isinstance(value, bool):
        raise InvalidParameterError(f"Filter on '{column}' expects a number.")
    # Keep integers exact: float() would round values above 2**53.
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().lstrip("+-").isdigit():
        return int(value.strip())
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise InvalidParameterError(f"Filter on '{column}' expects a number.") from exc
    if number != number or number in (float("inf"), float("-inf")):
        raise InvalidParameterError(f"Filter on '{column}' expects a finite number.")
    return number


def _to_timestamp(value: Any, column: str, tz: Any) -> pd.Timestamp:
    if not isinstance(value, str | int | float) or isinstance(value, bool):
        raise InvalidParameterError(f"Filter on '{column}' expects a date.")
    try:
        ts = pd.Timestamp(value)
    except (TypeError, ValueError) as exc:
        raise InvalidParameterError(f"Filter on '{column}' expects a valid date.") from exc
    if ts is pd.NaT:
        raise InvalidParameterError(f"Filter on '{column}' expects a valid date.")
    if tz is not None:
        ts = ts.tz_localize(tz) if ts.tzinfo is None else ts.tz_convert(tz)
    elif ts.tzinfo is not None:
        ts = ts.tz_convert(None)
    return ts


def _to_bool(value: Any, column: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in {"true", "false"}:
        return value.strip().lower() == "true"
    raise InvalidParameterError(f"Filter on '{column}' expects true or false.")


def _to_text(value: Any, column: str) -> str:
    if value is None or isinstance(value, dict | list):
        raise InvalidParameterError(f"Filter on '{column}' expects a text value.")
    text = str(value)
    if len(text) > MAX_TEXT_LENGTH:
        raise InvalidParameterError(f"Filter value for '{column}' is too long.")
    return text


def validate_conditions(
    raw: list[dict[str, Any]], df: pd.DataFrame, kinds: dict[str, ColumnKind]
) -> list[Condition]:
    conditions: list[Condition] = []
    for item in raw:
        column = item.get("column")
        op = item.get("op")
        value = item.get("value")
        if not isinstance(column, str) or column not in df.columns or column not in kinds:
            raise InvalidParameterError(f"Unknown filter column: {column!r}.")
        kind = kinds[column]
        allowed = OPERATORS_BY_KIND[kind]
        if op not in allowed:
            raise InvalidParameterError(
                f"Operator {op!r} is not valid for {kind} column '{column}'.",
                details={"allowed": list(allowed)},
            )
        if op in NULL_OPS:
            conditions.append(Condition(column, op))
            continue

        if kind in ("numeric", "datetime"):
            tz = getattr(df[column].dtype, "tz", None)

            def coerce(v: Any, col: str = column, k: str = kind, z: Any = tz) -> Any:
                return _to_number(v, col) if k == "numeric" else _to_timestamp(v, col, z)

            if op == "between":
                if not isinstance(value, list | tuple) or len(value) != 2:
                    raise InvalidParameterError(
                        f"'between' on '{column}' expects a [min, max] pair."
                    )
                low, high = coerce(value[0]), coerce(value[1])
                if low > high:
                    low, high = high, low
                conditions.append(Condition(column, op, (low, high)))
            else:
                conditions.append(Condition(column, op, coerce(value)))
        elif kind == "boolean":
            conditions.append(Condition(column, op, _to_bool(value, column)))
        else:
            if op in ("in", "not_in"):
                if not isinstance(value, list | tuple) or not value:
                    raise InvalidParameterError(f"'{op}' on '{column}' expects a list of values.")
                if len(value) > MAX_LIST_VALUES:
                    raise InvalidParameterError(f"At most {MAX_LIST_VALUES} values are allowed.")
                conditions.append(Condition(column, op, tuple(_to_text(v, column) for v in value)))
            else:
                conditions.append(Condition(column, op, _to_text(value, column)))
    return conditions


def _text_series(series: pd.Series) -> pd.Series:
    return series.astype(str)


def condition_mask(df: pd.DataFrame, cond: Condition) -> pd.Series:
    series = df[cond.column]
    notna = series.notna()
    op, value = cond.op, cond.value
    if op == "is_null":
        return ~notna
    if op == "not_null":
        return notna

    if ptypes.is_numeric_dtype(series) or ptypes.is_datetime64_any_dtype(series):
        if ptypes.is_bool_dtype(series):
            return notna & ((series == value) if op == "eq" else (series != value))
        if op == "between":
            low, high = value
            return notna & (series >= low) & (series <= high)
        compare = {
            "eq": series.eq,
            "ne": series.ne,
            "gt": series.gt,
            "gte": series.ge,
            "lt": series.lt,
            "lte": series.le,
        }[op]
        return notna & compare(value).fillna(False).astype(bool)

    text = _text_series(series)
    if isinstance(value, bool):
        value = str(value)
    if op == "eq":
        return notna & (text == value)
    if op == "ne":
        return notna & (text != value)
    if op == "in":
        return notna & text.isin(value)
    if op == "not_in":
        return notna & ~text.isin(value)
    if op == "contains":
        return notna & text.str.contains(value, case=False, regex=False)
    if op == "starts_with":
        return notna & text.str.lower().str.startswith(value.lower())
    raise InvalidParameterError(f"Unsupported operator {op!r}.")  # pragma: no cover


def apply_filters(df: pd.DataFrame, conditions: list[Condition]) -> pd.DataFrame:
    if not conditions:
        return df
    mask = pd.Series(True, index=df.index)
    for cond in conditions:
        mask &= condition_mask(df, cond)
    return df.loc[mask]
