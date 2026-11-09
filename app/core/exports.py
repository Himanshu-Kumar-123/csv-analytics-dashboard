"""Summary exports as CSV (framework-agnostic). Raw rows are never exported."""

from __future__ import annotations

import io
from typing import Any

import pandas as pd

from app.core.exceptions import InvalidParameterError
from app.core.profiling import ColumnKind
from app.core.quality import duplicates, missing_summary
from app.core.statistics import correlations, describe

EXPORT_KINDS = ("overview", "statistics", "missing", "duplicates", "correlations")
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def neutralize(value: Any) -> Any:
    """Prefix strings that spreadsheets would evaluate as formulas (CSV injection)."""
    if isinstance(value, str) and value.startswith(FORMULA_PREFIXES):
        return "'" + value
    return value


def to_safe_csv(df: pd.DataFrame) -> bytes:
    safe = df.map(neutralize)
    safe.columns = [neutralize(str(c)) for c in df.columns]
    return safe.to_csv(index=False).encode("utf-8-sig")


def _overview(df: pd.DataFrame, kinds: dict[str, ColumnKind]) -> pd.DataFrame:
    rows = len(df)
    records = []
    for name in df.columns:
        missing = int(df[name].isna().sum())
        records.append(
            {
                "column": name,
                "kind": kinds.get(name, "text"),
                "dtype": str(df[name].dtype),
                "non_missing": rows - missing,
                "missing": missing,
                "missing_pct": round(100 * missing / rows, 2) if rows else 0.0,
                "unique": int(df[name].nunique(dropna=True)),
            }
        )
    return pd.DataFrame(records)


def _statistics(df: pd.DataFrame, kinds: dict[str, ColumnKind]) -> pd.DataFrame:
    stats = describe(df, kinds)
    records: list[dict[str, Any]] = []
    for group in ("numeric", "categorical", "datetime", "boolean"):
        for entry in stats[group]:
            row = {"kind": entry.pop("kind", group), **entry}
            if "top_values" in row:
                row["top_values"] = "; ".join(
                    f"{v['value']} ({v['count']})" for v in row["top_values"]
                )
            records.append(row)
    frame = pd.DataFrame(records)
    if not frame.empty:
        frame = frame[
            ["column", "kind"] + [c for c in frame.columns if c not in ("column", "kind")]
        ]
    return frame


def _missing(df: pd.DataFrame, kinds: dict[str, ColumnKind]) -> pd.DataFrame:
    return pd.DataFrame(missing_summary(df, kinds)["columns"])


def _duplicates(df: pd.DataFrame, kinds: dict[str, ColumnKind]) -> pd.DataFrame:
    exact = duplicates(df, max_groups=1)
    loose = duplicates(df, normalize=True, max_groups=1)
    metrics = [
        ("rows", exact["rows"]),
        ("unique_rows", exact["unique_rows"]),
        ("duplicate_rows", exact["duplicate_rows"]),
        ("duplicate_pct", exact["duplicate_pct"]),
        ("duplicate_groups", exact["groups_count"]),
        ("rows_in_duplicate_groups", exact["rows_in_groups"]),
        ("near_duplicate_rows_ignoring_case_whitespace", loose["duplicate_rows"]),
    ]
    return pd.DataFrame(metrics, columns=["metric", "value"])


def _correlations(df: pd.DataFrame, kinds: dict[str, ColumnKind]) -> pd.DataFrame:
    frames = []
    for method in ("pearson", "spearman"):
        result = correlations(df, kinds, method, top_pairs=1_000_000)
        frames.append(pd.DataFrame(result["pairs"], columns=["a", "b", "r"]).assign(method=method))
    out = pd.concat(frames, ignore_index=True)
    return out.rename(columns={"a": "column_a", "b": "column_b", "r": "coefficient"})


_BUILDERS = {
    "overview": _overview,
    "statistics": _statistics,
    "missing": _missing,
    "duplicates": _duplicates,
    "correlations": _correlations,
}


def summary_table(kind: str, df: pd.DataFrame, kinds: dict[str, ColumnKind]) -> pd.DataFrame:
    if kind not in _BUILDERS:
        raise InvalidParameterError(
            f"Unknown export {kind!r}.", details={"allowed": list(EXPORT_KINDS)}
        )
    return _BUILDERS[kind](df, kinds)


def summary_csv(kind: str, df: pd.DataFrame, kinds: dict[str, ColumnKind]) -> bytes:
    buffer = io.BytesIO(to_safe_csv(summary_table(kind, df, kinds)))
    return buffer.getvalue()
