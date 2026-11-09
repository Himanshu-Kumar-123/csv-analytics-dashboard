"""Generate the synthetic sample datasets in sample_data/ (deterministic)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent.parent / "sample_data"
SEED = 20241109


def sales_orders(rng: np.random.Generator, n: int = 5000) -> pd.DataFrame:
    categories = {
        "Electronics": (["Laptop", "Headphones", "Monitor", "Keyboard", "Webcam"], 40, 1500),
        "Furniture": (["Desk", "Chair", "Bookshelf", "Lamp"], 25, 600),
        "Office Supplies": (["Notebook", "Pens", "Stapler", "Paper Ream", "Binder"], 2, 40),
        "Apparel": (["T-Shirt", "Jacket", "Cap", "Sneakers"], 10, 150),
    }
    regions = ["North", "South", "East", "West", "Central"]
    segments = ["Consumer", "Corporate", "Small Business"]
    cat_names = list(categories)
    cat = rng.choice(cat_names, size=n, p=[0.3, 0.2, 0.35, 0.15])
    product, unit_price = [], []
    for c in cat:
        items, lo, hi = categories[c]
        product.append(rng.choice(items))
        unit_price.append(round(float(rng.uniform(lo, hi)), 2))
    units = rng.integers(1, 15, size=n)
    discount = rng.choice([0, 0.05, 0.1, 0.15, 0.2], size=n, p=[0.5, 0.2, 0.15, 0.1, 0.05])
    dates = pd.Timestamp("2023-01-01") + pd.to_timedelta(rng.integers(0, 730, size=n), unit="D")
    df = pd.DataFrame(
        {
            "order_id": [f"ORD-{100000 + i}" for i in range(n)],
            "order_date": dates.strftime("%Y-%m-%d"),
            "region": rng.choice(regions, size=n),
            "customer_segment": rng.choice(segments, size=n, p=[0.55, 0.3, 0.15]),
            "category": cat,
            "product": product,
            "units": units,
            "unit_price": unit_price,
            "discount": discount,
        }
    )
    df["revenue"] = (df["units"] * df["unit_price"] * (1 - df["discount"])).round(2)
    df["ship_days"] = rng.poisson(3, size=n) + 1
    missing = rng.random(n) < 0.02
    df.loc[missing, "ship_days"] = np.nan
    df["ship_days"] = df["ship_days"].astype("Int64")
    return df.sort_values("order_date").reset_index(drop=True)


def employees(rng: np.random.Generator, n: int = 1000) -> pd.DataFrame:
    first = [
        "Aarav",
        "Diya",
        "Ishaan",
        "Meera",
        "Rohan",
        "Sara",
        "Kabir",
        "Anaya",
        "Vivaan",
        "Priya",
        "Arjun",
        "Neha",
        "Liam",
        "Emma",
        "Noah",
        "Olivia",
        "Mateo",
        "Sofia",
    ]
    last = [
        "Sharma",
        "Patel",
        "Iyer",
        "Khan",
        "Singh",
        "Gupta",
        "Smith",
        "Garcia",
        "Chen",
        "Nair",
        "Das",
        "Reddy",
        "Brown",
        "Lopez",
        "Kumar",
        "Wilson",
    ]
    departments = ["Engineering", "Sales", "Marketing", "Finance", "HR", "Operations", "Support"]
    levels = ["Junior", "Mid", "Senior", "Lead", "Manager"]
    cities = ["Bengaluru", "Mumbai", "Delhi", "Pune", "Hyderabad", "Chennai", "Remote"]
    level = rng.choice(levels, size=n, p=[0.3, 0.3, 0.2, 0.12, 0.08])
    base = {
        "Junior": 600_000,
        "Mid": 1_100_000,
        "Senior": 1_800_000,
        "Lead": 2_500_000,
        "Manager": 3_000_000,
    }
    salary = np.array([base[lv] for lv in level]) * rng.normal(1, 0.12, size=n)
    hire = pd.Timestamp("2012-01-01") + pd.to_timedelta(rng.integers(0, 4600, size=n), unit="D")
    df = pd.DataFrame(
        {
            "employee_id": [f"E{10000 + i}" for i in range(n)],
            "name": [f"{rng.choice(first)} {rng.choice(last)}" for _ in range(n)],
            "department": rng.choice(departments, size=n),
            "job_level": level,
            "city": rng.choice(cities, size=n),
            "hire_date": hire.strftime("%Y-%m-%d"),
            "age": rng.integers(21, 62, size=n).astype("float"),
            "salary": salary.round(-3),
            "performance_score": rng.choice(
                [1, 2, 3, 4, 5], size=n, p=[0.05, 0.15, 0.4, 0.3, 0.1]
            ).astype("float"),
            "remote": rng.random(n) < 0.3,
            "manager_rating": rng.normal(3.8, 0.6, size=n).clip(1, 5).round(1),
        }
    )
    for col, rate in [
        ("age", 0.04),
        ("salary", 0.06),
        ("performance_score", 0.08),
        ("city", 0.05),
        ("manager_rating", 0.15),
        ("department", 0.02),
    ]:
        df.loc[rng.random(n) < rate, col] = np.nan
    dupes = df.sample(30, random_state=SEED)
    partial = df.sample(15, random_state=SEED + 1).assign(
        employee_id=lambda d: [f"E{20000 + i}" for i in range(len(d))]
    )
    out = pd.concat([df, dupes, partial], ignore_index=True)
    return out.sample(frac=1, random_state=SEED).reset_index(drop=True)


def air_quality(rng: np.random.Generator, hours: int = 4380) -> pd.DataFrame:
    frames = []
    for station, offset in [("Station A", 0.0), ("Station B", 12.0)]:
        ts = pd.date_range("2024-01-01", periods=hours, freq="h")
        t = np.arange(hours)
        daily = np.sin(2 * np.pi * t / 24)
        seasonal = np.cos(2 * np.pi * t / (24 * 365))
        pm25 = (35 + offset + 15 * seasonal + 8 * daily + rng.normal(0, 6, hours)).clip(2)
        frame = pd.DataFrame(
            {
                "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
                "station": station,
                "pm25": pm25.round(1),
                "pm10": (pm25 * rng.uniform(1.4, 1.9, hours)).round(1),
                "no2": (25 + 10 * daily + rng.normal(0, 5, hours)).clip(1).round(1),
                "o3": (40 - 12 * daily + rng.normal(0, 7, hours)).clip(1).round(1),
                "temperature_c": (24 - 6 * seasonal + 5 * daily + rng.normal(0, 1.5, hours)).round(
                    1
                ),
                "humidity_pct": (60 + 15 * seasonal - 10 * daily + rng.normal(0, 5, hours))
                .clip(5, 100)
                .round(0),
            }
        )
        for _ in range(6):  # sensor outages
            start = int(rng.integers(0, hours - 48))
            length = int(rng.integers(6, 48))
            cols = rng.choice(["pm25", "pm10", "no2", "o3"], size=2, replace=False)
            frame.loc[start : start + length, list(cols)] = np.nan
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    rng = np.random.default_rng(SEED)
    for name, builder in [
        ("sales_orders", sales_orders),
        ("employees", employees),
        ("air_quality", air_quality),
    ]:
        df = builder(rng)
        df.to_csv(OUT / f"{name}.csv", index=False)
        print(f"{name}.csv: {len(df):,} rows x {len(df.columns)} cols")


if __name__ == "__main__":
    main()
