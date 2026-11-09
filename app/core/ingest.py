"""CSV validation, sniffing and parsing."""

from __future__ import annotations

import codecs
import csv
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from pandas.api import types as ptypes
from pandas.tseries.api import guess_datetime_format

from app.core.exceptions import InvalidFileError

SNIFF_BYTES = 64 * 1024
DELIMITERS = ",;\t|"
FALLBACK_ENCODINGS = ("cp1252", "latin-1")
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_DATE_PATTERNS = re.compile(
    r"^\s*("
    r"\d{4}-\d{1,2}-\d{1,2}([ T]\d{1,2}:\d{2}(:\d{2}(\.\d+)?)?)?(Z|[+-]\d{2}:?\d{2})?"
    r"|\d{4}/\d{1,2}/\d{1,2}( \d{1,2}:\d{2}(:\d{2})?)?"
    r"|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}( \d{1,2}:\d{2}(:\d{2})?)?"
    r")\s*$"
)


@dataclass(frozen=True)
class IngestLimits:
    max_columns: int = 1000
    max_header_length: int = 256
    max_cell_length: int = 10_000


@dataclass(frozen=True)
class CSVFormat:
    encoding: str
    delimiter: str


@dataclass
class ParsedCSV:
    df: pd.DataFrame
    encoding: str
    delimiter: str


def detect_encoding(sample: bytes, *, complete: bool) -> str:
    if sample.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return "utf-16"
    if b"\x00" in sample:
        raise InvalidFileError("The file appears to be binary, not a text CSV file.")
    if sample.startswith(codecs.BOM_UTF8):
        return "utf-8-sig"
    try:
        codecs.getincrementaldecoder("utf-8")().decode(sample, final=complete)
        return "utf-8"
    except UnicodeDecodeError:
        pass
    for encoding in FALLBACK_ENCODINGS:
        try:
            sample.decode(encoding)
            return encoding
        except UnicodeDecodeError:
            continue
    raise InvalidFileError("Unable to determine the text encoding of the file.")


def _decode_sample(sample: bytes, encoding: str, *, complete: bool) -> str:
    decoder = codecs.getincrementaldecoder(encoding)(errors="replace")
    return decoder.decode(sample, final=complete)


def _guess_delimiter(lines: list[str]) -> str:
    best, best_score = ",", -1.0
    for delim in DELIMITERS:
        counts = [line.count(delim) for line in lines if line.strip()]
        if not counts or counts[0] == 0:
            continue
        consistent = sum(1 for c in counts if c == counts[0]) / len(counts)
        score = consistent * 1000 + counts[0]
        if score > best_score:
            best, best_score = delim, score
    return best


def sniff_format(path: Path) -> CSVFormat:
    with path.open("rb") as fh:
        sample = fh.read(SNIFF_BYTES)
        complete = fh.read(1) == b""
    if not sample.strip():
        raise InvalidFileError("The file is empty.")
    encoding = detect_encoding(sample, complete=complete)
    text = _decode_sample(sample, encoding, complete=complete)
    if encoding == "utf-16" and "\x00" in text:
        raise InvalidFileError("The file appears to be binary, not a text CSV file.")
    if len(_CONTROL_CHARS.findall(text)) > max(1, len(text) // 100):
        raise InvalidFileError("The file appears to be binary, not a text CSV file.")

    lines = text.splitlines()
    if not complete and len(lines) > 1:
        lines = lines[:-1]  # last line may be truncated
    lines = lines[:50]
    try:
        delimiter = csv.Sniffer().sniff("\n".join(lines), delimiters=DELIMITERS).delimiter
    except csv.Error:
        delimiter = _guess_delimiter(lines)
    return CSVFormat(encoding=encoding, delimiter=delimiter)


def _normalise_headers(columns: list[object], limits: IngestLimits) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for i, raw in enumerate(columns):
        name = str(raw).strip()
        if not name or name.startswith("Unnamed: "):
            name = f"column_{i + 1}"
        if len(name) > limits.max_header_length:
            raise InvalidFileError(
                f"Column header {i + 1} exceeds {limits.max_header_length} characters."
            )
        base, n = name, 1
        while name in seen:
            n += 1
            name = f"{base}_{n}"
        seen.add(name)
        names.append(name)
    return names


def _maybe_datetime(series: pd.Series) -> pd.Series | None:
    non_null = series.dropna()
    if non_null.empty:
        return None
    sample = non_null.astype(str).head(200)
    if not sample.map(lambda v: bool(_DATE_PATTERNS.match(v))).all():
        return None
    fmt = guess_datetime_format(str(sample.iloc[0]))
    if fmt is None:
        return None
    parsed = pd.to_datetime(series, format=fmt, errors="coerce")
    if not ptypes.is_datetime64_any_dtype(parsed):
        return None
    # Only convert when every non-null value parses; never silently drop data.
    if int(parsed.notna().sum()) != len(non_null):
        return None
    return parsed


def infer_types(df: pd.DataFrame) -> pd.DataFrame:
    for col in df.columns:
        if df[col].dtype == object:
            converted = _maybe_datetime(df[col])
            if converted is not None:
                df[col] = converted
    return df


def _read(path: Path, fmt: CSVFormat, **kwargs: object) -> pd.DataFrame:
    return pd.read_csv(  # type: ignore[call-overload]
        path,
        sep=fmt.delimiter,
        encoding=fmt.encoding,
        low_memory=False,
        on_bad_lines="error",
        **kwargs,
    )


def parse_csv(path: Path, limits: IngestLimits | None = None) -> ParsedCSV:
    limits = limits or IngestLimits()
    fmt = sniff_format(path)

    try:
        header = _read(path, fmt, nrows=0)
    except pd.errors.EmptyDataError as exc:
        raise InvalidFileError("The file contains no data.") from exc
    except (pd.errors.ParserError, UnicodeDecodeError, csv.Error) as exc:
        raise InvalidFileError(
            "The file is not a well-formed CSV.", details=str(exc)[:300]
        ) from exc
    if len(header.columns) > limits.max_columns:
        raise InvalidFileError(
            f"The file has {len(header.columns)} columns; the maximum is {limits.max_columns}."
        )

    df: pd.DataFrame | None = None
    candidates = [fmt]
    if fmt.encoding.startswith("utf-8"):
        candidates += [CSVFormat(enc, fmt.delimiter) for enc in FALLBACK_ENCODINGS]
    last_error: Exception | None = None
    for candidate in candidates:
        try:
            df = _read(path, candidate)
            fmt = candidate
            break
        except UnicodeDecodeError as exc:
            last_error = exc
            continue
        except pd.errors.EmptyDataError as exc:
            raise InvalidFileError("The file contains no data.") from exc
        except (pd.errors.ParserError, csv.Error, ValueError) as exc:
            raise InvalidFileError(
                "The file is not a well-formed CSV.", details=str(exc)[:300]
            ) from exc
    if df is None:
        raise InvalidFileError("Unable to decode the file.", details=str(last_error)[:300])

    if df.empty:
        raise InvalidFileError("The file contains a header but no data rows.")

    df.columns = pd.Index(_normalise_headers(list(df.columns), limits))
    for col in df.columns:
        if df[col].dtype == object:
            lengths = df[col].dropna().astype(str).str.len()
            if not lengths.empty and int(lengths.max()) > limits.max_cell_length:
                raise InvalidFileError(
                    f"Column '{col}' contains a value longer than "
                    f"{limits.max_cell_length} characters."
                )

    df = infer_types(df)
    return ParsedCSV(df=df, encoding=fmt.encoding, delimiter=fmt.delimiter)
