from __future__ import annotations

import json

from flask.testing import FlaskClient

from tests.helpers import SIMPLE_CSV, upload_csv


def make(client: FlaskClient, headers: dict) -> str:
    return upload_csv(client, headers, SIMPLE_CSV).get_json()["id"]


def test_columns_include_operators(client: FlaskClient, csrf_headers: dict) -> None:
    ds = make(client, csrf_headers)
    cols = {
        c["name"]: c for c in client.get(f"/api/v1/datasets/{ds}/columns").get_json()["columns"]
    }
    assert "between" in cols["score"]["operators"]
    assert "contains" in cols["city"]["operators"]


def test_preview_default(client: FlaskClient, csrf_headers: dict) -> None:
    ds = make(client, csrf_headers)
    body = client.get(f"/api/v1/datasets/{ds}/preview").get_json()
    assert body["total_rows"] == 5
    assert body["matched_rows"] == 5
    assert body["rows"][0]["joined"] == "2023-01-05"
    assert body["rows"][2]["score"] is None
    assert [c["name"] for c in body["columns"]] == ["id", "name", "city", "score", "joined"]


def test_preview_sort_and_filter(client: FlaskClient, csrf_headers: dict) -> None:
    ds = make(client, csrf_headers)
    filters = json.dumps([{"column": "city", "op": "eq", "value": "Delhi"}])
    body = client.get(
        f"/api/v1/datasets/{ds}/preview",
        query_string={"filters": filters, "sort": "id", "order": "desc"},
    ).get_json()
    assert body["matched_rows"] == 3
    assert [r["id"] for r in body["rows"]] == [5, 3, 1]
    assert body["filters"] == [{"column": "city", "op": "eq", "value": "Delhi"}]


def test_preview_page_size_capped(client: FlaskClient, csrf_headers: dict) -> None:
    ds = make(client, csrf_headers)
    resp = client.get(f"/api/v1/datasets/{ds}/preview?page_size=201")
    assert resp.status_code == 422
    assert "page_size" in resp.get_json()["error"]["details"]


def test_preview_invalid_params(client: FlaskClient, csrf_headers: dict) -> None:
    ds = make(client, csrf_headers)
    base = f"/api/v1/datasets/{ds}/preview"
    assert client.get(f"{base}?page=0").status_code == 422
    assert client.get(f"{base}?order=sideways").status_code == 422
    assert client.get(f"{base}?sort=nope").status_code == 422
    assert client.get(f"{base}?filters=notjson").status_code == 422
    bad = json.dumps([{"column": "score", "op": "contains", "value": "x"}])
    resp = client.get(base, query_string={"filters": bad})
    assert resp.status_code == 422
    assert "allowed" in resp.get_json()["error"]["details"]


def test_column_values(client: FlaskClient, csrf_headers: dict) -> None:
    ds = make(client, csrf_headers)
    body = client.get(f"/api/v1/datasets/{ds}/columns/city/values?top=1").get_json()
    assert body["values"] == [{"value": "Delhi", "count": 3, "percent": 60.0}]
    assert body["other_count"] == 2
    assert client.get(f"/api/v1/datasets/{ds}/columns/nope/values").status_code == 404


def test_dataset_pages_render(client: FlaskClient, csrf_headers: dict) -> None:
    ds = make(client, csrf_headers)
    for suffix in ("", "/explore", "/statistics", "/quality", "/visualize"):
        resp = client.get(f"/datasets/{ds}{suffix}")
        assert resp.status_code == 200, suffix
        assert 'data-dataset-id="' in resp.get_data(as_text=True)
    assert client.get("/datasets/00000000-0000-0000-0000-000000000000").status_code == 404


def test_dataset_name_is_escaped_in_html(client: FlaskClient, csrf_headers: dict) -> None:
    payload = "<script>alert(1)</script>"
    ds = upload_csv(client, csrf_headers, SIMPLE_CSV, name=payload).get_json()["id"]
    html = client.get(f"/datasets/{ds}").get_data(as_text=True)
    assert payload not in html
    assert "&lt;script&gt;" in html
