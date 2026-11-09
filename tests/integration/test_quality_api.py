from __future__ import annotations

import json

from flask.testing import FlaskClient

from tests.helpers import upload_csv

DUP_CSV = "id,city,score\n1,Delhi,10\n2,Pune,\n1,Delhi,10\n3, delhi ,10\n4,,\n"


def make(client: FlaskClient, headers: dict) -> str:
    return upload_csv(client, headers, DUP_CSV).get_json()["id"]


def test_missing_endpoint(client: FlaskClient, csrf_headers: dict) -> None:
    ds = make(client, csrf_headers)
    body = client.get(f"/api/v1/datasets/{ds}/quality/missing").get_json()
    assert body["missing_cells"] == 3
    assert body["rows_with_missing"] == 2
    assert body["matched_rows"] == body["total_rows"] == 5


def test_duplicates_endpoint(client: FlaskClient, csrf_headers: dict) -> None:
    ds = make(client, csrf_headers)
    url = f"/api/v1/datasets/{ds}/quality/duplicates"
    body = client.get(url).get_json()
    assert body["duplicate_rows"] == 1
    assert body["groups"][0]["row_numbers"] == [1, 3]
    subset = client.get(
        url, query_string={"columns": json.dumps(["city", "score"]), "normalize": "true"}
    ).get_json()
    assert subset["duplicate_rows"] == 2
    assert subset["normalized"] is True


def test_duplicates_with_filters(client: FlaskClient, csrf_headers: dict) -> None:
    ds = make(client, csrf_headers)
    filters = json.dumps([{"column": "id", "op": "gte", "value": 2}])
    body = client.get(
        f"/api/v1/datasets/{ds}/quality/duplicates", query_string={"filters": filters}
    ).get_json()
    assert body["matched_rows"] == 3 and body["duplicate_rows"] == 0


def test_duplicates_validation(client: FlaskClient, csrf_headers: dict) -> None:
    ds = make(client, csrf_headers)
    url = f"/api/v1/datasets/{ds}/quality/duplicates"
    assert client.get(url, query_string={"columns": '["nope"]'}).status_code == 422
    assert client.get(url, query_string={"columns": "city"}).status_code == 422
    assert client.get(url, query_string={"max_groups": 0}).status_code == 422
    assert client.get(url, query_string={"normalize": "maybe"}).status_code == 422
