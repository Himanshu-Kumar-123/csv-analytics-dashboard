from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.core.exceptions import InvalidParameterError
from app.core.profiling import column_kinds
from app.core.quality import duplicates, missing_summary, parse_columns_param


@pytest.fixture
def df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "a": [1.0, None, 3.0, None, 5.0],
            "b": ["x", None, "z", None, "x"],
            "c": [None, None, None, None, None],
            "d": [1, 2, 3, 4, 5],
        }
    )


def test_missing_summary(df: pd.DataFrame) -> None:
    out = missing_summary(df, column_kinds(df))
    assert out["missing_cells"] == 9
    assert out["missing_pct"] == 45.0
    assert out["rows_with_missing"] == 5 and out["complete_rows"] == 0
    assert out["columns_with_missing"] == 3
    assert out["fully_missing_columns"] == ["c"]
    cols = {c["column"]: c for c in out["columns"]}
    assert cols["a"]["missing"] == 2 and cols["d"]["missing"] == 0
    assert out["patterns"][0] == {"columns": ["c"], "rows": 3, "percent": 60.0}
    assert out["patterns"][1]["columns"] == ["a", "b", "c"]
    assert out["rows_by_missing_count"] == [{"missing": 1, "rows": 3}, {"missing": 3, "rows": 2}]


def test_missing_summary_no_missing_and_empty() -> None:
    clean = pd.DataFrame({"a": [1, 2]})
    out = missing_summary(clean, column_kinds(clean))
    assert out["patterns"] == [] and out["complete_rows"] == 2
    empty = clean.iloc[0:0]
    assert missing_summary(empty, column_kinds(empty))["missing_pct"] == 0.0


def test_duplicates_all_columns() -> None:
    df = pd.DataFrame({"k": [1, 2, 1, 3, 1, 2], "v": ["a", "b", "a", "c", "a", "b"]})
    out = duplicates(df)
    assert out["duplicate_rows"] == 3
    assert out["rows_in_groups"] == 5
    assert out["groups_count"] == 2
    assert out["groups"][0] == {"size": 3, "row_numbers": [1, 3, 5], "values": {"k": 1, "v": "a"}}
    assert out["unique_rows"] == 3


def test_duplicates_subset_and_nulls() -> None:
    df = pd.DataFrame({"k": [1, 1, None, None], "v": ["a", "b", "c", "d"]})
    assert duplicates(df)["duplicate_rows"] == 0
    out = duplicates(df, ["k"])
    assert out["duplicate_rows"] == 2
    assert out["columns"] == ["k"] and not out["all_columns"]


def test_duplicates_normalize_text() -> None:
    df = pd.DataFrame({"city": ["Delhi", " delhi ", "Pune", "PUNE", "Goa"], "n": [1, 1, 2, 2, 3]})
    assert duplicates(df)["duplicate_rows"] == 0
    out = duplicates(df, normalize=True)
    assert out["duplicate_rows"] == 2
    assert out["groups"][0]["values"]["city"] in {"Delhi", "Pune"}


def test_duplicates_limits_groups_and_preserves_row_numbers() -> None:
    df = pd.DataFrame({"k": np.repeat(np.arange(30), 2)})
    out = duplicates(df, max_groups=5)
    assert out["groups_count"] == 30 and len(out["groups"]) == 5 and out["truncated"]
    filtered = df[df["k"] >= 10]
    assert duplicates(filtered, max_groups=1)["groups"][0]["row_numbers"][0] >= 21


def test_parse_columns_param() -> None:
    df = pd.DataFrame({"a": [1], "b": [2]})
    assert parse_columns_param(None, df) is None
    assert parse_columns_param('["b", "a", "b"]', df) == ["b", "a"]
    for bad in ("nope", '{"a": 1}', "[1]", '["zzz"]'):
        with pytest.raises(InvalidParameterError):
            parse_columns_param(bad, df)


def test_duplicates_format_dates() -> None:
    df = pd.DataFrame({"d": pd.to_datetime(["2024-01-01", "2024-01-01"]), "n": [1, 1]})
    assert duplicates(df)["groups"][0]["values"] == {"d": "2024-01-01", "n": 1}
