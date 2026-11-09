from __future__ import annotations

import csv
import io

import pandas as pd
import pytest
from pypdf import PdfReader

from app.core.exceptions import InvalidParameterError
from app.core.exports import EXPORT_KINDS, neutralize, summary_csv, summary_table, to_safe_csv
from app.core.profiling import column_kinds
from app.core.report import build_report


@pytest.fixture
def df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "n": [1.0, 2.0, None, 4.0, 4.0],
            "m": [2.0, 4.0, 6.0, 8.0, 8.0],
            "c": ["=cmd|' /C calc'!A0", "b", "b", None, None],
            "d": pd.to_datetime(["2024-01-01"] * 5),
        }
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [("=1+1", "'=1+1"), ("+1", "'+1"), ("-1", "'-1"), ("@x", "'@x"), ("\tx", "'\tx"),
     ("ok", "ok"), (-1, -1), (None, None)],
)  # fmt: skip
def test_neutralize(value: object, expected: object) -> None:
    assert neutralize(value) == expected


def test_to_safe_csv_neutralizes_headers_and_cells() -> None:
    out = to_safe_csv(pd.DataFrame({"=h": ["=x", "y"]})).decode("utf-8-sig")
    assert out.splitlines() == ["'=h", "'=x", "y"]


@pytest.mark.parametrize("kind", EXPORT_KINDS)
def test_every_summary_kind(df: pd.DataFrame, kind: str) -> None:
    table = summary_table(kind, df, column_kinds(df))
    assert not table.empty
    text = summary_csv(kind, df, column_kinds(df)).decode("utf-8-sig")
    for row in csv.reader(io.StringIO(text)):
        assert not any(cell.startswith(("=", "+", "@")) for cell in row), row


def test_summaries_contain_no_raw_rows(df: pd.DataFrame) -> None:
    overview = summary_table("overview", df, column_kinds(df))
    assert list(overview["column"]) == ["n", "m", "c", "d"]
    dups = summary_table("duplicates", df, column_kinds(df)).set_index("metric")["value"]
    assert dups["duplicate_rows"] == 1


def test_unknown_kind(df: pd.DataFrame) -> None:
    with pytest.raises(InvalidParameterError):
        summary_table("raw", df, column_kinds(df))


def test_pdf_report(df: pd.DataFrame) -> None:
    pdf = build_report(
        df,
        column_kinds(df),
        title="Sales <b>&</b>",
        total_rows=10,
        filters=[{"column": "n", "op": "gt", "value": 0}],
    )
    assert pdf.startswith(b"%PDF")
    reader = PdfReader(io.BytesIO(pdf))
    text = "\n".join(page.extract_text() for page in reader.pages)
    assert "Analysis summary: Sales <b>&</b>" in text
    assert "Filters applied" in text and "Numeric statistics" in text
    assert reader.metadata is not None and reader.metadata.title.startswith("Analysis summary")


def test_pdf_report_empty_frame(df: pd.DataFrame) -> None:
    empty = df.iloc[0:0]
    assert build_report(empty, column_kinds(df), title="x", total_rows=5, filters=[]).startswith(
        b"%PDF"
    )
