from __future__ import annotations

import json

from flask.testing import FlaskClient

from tests.helpers import SIMPLE_CSV, upload_csv


def make(client: FlaskClient, headers: dict) -> str:
    return upload_csv(client, headers, SIMPLE_CSV).get_json()["id"]


def test_statistics_endpoint(client: FlaskClient, csrf_headers: dict) -> None:
    ds = make(client, csrf_headers)
    body = client.get(f"/api/v1/datasets/{ds}/statistics").get_json()
    assert body["total_rows"] == body["matched_rows"] == 5
    numeric = {c["column"]: c for c in body["numeric"]}
    assert numeric["score"]["missing"] == 1
    assert {c["column"] for c in body["categorical"]} >= {"name", "city"}
    assert [c["column"] for c in body["datetime"]] == ["joined"]


def test_statistics_respects_filters(client: FlaskClient, csrf_headers: dict) -> None:
    ds = make(client, csrf_headers)
    filters = json.dumps([{"column": "city", "op": "eq", "value": "Delhi"}])
    body = client.get(
        f"/api/v1/datasets/{ds}/statistics", query_string={"filters": filters}
    ).get_json()
    assert body["matched_rows"] == 3
    assert body["summary"]["rows"] == 3
    assert body["filters"][0]["column"] == "city"


def test_statistics_invalid_filter(client: FlaskClient, csrf_headers: dict) -> None:
    ds = make(client, csrf_headers)
    bad = json.dumps([{"column": "nope", "op": "eq", "value": 1}])
    resp = client.get(f"/api/v1/datasets/{ds}/statistics", query_string={"filters": bad})
    assert resp.status_code == 422


def test_correlations_endpoint(client: FlaskClient, csrf_headers: dict) -> None:
    ds = make(client, csrf_headers)
    body = client.get(f"/api/v1/datasets/{ds}/correlations?method=spearman").get_json()
    assert body["method"] == "spearman"
    assert body["columns"] == ["id", "score"]
    assert len(body["matrix"]) == 2
    assert client.get(f"/api/v1/datasets/{ds}/correlations?method=kendall").status_code == 422


def test_statistics_unknown_dataset(client: FlaskClient) -> None:
    resp = client.get("/api/v1/datasets/00000000-0000-0000-0000-000000000000/statistics")
    assert resp.status_code == 404
