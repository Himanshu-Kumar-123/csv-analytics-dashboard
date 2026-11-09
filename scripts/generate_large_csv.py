"""Generate a large synthetic CSV for performance testing (not committed).

Usage: python scripts/generate_large_csv.py [rows] [output_path]
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd


def build(rows: int, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    df = pd.DataFrame(
        {
            "id": np.arange(rows),
            "date": (
                pd.Timestamp("2020-01-01") + pd.to_timedelta(rng.integers(0, 1500, rows), "D")
            ).strftime("%Y-%m-%d"),
            "region": rng.choice(["North", "South", "East", "West"], rows),
            "category": rng.choice([f"cat_{i}" for i in range(20)], rows),
            "segment": rng.choice(["A", "B", "C"], rows),
            "flag": rng.random(rows) < 0.5,
            "quantity": rng.integers(1, 100, rows),
            "price": rng.uniform(1, 500, rows).round(2),
            "discount": rng.uniform(0, 0.3, rows).round(3),
            "score": rng.normal(50, 15, rows).round(2),
            "latency_ms": rng.exponential(120, rows).round(1),
            "rating": rng.integers(1, 6, rows).astype(float),
            "temperature": rng.normal(22, 6, rows).round(1),
            "code": [f"C{v:06d}" for v in rng.integers(0, 999_999, rows)],
            "comment": rng.choice(["ok", "late", "damaged", "refund", "great"], rows),
        }
    )
    for col in ("score", "rating", "comment"):
        df.loc[rng.random(rows) < 0.05, col] = np.nan
    return df


def main() -> None:
    rows = int(sys.argv[1]) if len(sys.argv) > 1 else 500_000
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("large_sample.csv")
    build(rows).to_csv(out, index=False)
    print(f"Wrote {rows:,} rows to {out} ({out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
