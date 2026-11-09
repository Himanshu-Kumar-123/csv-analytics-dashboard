"""Registry of bundled sample datasets."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Sample:
    key: str
    title: str
    filename: str
    description: str


SAMPLES: dict[str, Sample] = {
    s.key: s
    for s in (
        Sample(
            "sales_orders",
            "Sales orders",
            "sales_orders.csv",
            "5,000 retail orders with dates, regions, product categories, prices and revenue.",
        ),
        Sample(
            "employees",
            "Employees",
            "employees.csv",
            "1,000+ employee records with deliberate missing values and duplicate rows.",
        ),
        Sample(
            "air_quality",
            "Air quality",
            "air_quality.csv",
            "Hourly pollutant and weather readings from two stations, with sensor gaps.",
        ),
    )
}
