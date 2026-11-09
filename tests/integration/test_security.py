from __future__ import annotations

from flask.testing import FlaskClient

from tests.helpers import SIMPLE_CSV, upload_csv


def test_no_raw_data_endpoints(client: FlaskClient, csrf_headers: dict) -> None:
    ds = upload_csv(client, csrf_headers, SIMPLE_CSV).get_json()["id"]
    for path in (
        f"/api/v1/datasets/{ds}/download",
        f"/api/v1/datasets/{ds}/raw",
        f"/api/v1/datasets/{ds}/export/original.csv",
        f"/static/../instance/data/{ds}/original.csv",
        f"/data/{ds}/original.csv",
    ):
        assert client.get(path).status_code == 404, path


def test_invalid_dataset_ids(client: FlaskClient) -> None:
    for bad in ("..%2F..%2Fetc%2Fpasswd", "not-a-uuid", "1;DROP TABLE datasets"):
        assert client.get(f"/api/v1/datasets/{bad}/preview").status_code == 404
        assert client.get(f"/datasets/{bad}").status_code == 404


def test_mutations_require_csrf(client: FlaskClient, csrf_headers: dict) -> None:
    ds = upload_csv(client, csrf_headers, SIMPLE_CSV).get_json()["id"]
    assert client.delete(f"/api/v1/datasets/{ds}").status_code == 400
    assert client.post("/api/v1/samples/employees").status_code == 400
    assert client.get(f"/api/v1/datasets/{ds}").status_code == 200


def test_preview_never_exceeds_cap(client: FlaskClient, csrf_headers: dict) -> None:
    rows = "\n".join(f"{i},{i * 2}" for i in range(500))
    ds = upload_csv(client, csrf_headers, f"a,b\n{rows}\n").get_json()["id"]
    assert client.get(f"/api/v1/datasets/{ds}/preview?page_size=500").status_code == 422
    body = client.get(f"/api/v1/datasets/{ds}/preview?page_size=200").get_json()
    assert len(body["rows"]) == 200


def test_csp_on_pages(client: FlaskClient, csrf_headers: dict) -> None:
    ds = upload_csv(client, csrf_headers, SIMPLE_CSV).get_json()["id"]
    csp = client.get(f"/datasets/{ds}/visualize").headers["Content-Security-Policy"]
    assert "script-src 'self'" in csp and "unsafe-eval" not in csp
