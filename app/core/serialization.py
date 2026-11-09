"""Convert pandas / NumPy values into JSON-safe Python objects."""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any

import numpy as np
import pandas as pd


def to_jsonable(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bool | str | int):
        return value
    if isinstance(value, float):
        return None if math.isnan(value) or math.isinf(value) else value
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        f = float(value)
        return None if math.isnan(f) or math.isinf(f) else f
    if value is pd.NaT:
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, pd.Timedelta):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple | set):
        return [to_jsonable(v) for v in value]
    if isinstance(value, np.ndarray):
        return [to_jsonable(v) for v in value.tolist()]
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return str(value)


def frame_to_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    columns = [str(c) for c in df.columns]
    return [
        {col: to_jsonable(v) for col, v in zip(columns, row, strict=True)}
        for row in df.itertuples(index=False, name=None)
    ]
