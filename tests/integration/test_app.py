from flask.testing import FlaskClient


def test_health(client: FlaskClient) -> None:
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_index_renders_with_csrf_meta(client: FlaskClient) -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    assert 'name="csrf-token"' in resp.get_data(as_text=True)


def test_security_headers_present(client: FlaskClient) -> None:
    resp = client.get("/")
    csp = resp.headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "script-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"


def test_api_404_is_json(client: FlaskClient) -> None:
    resp = client.get("/api/v1/does-not-exist")
    assert resp.status_code == 404
    body = resp.get_json()
    assert body["error"]["code"] == "not_found"


def test_html_404_is_page(client: FlaskClient) -> None:
    resp = client.get("/nope", headers={"Accept": "text/html"})
    assert resp.status_code == 404
    assert "text/html" in resp.content_type


def test_json_responses_not_cached(client: FlaskClient) -> None:
    assert client.get("/api/v1/health").headers["Cache-Control"] == "no-store"
