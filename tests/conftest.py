from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app import create_app
from app.extensions import db

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def instance_dir(tmp_path: Path) -> Path:
    path = tmp_path / "instance"
    path.mkdir()
    return path


@pytest.fixture
def app(instance_dir: Path) -> Iterator[Flask]:
    application = create_app("testing", instance_path=str(instance_dir))
    with application.app_context():
        db.create_all()
    yield application


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    return app.test_client()


@pytest.fixture
def csrf_token(client: FlaskClient) -> str:
    html = client.get("/").get_data(as_text=True)
    match = re.search(r'name="csrf-token" content="([^"]+)"', html)
    assert match, "CSRF meta tag missing"
    return match.group(1)


@pytest.fixture
def csrf_headers(csrf_token: str) -> dict[str, str]:
    return {"X-CSRFToken": csrf_token}
