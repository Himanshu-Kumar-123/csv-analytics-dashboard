from __future__ import annotations

from pathlib import Path

from flask import Flask
from flask.testing import FlaskClient

from app import create_app
from tests.helpers import SIMPLE_CSV, upload_csv


def test_upload_returns_metadata_and_schema(client: FlaskClient, csrf_headers: dict) -> None:
    resp = upload_csv(client, csrf_headers, SIMPLE_CSV, "people.csv")
    assert resp.status_code == 201, resp.get_json()
    body = resp.get_json()
    assert body["name"] == "people"
    assert body["rows"] == 5
    assert body["columns"] == 5
    kinds = {c["name"]: c["kind"] for c in body["schema"]}
    assert kinds == {
        "id": "numeric",
        "name": "categorical",
        "city": "categorical",
        "score": "numeric",
        "joined": "datetime",
    }
    score = next(c for c in body["schema"] if c["name"] == "score")
    assert score["null_count"] == 1


def test_upload_custom_name(client: FlaskClient, csrf_headers: dict) -> None:
    resp = upload_csv(client, csrf_headers, SIMPLE_CSV, name="  My   data  ")
    assert resp.get_json()["name"] == "My data"


def test_upload_requires_csrf(client: FlaskClient) -> None:
    resp = upload_csv(client, {}, SIMPLE_CSV)
    assert resp.status_code == 400
    assert resp.get_json()["error"]["code"] == "csrf_failed"


def test_upload_missing_file(client: FlaskClient, csrf_headers: dict) -> None:
    resp = client.post("/api/v1/datasets", data={}, headers=csrf_headers)
    assert resp.status_code == 422


def test_upload_rejects_wrong_extension(client: FlaskClient, csrf_headers: dict) -> None:
    resp = upload_csv(client, csrf_headers, SIMPLE_CSV, "data.xlsx")
    assert resp.status_code == 400
    assert resp.get_json()["error"]["code"] == "unsupported_file"


def test_upload_rejects_binary_disguised_as_csv(client: FlaskClient, csrf_headers: dict) -> None:
    resp = upload_csv(client, csrf_headers, b"\x89PNG\r\n\x1a\n\x00\x00\x00", "image.csv")
    assert resp.status_code == 400
    assert resp.get_json()["error"]["code"] == "invalid_file"


def test_upload_path_traversal_filename_is_sanitised(
    client: FlaskClient, csrf_headers: dict, app: Flask
) -> None:
    resp = upload_csv(client, csrf_headers, SIMPLE_CSV, "../../etc/passwd.csv")
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["original_filename"] == "etc_passwd.csv"
    data_dir = Path(app.config["DATA_DIR"])
    assert (data_dir / body["id"] / "original.csv").is_file()
    assert not (data_dir.parent.parent / "etc").exists()


def test_upload_too_large_returns_413(instance_dir: Path) -> None:
    app = create_app("testing", instance_path=str(instance_dir), overrides={"MAX_UPLOAD_MB": 1})
    app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024
    from app.extensions import db

    with app.app_context():
        db.create_all()
    client = app.test_client()
    html = client.get("/").get_data(as_text=True)
    token = html.split('name="csrf-token" content="')[1].split('"')[0]
    big = "a,b\n" + "1234567890,1234567890\n" * 60_000  # ~1.3 MB
    resp = upload_csv(client, {"X-CSRFToken": token}, big)
    assert resp.status_code == 413
    assert resp.get_json()["error"]["code"] == "payload_too_large"
    assert list((Path(app.config["DATA_DIR"]) / ".tmp").iterdir()) == []


def test_request_body_over_max_content_length_is_413(app: Flask, csrf_headers: dict) -> None:
    app.config["MAX_CONTENT_LENGTH"] = 1024
    client = app.test_client()
    resp = upload_csv(client, csrf_headers, "a\n" + "1\n" * 2000)
    assert resp.status_code == 413


def test_invalid_upload_leaves_no_files(
    client: FlaskClient, csrf_headers: dict, app: Flask
) -> None:
    resp = upload_csv(client, csrf_headers, "a,b,c\n")
    assert resp.status_code == 400
    data_dir = Path(app.config["DATA_DIR"])
    assert [p.name for p in data_dir.iterdir()] == [".tmp"]
    assert list((data_dir / ".tmp").iterdir()) == []


def test_list_get_delete(client: FlaskClient, csrf_headers: dict, app: Flask) -> None:
    first = upload_csv(client, csrf_headers, SIMPLE_CSV, "one.csv").get_json()
    second = upload_csv(client, csrf_headers, SIMPLE_CSV, "two.csv").get_json()

    listing = client.get("/api/v1/datasets").get_json()["datasets"]
    assert [d["id"] for d in listing] == [second["id"], first["id"]]
    assert "schema" not in listing[0]

    detail = client.get(f"/api/v1/datasets/{first['id']}").get_json()
    assert detail["schema"][0]["name"] == "id"

    resp = client.delete(f"/api/v1/datasets/{first['id']}", headers=csrf_headers)
    assert resp.status_code == 204
    assert client.get(f"/api/v1/datasets/{first['id']}").status_code == 404
    assert not (Path(app.config["DATA_DIR"]) / first["id"]).exists()


def test_delete_requires_csrf(client: FlaskClient, csrf_headers: dict) -> None:
    ds = upload_csv(client, csrf_headers, SIMPLE_CSV).get_json()
    assert client.delete(f"/api/v1/datasets/{ds['id']}").status_code == 400


def test_unknown_and_malformed_ids_are_404(client: FlaskClient, csrf_headers: dict) -> None:
    assert client.get("/api/v1/datasets/00000000-0000-0000-0000-000000000000").status_code == 404
    assert client.get("/api/v1/datasets/..%2F..%2Fetc").status_code == 404
    resp = client.delete("/api/v1/datasets/nope", headers=csrf_headers)
    assert resp.status_code == 404


def test_datasets_persist_across_restart(instance_dir: Path) -> None:
    from app.extensions import db
    from app.services.dataset_service import get_dataset_service

    app1 = create_app("testing", instance_path=str(instance_dir))
    with app1.app_context():
        db.create_all()
    c1 = app1.test_client()
    token = c1.get("/").get_data(as_text=True).split('name="csrf-token" content="')[1]
    token = token.split('"')[0]
    ds = upload_csv(c1, {"X-CSRFToken": token}, SIMPLE_CSV).get_json()

    app2 = create_app("testing", instance_path=str(instance_dir))
    c2 = app2.test_client()
    listing = c2.get("/api/v1/datasets").get_json()["datasets"]
    assert [d["id"] for d in listing] == [ds["id"]]
    with app2.app_context():
        df = get_dataset_service().load_frame(ds["id"])
    assert len(df) == 5
    assert str(df["joined"].dtype).startswith("datetime64")


def test_samples_list_and_import(client: FlaskClient, csrf_headers: dict) -> None:
    samples = client.get("/api/v1/samples").get_json()["samples"]
    assert {s["key"] for s in samples} == {"sales_orders", "employees", "air_quality"}
    for s in samples:
        resp = client.post(f"/api/v1/samples/{s['key']}", headers=csrf_headers)
        assert resp.status_code == 201, resp.get_json()
        assert resp.get_json()["is_sample"] is True
        assert resp.get_json()["rows"] > 1000
    assert client.post("/api/v1/samples/unknown", headers=csrf_headers).status_code == 404


def test_migrations_create_schema(instance_dir: Path) -> None:
    from flask_migrate import upgrade
    from sqlalchemy import inspect

    from app.extensions import db

    app = create_app("testing", instance_path=str(instance_dir))
    with app.app_context():
        upgrade()
        assert "datasets" in inspect(db.engine).get_table_names()
