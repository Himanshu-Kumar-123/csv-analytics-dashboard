from __future__ import annotations

import io
import json

from flask.testing import FlaskClient
from pypdf import PdfReader

from tests.helpers import SIMPLE_CSV, upload_csv

INJECTION_CSV = 'label,amount\n=HYPERLINK("http://x"),1\n=HYPERLINK("http://x"),2\nok,3\n'


def make(
    client: FlaskClient, headers: dict, content: str = SIMPLE_CSV, name: str = "My Data"
) -> str:
    return upload_csv(client, headers, content, name=name).get_json()["id"]


def test_csv_exports(client: FlaskClient, csrf_headers: dict) -> None:
    ds = make(client, csrf_headers)
    for kind in ("overview", "statistics", "missing", "duplicates", "correlations"):
        resp = client.get(f"/api/v1/datasets/{ds}/export/{kind}.csv")
        assert resp.status_code == 200, kind
        assert resp.mimetype == "text/csv"
        assert resp.headers["Content-Disposition"] == (
            f'attachment; filename="my-data-{kind}-summary.csv"'
        )
        assert resp.headers["Cache-Control"] == "no-store"


def test_csv_export_applies_filters(client: FlaskClient, csrf_headers: dict) -> None:
    ds = make(client, csrf_headers)
    filters = json.dumps([{"column": "city", "op": "eq", "value": "Delhi"}])
    text = client.get(
        f"/api/v1/datasets/{ds}/export/statistics.csv", query_string={"filters": filters}
    ).get_data(as_text=True)
    assert "Pune" not in text and "Delhi" in text


def test_csv_export_formula_injection(client: FlaskClient, csrf_headers: dict) -> None:
    ds = make(client, csrf_headers, INJECTION_CSV)
    text = client.get(f"/api/v1/datasets/{ds}/export/statistics.csv").get_data(as_text=True)
    for line in text.splitlines():
        for cell in line.split(","):
            assert not cell.strip('"').startswith("="), line


def test_unknown_export_kind(client: FlaskClient, csrf_headers: dict) -> None:
    ds = make(client, csrf_headers)
    assert client.get(f"/api/v1/datasets/{ds}/export/raw.csv").status_code == 404
    assert client.get(f"/api/v1/datasets/{ds}/export/original.csv").status_code == 404


def test_pdf_export(client: FlaskClient, csrf_headers: dict) -> None:
    ds = make(client, csrf_headers)
    resp = client.get(f"/api/v1/datasets/{ds}/export/report.pdf")
    assert resp.status_code == 200 and resp.mimetype == "application/pdf"
    assert resp.headers["Content-Disposition"] == 'attachment; filename="my-data-report.pdf"'
    text = PdfReader(io.BytesIO(resp.data)).pages[0].extract_text()
    assert "Analysis summary: My Data" in text


def test_pdf_export_bad_filter(client: FlaskClient, csrf_headers: dict) -> None:
    ds = make(client, csrf_headers)
    resp = client.get(f"/api/v1/datasets/{ds}/export/report.pdf?filters=oops")
    assert resp.status_code == 422
