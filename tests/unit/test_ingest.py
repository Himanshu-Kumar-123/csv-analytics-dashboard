from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from app.core.exceptions import InvalidFileError
from app.core.ingest import IngestLimits, detect_encoding, parse_csv, sniff_format


def write(tmp_path: Path, content: bytes | str, name: str = "f.csv") -> Path:
    path = tmp_path / name
    path.write_bytes(content.encode("utf-8") if isinstance(content, str) else content)
    return path


def test_parses_simple_csv_and_infers_types(tmp_path: Path) -> None:
    path = write(tmp_path, "a,b,c,d\n1,x,2.5,2024-01-01\n2,y,,2024-02-01\n")
    parsed = parse_csv(path)
    df = parsed.df
    assert list(df.columns) == ["a", "b", "c", "d"]
    assert parsed.delimiter == ","
    assert parsed.encoding == "utf-8"
    assert pd.api.types.is_integer_dtype(df["a"])
    assert pd.api.types.is_float_dtype(df["c"])
    assert pd.api.types.is_datetime64_any_dtype(df["d"])
    assert df["c"].isna().sum() == 1


@pytest.mark.parametrize("delim", [";", "\t", "|"])
def test_detects_alternative_delimiters(tmp_path: Path, delim: str) -> None:
    rows = [["name", "qty", "price"], ["apple", "3", "1,5"], ["pear", "4", "2,0"]]
    path = write(tmp_path, "\n".join(delim.join(r) for r in rows) + "\n")
    parsed = parse_csv(path)
    assert parsed.delimiter == delim
    assert list(parsed.df.columns) == ["name", "qty", "price"]


def test_single_column_file(tmp_path: Path) -> None:
    parsed = parse_csv(write(tmp_path, "value\n1\n2\n3\n"))
    assert list(parsed.df.columns) == ["value"]
    assert len(parsed.df) == 3


def test_utf8_bom_is_stripped(tmp_path: Path) -> None:
    parsed = parse_csv(write(tmp_path, b"\xef\xbb\xbfname,qty\nx,1\n"))
    assert list(parsed.df.columns) == ["name", "qty"]


def test_cp1252_fallback(tmp_path: Path) -> None:
    parsed = parse_csv(write(tmp_path, "city,temp\nZürich,5\nMálaga,20\n".encode("cp1252")))
    assert parsed.encoding in {"cp1252", "latin-1"}
    assert parsed.df["city"].tolist() == ["Zürich", "Málaga"]


def test_utf16_with_bom(tmp_path: Path) -> None:
    parsed = parse_csv(write(tmp_path, "a,b\n1,2\n".encode("utf-16")))
    assert parsed.encoding == "utf-16"
    assert parsed.df["b"].tolist() == [2]


def test_quoted_newlines_and_delimiters(tmp_path: Path) -> None:
    parsed = parse_csv(write(tmp_path, 'id,note\n1,"hello, world"\n2,"multi\nline"\n'))
    assert parsed.df["note"].tolist() == ["hello, world", "multi\nline"]


def test_blank_and_duplicate_headers_are_normalised(tmp_path: Path) -> None:
    parsed = parse_csv(write(tmp_path, "a,,a, b \n1,2,3,4\n"))
    assert list(parsed.df.columns) == ["a", "column_2", "a.1", "b"]


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"", "empty"),
        (b"   \n\n", "empty"),
        (b"a,b,c\n", "no data rows"),
        (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR", "binary"),
        (b"PK\x03\x04\x14\x00\x06\x00", "binary"),
        (b"a,b\n1,2\n3,4,5,6\n", "well-formed"),
    ],
)
def test_rejects_invalid_files(tmp_path: Path, content: bytes, message: str) -> None:
    with pytest.raises(InvalidFileError, match=message):
        parse_csv(write(tmp_path, content))


def test_rejects_too_many_columns(tmp_path: Path) -> None:
    header = ",".join(f"c{i}" for i in range(11))
    row = ",".join("1" for _ in range(11))
    with pytest.raises(InvalidFileError, match="maximum is 10"):
        parse_csv(write(tmp_path, f"{header}\n{row}\n"), IngestLimits(max_columns=10))


def test_rejects_overlong_header(tmp_path: Path) -> None:
    with pytest.raises(InvalidFileError, match="header"):
        parse_csv(write(tmp_path, f"{'h' * 30},b\n1,2\n"), IngestLimits(max_header_length=20))


def test_rejects_overlong_cell(tmp_path: Path) -> None:
    with pytest.raises(InvalidFileError, match="longer than"):
        parse_csv(write(tmp_path, f"a,b\n{'x' * 50},2\n"), IngestLimits(max_cell_length=20))


def test_partially_parseable_dates_stay_text(tmp_path: Path) -> None:
    parsed = parse_csv(write(tmp_path, "d\n2024-01-01\nnot a date\n2024-01-03\n"))
    assert parsed.df["d"].dtype == object


def test_datetime_with_time(tmp_path: Path) -> None:
    parsed = parse_csv(write(tmp_path, "ts\n2024-01-01 10:00:00\n2024-01-01 11:30:00\n"))
    assert pd.api.types.is_datetime64_any_dtype(parsed.df["ts"])


def test_numeric_like_strings_with_text_are_object(tmp_path: Path) -> None:
    parsed = parse_csv(write(tmp_path, "code\n001\nA12\n003\n"))
    assert parsed.df["code"].dtype == object


def test_detect_encoding_rejects_nul_bytes() -> None:
    with pytest.raises(InvalidFileError):
        detect_encoding(b"a,b\x00\n", complete=True)


def test_sniff_handles_truncated_sample(tmp_path: Path) -> None:
    body = "a;b;c\n" + "1;2;3\n" * 20000
    fmt = sniff_format(write(tmp_path, body))
    assert fmt.delimiter == ";"
