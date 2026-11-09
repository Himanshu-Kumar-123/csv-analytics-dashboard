from __future__ import annotations

import pandas as pd
import pytest

from app.core.exceptions import InvalidParameterError
from app.core.explore import preview, value_counts
from app.core.profiling import build_schema, column_kind


def test_preview_paginates_and_sorts() -> None:
    df = pd.DataFrame({"n": range(1, 101), "s": [f"v{i}" for i in range(100)]})
    out = preview(df, page=2, page_size=30, sort="n", order="desc")
    assert out["matched_rows"] == 100
    assert out["total_pages"] == 4
    assert out["first_row"] == 31
    assert [r["n"] for r in out["rows"]][:3] == [70, 69, 68]


def test_preview_clamps_page_and_handles_empty() -> None:
    df = pd.DataFrame({"n": [1, 2, 3]})
    assert preview(df, page=99, page_size=2)["page"] == 2
    empty = preview(df.iloc[0:0], page=1, page_size=10)
    assert empty["rows"] == [] and empty["first_row"] == 0


def test_preview_formats_dates_and_nulls() -> None:
    df = pd.DataFrame(
        {
            "d": pd.to_datetime(["2024-01-01", None]),
            "t": pd.to_datetime(["2024-01-01 10:30:00", "2024-01-02 00:00:00"]),
            "x": [1.5, float("nan")],
        }
    )
    rows = preview(df, page=1, page_size=10)["rows"]
    assert rows[0] == {"d": "2024-01-01", "t": "2024-01-01 10:30:00", "x": 1.5}
    assert rows[1]["d"] is None and rows[1]["x"] is None


def test_preview_unknown_sort_column() -> None:
    with pytest.raises(InvalidParameterError):
        preview(pd.DataFrame({"a": [1]}), page=1, page_size=10, sort="b")


def test_value_counts() -> None:
    s = pd.Series(["a", "b", "a", None, "c", "a"])
    out = value_counts(s, top=2)
    assert out["values"][0] == {"value": "a", "count": 3, "percent": 60.0}
    assert out["distinct"] == 3
    assert out["null"] == 1
    assert out["other_count"] == 1


def test_column_kinds_and_schema() -> None:
    df = pd.DataFrame(
        {
            "num": [1, 2, 3],
            "flag": [True, False, True],
            "when": pd.to_datetime(["2024-01-01"] * 3),
            "cat": ["a", "a", "b"],
            "empty": [None, None, None],
        }
    )
    assert column_kind(df["num"]) == "numeric"
    assert column_kind(df["flag"]) == "boolean"
    assert column_kind(df["when"]) == "datetime"
    assert column_kind(df["cat"]) == "categorical"
    text = pd.Series([f"unique-{i}" for i in range(200)])
    assert column_kind(text) == "text"
    schema = {c["name"]: c for c in build_schema(df)}
    assert schema["empty"]["null_count"] == 3
    assert schema["cat"]["unique"] == 2
