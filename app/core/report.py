"""PDF analysis report (ReportLab + Matplotlib Agg). Contains summaries only, no raw rows."""

from __future__ import annotations

import io
from datetime import UTC, datetime
from typing import Any
from xml.sax.saxutils import escape

import matplotlib

matplotlib.use("Agg")

import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.core.profiling import ColumnKind
from app.core.quality import duplicates, missing_summary
from app.core.statistics import correlations, describe

MAX_TABLE_ROWS = 40
MAX_CELL_CHARS = 32
MAX_HEATMAP_COLUMNS = 15
MAX_HISTOGRAMS = 4

_styles = getSampleStyleSheet()


def _text(value: Any) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "-"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        return f"{value:,.4g}" if abs(value) < 1e6 else f"{value:,.0f}"
    text = str(value)
    return text if len(text) <= MAX_CELL_CHARS else text[: MAX_CELL_CHARS - 1] + "\u2026"


def _p(text: str, style: str = "BodyText") -> Paragraph:
    return Paragraph(escape(text), _styles[style])


def _table(headers: list[str], rows: list[list[Any]], note_total: int | None = None) -> list[Any]:
    shown = rows[:MAX_TABLE_ROWS]
    data = [headers] + [[_text(v) for v in r] for r in shown]
    table = Table(data, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), "Helvetica", 7.5),
                ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 7.5),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e9ecef")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f9fa")]),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#dee2e6")),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
            ]
        )
    )
    out: list[Any] = [table]
    total = note_total if note_total is not None else len(rows)
    if total > len(shown):
        out.append(_p(f"Showing {len(shown)} of {total} rows.", "Italic"))
    return out


def _image(fig: Figure, width_cm: float = 17) -> Image:
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=150, bbox_inches="tight")
    buffer.seek(0)
    w, h = fig.get_size_inches()
    return Image(buffer, width=width_cm * cm, height=width_cm * cm * h / w)


def _missing_chart(columns: list[dict[str, Any]]) -> Image:
    cols = sorted(columns, key=lambda c: c["missing_pct"], reverse=True)[:30]
    fig = Figure(figsize=(8, 3.2))
    ax = fig.subplots()
    ax.bar([c["column"][:20] for c in cols], [c["missing_pct"] for c in cols], color="#fd7e14")
    ax.set_ylabel("% missing")
    ax.set_ylim(0, 100)
    ax.tick_params(axis="x", labelrotation=60, labelsize=7)
    ax.set_title("Missing values by column", fontsize=10)
    return _image(fig)


def _histograms(df: pd.DataFrame, columns: list[str]) -> Image:
    n = len(columns)
    fig = Figure(figsize=(8, 2.8 * ((n + 1) // 2)))
    axes = np.atleast_1d(fig.subplots((n + 1) // 2, 2)).ravel()
    for ax, col in zip(axes, columns, strict=False):
        values = pd.to_numeric(df[col], errors="coerce").dropna()
        ax.hist(values, bins=30, color="#0d6efd")
        ax.set_title(col[:40], fontsize=9)
        ax.tick_params(labelsize=7)
    for ax in axes[n:]:
        ax.set_visible(False)
    fig.tight_layout()
    return _image(fig)


def _heatmap(result: dict[str, Any]) -> Image:
    cols = result["columns"]
    matrix = np.array([[np.nan if v is None else v for v in row] for row in result["matrix"]])
    fig = Figure(figsize=(6.5, 5.5))
    ax = fig.subplots()
    im = ax.imshow(matrix, cmap="RdBu", vmin=-1, vmax=1)
    labels = [c[:18] for c in cols]
    ax.set_xticks(range(len(cols)), labels, rotation=60, ha="right", fontsize=7)
    ax.set_yticks(range(len(cols)), labels, fontsize=7)
    for i in range(len(cols)):
        for j in range(len(cols)):
            if not np.isnan(matrix[i, j]):
                ax.text(j, i, f"{matrix[i, j]:.2f}", ha="center", va="center", fontsize=6)
    fig.colorbar(im, ax=ax, shrink=0.8)
    ax.set_title("Pearson correlation", fontsize=10)
    return _image(fig, 14)


def build_report(
    df: pd.DataFrame,
    kinds: dict[str, ColumnKind],
    *,
    title: str,
    total_rows: int,
    filters: list[dict[str, Any]],
) -> bytes:
    stats = describe(df, kinds)
    missing = missing_summary(df, kinds)
    dups = duplicates(df, max_groups=1)
    corr = correlations(df, kinds, "pearson")
    summary = stats["summary"]

    story: list[Any] = [
        _p(f"Analysis summary: {title}", "Title"),
        _p(f"Generated {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}", "Italic"),
        Spacer(1, 0.3 * cm),
    ]
    if filters:
        described = "; ".join(
            f"{f['column']} {f['op']} {f.get('value', '')}".strip() for f in filters
        )
        story.append(_p(f"Filters applied ({len(df):,} of {total_rows:,} rows): {described}"))
    story.append(_p("Dataset summary", "Heading2"))
    kinds_text = ", ".join(f"{v} {k}" for k, v in summary["kinds"].items())
    story += _table(
        ["Metric", "Value"],
        [
            ["Rows", summary["rows"]],
            ["Columns", summary["columns"]],
            ["Column kinds", kinds_text],
            ["Missing cells", f"{summary['missing_cells']:,} ({summary['missing_pct']}%)"],
            ["Complete rows", f"{missing['complete_rows']:,} ({missing['complete_rows_pct']}%)"],
            ["Duplicate rows", f"{dups['duplicate_rows']:,} ({dups['duplicate_pct']}%)"],
        ],
    )

    story.append(_p("Columns", "Heading2"))
    story += _table(
        ["Column", "Kind", "Missing", "Missing %"],
        [[c["column"], c["kind"], c["missing"], c["missing_pct"]] for c in missing["columns"]],
    )

    if stats["numeric"]:
        story.append(_p("Numeric statistics", "Heading2"))
        story += _table(
            ["Column", "Count", "Mean", "Std", "Min", "Median", "Max", "Outliers"],
            [
                [s["column"], s["count"], s["mean"], s["std"], s["min"], s["median"], s["max"],
                 s["outliers"]]
                for s in stats["numeric"]
            ],
        )  # fmt: skip
    if stats["categorical"]:
        story.append(_p("Categorical and text statistics", "Heading2"))
        story += _table(
            ["Column", "Count", "Unique", "Most common", "Mode count"],
            [
                [s["column"], s["count"], s["unique"], s["mode"], s["mode_count"]]
                for s in stats["categorical"]
            ],
        )
    if stats["datetime"]:
        story.append(_p("Date and time statistics", "Heading2"))
        story += _table(
            ["Column", "Count", "Earliest", "Latest", "Range (days)"],
            [
                [s["column"], s["count"], s["min"], s["max"], s["range_days"]]
                for s in stats["datetime"]
            ],
        )

    story += [PageBreak(), _p("Data quality", "Heading2")]
    if missing["missing_cells"]:
        story.append(_missing_chart(missing["columns"]))
    else:
        story.append(_p("No missing values."))
    story.append(
        _p(
            f"{dups['duplicate_rows']:,} duplicate rows across {dups['groups_count']:,} groups "
            f"(compared on all columns)."
        )
    )

    numeric_cols = [s["column"] for s in stats["numeric"] if s["count"]][:MAX_HISTOGRAMS]
    if numeric_cols and len(df):
        story += [_p("Distributions", "Heading2"), _histograms(df, numeric_cols)]

    if len(corr["columns"]) >= 2:
        story.append(_p("Correlations", "Heading2"))
        if len(corr["columns"]) <= MAX_HEATMAP_COLUMNS:
            story.append(_heatmap(corr))
        story += _table(
            ["Column A", "Column B", "Pearson r"], [[p["a"], p["b"], p["r"]] for p in corr["pairs"]]
        )

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.6 * cm,
        rightMargin=1.6 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title=f"Analysis summary: {title}",
        author="CSV Analytics Dashboard",
    )
    doc.build(story)
    return buffer.getvalue()
