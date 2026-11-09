from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.core.exceptions import InvalidParameterError
from app.core.profiling import column_kinds
from app.core.statistics import (
    boolean_stats,
    categorical_stats,
    correlations,
    datetime_stats,
    describe,
    numeric_stats,
)


def test_numeric_stats_values() -> None:
    s = pd.Series([1, 2, 3, 4, 100, None, 0, -1], name="x")
    out = numeric_stats(s)
    assert out["count"] == 7 and out["missing"] == 1
    assert out["missing_pct"] == 12.5
    assert out["min"] == -1 and out["max"] == 100
    assert out["median"] == 2
    assert out["zeros"] == 1 and out["negatives"] == 1
    assert out["outliers"] == 1
    assert out["mean"] == pytest.approx(np.mean([1, 2, 3, 4, 100, 0, -1]), rel=1e-6)
    assert out["sum"] == 109


def test_numeric_stats_all_missing_and_constant() -> None:
    empty = numeric_stats(pd.Series([None, None], dtype="float64", name="e"))
    assert empty["count"] == 0 and empty["mean"] is None and empty["outliers"] == 0
    const = numeric_stats(pd.Series([5.0, 5.0, 5.0], name="c"))
    assert const["std"] == 0 and const["skewness"] in (None, 0.0)


def test_categorical_stats() -> None:
    s = pd.Series(["a", "bb", "a", None, "ccc", "a"], name="c")
    out = categorical_stats(s, top=2)
    assert out["unique"] == 3
    assert out["mode"] == "a" and out["mode_count"] == 3
    assert len(out["top_values"]) == 2
    assert out["top_values"][0] == {"value": "a", "count": 3, "percent": 60.0}
    assert out["min_length"] == 1 and out["max_length"] == 3
    assert out["mean_length"] == pytest.approx((3 * 1 + 2 + 3) / 5, abs=0.01)
    assert out["entropy"] > 0


def test_categorical_stats_empty() -> None:
    out = categorical_stats(pd.Series([None, None], dtype="object", name="c"))
    assert out["unique"] == 0 and out["mode"] is None and out["entropy"] is None


def test_datetime_stats() -> None:
    s = pd.Series(pd.to_datetime(["2024-01-01", "2024-01-11", None]), name="d")
    out = datetime_stats(s)
    assert out["min"] == "2024-01-01"
    assert out["max"] == "2024-01-11"
    assert out["range_days"] == 10
    assert out["missing"] == 1
    timed = datetime_stats(pd.Series(pd.to_datetime(["2024-01-01 08:30:00"]), name="t"))
    assert timed["min"] == "2024-01-01 08:30:00"


def test_boolean_stats() -> None:
    out = boolean_stats(pd.Series([True, False, True, None], dtype="object", name="b"))
    assert out == {
        "column": "b",
        "count": 3,
        "missing": 1,
        "missing_pct": 25.0,
        "true_count": 2,
        "false_count": 1,
        "true_pct": 66.67,
    }


def test_describe_groups_by_kind() -> None:
    df = pd.DataFrame(
        {
            "n": [1.0, 2.0, None],
            "c": ["x", "y", "x"],
            "d": pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01"]),
            "b": [True, False, True],
        }
    )
    out = describe(df, column_kinds(df))
    assert [c["column"] for c in out["numeric"]] == ["n"]
    assert [c["column"] for c in out["categorical"]] == ["c"]
    assert [c["column"] for c in out["datetime"]] == ["d"]
    assert [c["column"] for c in out["boolean"]] == ["b"]
    assert out["summary"]["missing_cells"] == 1
    assert out["summary"]["cells"] == 12


def test_correlations_pearson_and_spearman() -> None:
    x = np.arange(1, 51, dtype=float)
    df = pd.DataFrame({"x": x, "y": 2 * x + 1, "z": -(x**3), "const": 1.0, "c": ["a"] * 50})
    kinds = column_kinds(df)
    out = correlations(df, kinds, "pearson")
    assert out["columns"] == ["x", "y", "z"]
    assert out["matrix"][0][1] == 1.0
    assert out["pairs"][0]["r"] == pytest.approx(1.0)
    spearman = correlations(df, kinds, "spearman")
    assert spearman["matrix"][0][2] == -1.0


def test_correlations_handles_missing_and_insufficient_data() -> None:
    df = pd.DataFrame({"a": [1.0, 2.0, None, None], "b": [None, None, 3.0, 4.0]})
    out = correlations(df, column_kinds(df))
    assert out["matrix"][0][1] is None
    assert out["pairs"] == []
    single = correlations(df[["a"]], column_kinds(df[["a"]]))
    assert single["matrix"] == [] and "message" in single


def test_correlations_rejects_bad_input() -> None:
    df = pd.DataFrame({"a": [1.0, 2.0, 3.0], "c": ["x", "y", "z"]})
    with pytest.raises(InvalidParameterError):
        correlations(df, column_kinds(df), "kendall")
    with pytest.raises(InvalidParameterError):
        correlations(df, column_kinds(df), columns=["c"])
