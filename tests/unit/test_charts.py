from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.core.charts import ChartSpec, build_chart
from app.core.exceptions import InvalidParameterError
from app.core.profiling import column_kinds


@pytest.fixture
def df() -> pd.DataFrame:
    rng = np.random.default_rng(0)
    n = 2_000
    return pd.DataFrame(
        {
            "num": rng.normal(50, 10, n),
            "num2": rng.normal(0, 1, n),
            "cat": rng.choice(["a", "b", "c", "d"], n),
            "flag": rng.choice([True, False], n),
            "when": pd.date_range("2023-01-01", periods=n, freq="h"),
        }
    )


def chart(df: pd.DataFrame, max_points: int = 10_000, **kw: object) -> dict:
    return build_chart(df, column_kinds(df), ChartSpec(**kw), max_points=max_points)  # type: ignore[arg-type]


def test_histogram_numeric_is_aggregated(df: pd.DataFrame) -> None:
    out = chart(df, type="histogram", x="num", bins=25)
    trace = out["figure"]["data"][0]
    assert trace["type"] == "bar"
    assert len(trace["y"]) == 25 and sum(trace["y"]) == len(df)
    assert out["meta"]["rows_used"] == len(df)


def test_histogram_datetime(df: pd.DataFrame) -> None:
    trace = chart(df, type="histogram", x="when", bins=10)["figure"]["data"][0]
    assert len(trace["x"]) == 10 and str(trace["x"][0]).startswith("2023")


def test_bar_count_and_mean(df: pd.DataFrame) -> None:
    out = chart(df, type="bar", x="cat")
    trace = out["figure"]["data"][0]
    assert sorted(trace["x"]) == ["a", "b", "c", "d"] and sum(trace["y"]) == len(df)
    mean = chart(df, type="bar", x="cat", y="num", agg="mean", top=2)
    assert len(mean["figure"]["data"][0]["x"]) == 2 and mean["meta"]["groups"] == 4


def test_line_resamples_dates(df: pd.DataFrame) -> None:
    out = chart(df, type="line", x="when", y="num", agg="mean", freq="day")
    assert out["meta"]["interval"] == "day"
    assert out["meta"]["points"] == 84
    auto = chart(df, type="line", x="when")
    assert auto["meta"]["interval"] == "day"


def test_line_point_limit(df: pd.DataFrame) -> None:
    with pytest.raises(InvalidParameterError, match="coarser"):
        chart(df, max_points=100, type="line", x="when", freq="hour")


def test_line_numeric_x_is_binned(df: pd.DataFrame) -> None:
    out = chart(df, max_points=50, type="line", x="num", y="num2", agg="mean")
    assert out["meta"]["binned"] and out["meta"]["points"] <= 50


def test_scatter_downsamples(df: pd.DataFrame) -> None:
    out = chart(df, max_points=500, type="scatter", x="num", y="num2", color="cat")
    assert out["meta"]["sampled"] is True and out["meta"]["points"] == 500
    assert sum(len(t["x"]) for t in out["figure"]["data"]) == 500
    assert {t["name"] for t in out["figure"]["data"]} == {"a", "b", "c", "d"}


def test_box_is_precomputed(df: pd.DataFrame) -> None:
    out = chart(df, type="box", y="num", x="cat")
    trace = out["figure"]["data"][0]
    assert trace["type"] == "box" and len(trace["q1"]) == 4
    assert "y" not in trace


def test_pie_groups_other() -> None:
    df = pd.DataFrame({"c": list("aaabbcdefg")})
    trace = chart(df, type="pie", x="c", top=3)["figure"]["data"][0]
    assert trace["labels"] == ["a", "b", "Other"] and trace["values"] == [3, 2, 5]


def test_heatmap_and_missing(df: pd.DataFrame) -> None:
    heat = chart(df, type="heatmap", method="spearman")["figure"]["data"][0]
    assert heat["type"] == "heatmap" and heat["x"] == ["num", "num2"]
    df.loc[:9, "cat"] = None
    miss = chart(df, type="missing")["figure"]["data"][0]
    assert miss["x"][0] == "cat" and miss["y"][0] == 0.5


@pytest.mark.parametrize(
    "kw",
    [
        {"type": "nope"},
        {"type": "histogram"},
        {"type": "histogram", "x": "cat"},
        {"type": "histogram", "x": "missing_col"},
        {"type": "bar", "x": "cat", "agg": "sum"},
        {"type": "scatter", "x": "num", "y": "cat"},
        {"type": "pie", "x": "num"},
        {"type": "line", "x": "when", "freq": "decade"},
    ],
)
def test_invalid_specs(df: pd.DataFrame, kw: dict) -> None:
    with pytest.raises(InvalidParameterError):
        chart(df, **kw)


def test_empty_frame_rejected(df: pd.DataFrame) -> None:
    with pytest.raises(InvalidParameterError, match="No rows"):
        chart(df.iloc[0:0], type="histogram", x="num")


def test_bar_with_column_named_key() -> None:
    df = pd.DataFrame({"cat": ["a", "a", "b"], "__key": [1.0, 2.0, 5.0]})
    trace = chart(df, type="bar", x="cat", y="__key", agg="sum")["figure"]["data"][0]
    assert dict(zip(trace["x"], trace["y"], strict=True)) == {"b": 5.0, "a": 3.0}
