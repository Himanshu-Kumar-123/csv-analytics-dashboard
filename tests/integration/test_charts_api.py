from __future__ import annotations

import json

from flask.testing import FlaskClient

from tests.helpers import SIMPLE_CSV, upload_csv


def make(client: FlaskClient, headers: dict) -> str:
    return upload_csv(client, headers, SIMPLE_CSV).get_json()["id"]


def test_chart_endpoint_types(client: FlaskClient, csrf_headers: dict) -> None:
    ds = make(client, csrf_headers)
    url = f"/api/v1/datasets/{ds}/chart"
    cases = [
        {"type": "histogram", "x": "score", "bins": 5},
        {"type": "bar", "x": "city"},
        {"type": "line", "x": "joined", "y": "score", "agg": "mean"},
        {"type": "scatter", "x": "id", "y": "score"},
        {"type": "box", "y": "score", "x": "city"},
        {"type": "pie", "x": "city"},
        {"type": "heatmap"},
        {"type": "missing"},
    ]
    for params in cases:
        resp = client.get(url, query_string=params)
        assert resp.status_code == 200, (params, resp.get_json())
        body = resp.get_json()
        assert body["figure"]["data"] and "layout" in body["figure"]
        assert body["meta"]["type"] == params["type"]


def test_chart_respects_filters(client: FlaskClient, csrf_headers: dict) -> None:
    ds = make(client, csrf_headers)
    filters = json.dumps([{"column": "city", "op": "eq", "value": "Delhi"}])
    body = client.get(
        f"/api/v1/datasets/{ds}/chart",
        query_string={"type": "bar", "x": "city", "filters": filters},
    ).get_json()
    assert body["figure"]["data"][0]["x"] == ["Delhi"]
    assert body["matched_rows"] == 3


def test_chart_validation(client: FlaskClient, csrf_headers: dict) -> None:
    ds = make(client, csrf_headers)
    url = f"/api/v1/datasets/{ds}/chart"
    assert client.get(url).status_code == 422
    assert client.get(url, query_string={"type": "pie3d"}).status_code == 422
    assert client.get(url, query_string={"type": "histogram", "x": "city"}).status_code == 422
    assert (
        client.get(url, query_string={"type": "histogram", "x": "score", "bins": 1}).status_code
        == 422
    )
    resp = client.get(url, query_string={"type": "scatter", "x": "id"})
    assert resp.status_code == 422
    assert "required" in resp.get_json()["error"]["message"]
