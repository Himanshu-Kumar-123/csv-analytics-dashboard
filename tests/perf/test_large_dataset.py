"""Performance budget for the 500,000-row target. Run with: pytest -m slow"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from app.core.charts import ChartSpec, build_chart
from app.core.explore import preview
from app.core.filters import apply_filters, validate_conditions
from app.core.ingest import parse_csv
from app.core.profiling import column_kinds
from app.core.quality import duplicates, missing_summary
from app.core.statistics import correlations, describe
from scripts.generate_large_csv import build

pytestmark = pytest.mark.slow
ROWS = 500_000


@pytest.fixture(scope="module")
def large_csv(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("perf") / "large.csv"
    build(ROWS).to_csv(path, index=False)
    return path


def timed(budget: float, fn):  # type: ignore[no-untyped-def]
    start = time.perf_counter()
    result = fn()
    elapsed = time.perf_counter() - start
    assert elapsed < budget, f"took {elapsed:.2f}s (budget {budget}s)"
    return result


def test_500k_rows_within_budget(large_csv: Path) -> None:
    df = timed(15, lambda: parse_csv(large_csv).df)
    assert len(df) == ROWS
    kinds = column_kinds(df)
    timed(2, lambda: preview(df, page=50, page_size=200, sort="price", order="desc"))
    conds = validate_conditions([{"column": "price", "op": "gt", "value": 100}], df, kinds)
    timed(2, lambda: apply_filters(df, conds))
    timed(6, lambda: describe(df, kinds))
    timed(6, lambda: correlations(df, kinds, "spearman"))
    timed(3, lambda: missing_summary(df, kinds))
    timed(6, lambda: duplicates(df, normalize=True))
    for spec in (
        ChartSpec("histogram", x="price"),
        ChartSpec("scatter", x="price", y="score"),
        ChartSpec("line", x="date", y="price", agg="mean"),
        ChartSpec("box", y="price", x="category"),
    ):
        out = timed(4, lambda spec=spec: build_chart(df, kinds, spec))
        assert out["meta"]["points"] <= 10_000
