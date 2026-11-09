from __future__ import annotations

import pandas as pd
import pytest

from app.core.exceptions import InvalidParameterError
from app.core.filters import apply_filters, parse_filter_param, validate_conditions
from app.core.profiling import column_kinds


@pytest.fixture
def df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "age": [25, 32, None, 45, 51],
            "city": ["Delhi", "Pune", "Delhi", None, "Mumbai"],
            "joined": pd.to_datetime(
                ["2023-01-01", "2023-06-15", "2024-01-01", "2024-03-10", None]
            ),
            "active": [True, False, True, True, False],
        }
    )


def run(df: pd.DataFrame, raw: list[dict]) -> pd.DataFrame:
    return apply_filters(df, validate_conditions(raw, df, column_kinds(df)))


@pytest.mark.parametrize(
    ("op", "value", "expected"),
    [
        ("eq", 32, [1]),
        ("ne", 32, [0, 3, 4]),
        ("gt", 32, [3, 4]),
        ("gte", 32, [1, 3, 4]),
        ("lt", 32, [0]),
        ("lte", "32", [0, 1]),
        ("between", [30, 50], [1, 3]),
        ("between", [50, 30], [1, 3]),
        ("is_null", None, [2]),
        ("not_null", None, [0, 1, 3, 4]),
    ],
)
def test_numeric_operators(df: pd.DataFrame, op: str, value: object, expected: list) -> None:
    assert run(df, [{"column": "age", "op": op, "value": value}]).index.tolist() == expected


@pytest.mark.parametrize(
    ("op", "value", "expected"),
    [
        ("eq", "Delhi", [0, 2]),
        ("ne", "Delhi", [1, 4]),
        ("in", ["Pune", "Mumbai"], [1, 4]),
        ("not_in", ["Pune"], [0, 2, 4]),
        ("contains", "um", [4]),
        ("contains", "DEL", [0, 2]),
        ("starts_with", "p", [1]),
        ("is_null", None, [3]),
    ],
)
def test_text_operators(df: pd.DataFrame, op: str, value: object, expected: list) -> None:
    assert run(df, [{"column": "city", "op": op, "value": value}]).index.tolist() == expected


def test_datetime_operators(df: pd.DataFrame) -> None:
    out = run(df, [{"column": "joined", "op": "gte", "value": "2024-01-01"}])
    assert out.index.tolist() == [2, 3]
    out = run(df, [{"column": "joined", "op": "between", "value": ["2023-02-01", "2023-12-31"]}])
    assert out.index.tolist() == [1]


def test_boolean_operator(df: pd.DataFrame) -> None:
    assert run(df, [{"column": "active", "op": "eq", "value": "false"}]).index.tolist() == [1, 4]


def test_conditions_are_combined_with_and(df: pd.DataFrame) -> None:
    out = run(
        df,
        [
            {"column": "city", "op": "eq", "value": "Delhi"},
            {"column": "age", "op": "lt", "value": 30},
        ],
    )
    assert out.index.tolist() == [0]


def test_no_conditions_returns_same_frame(df: pd.DataFrame) -> None:
    assert apply_filters(df, []) is df


def test_filter_does_not_mutate_source(df: pd.DataFrame) -> None:
    before = df.copy()
    run(df, [{"column": "age", "op": "gt", "value": 30}])
    pd.testing.assert_frame_equal(df, before)


@pytest.mark.parametrize(
    "raw",
    [
        [{"column": "missing", "op": "eq", "value": 1}],
        [{"column": "age", "op": "contains", "value": "1"}],
        [{"column": "city", "op": "gt", "value": "a"}],
        [{"column": "age", "op": "eq", "value": "abc"}],
        [{"column": "age", "op": "eq", "value": True}],
        [{"column": "age", "op": "between", "value": [1]}],
        [{"column": "joined", "op": "eq", "value": "not-a-date"}],
        [{"column": "city", "op": "in", "value": []}],
        [{"column": "city", "op": "in", "value": "Delhi"}],
        [{"column": "active", "op": "eq", "value": "maybe"}],
        [{"column": "age", "op": "__import__('os')", "value": 1}],
    ],
)
def test_invalid_conditions_raise(df: pd.DataFrame, raw: list[dict]) -> None:
    with pytest.raises(InvalidParameterError):
        validate_conditions(raw, df, column_kinds(df))


@pytest.mark.parametrize("raw", ["{", '{"a": 1}', "[1, 2]", [{"x": 1}] * 21])
def test_parse_filter_param_rejects_bad_payloads(raw: object) -> None:
    with pytest.raises(InvalidParameterError):
        parse_filter_param(raw)


def test_parse_filter_param_accepts_json_and_empty() -> None:
    assert parse_filter_param(None) == []
    assert parse_filter_param("") == []
    assert parse_filter_param('[{"column": "a", "op": "is_null"}]') == [
        {"column": "a", "op": "is_null"}
    ]
