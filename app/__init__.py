"""CSV Analytics Dashboard application factory."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from flask import Flask

from app.config import get_config
from app.errors import register_error_handlers
from app.extensions import csrf, db, migrate
from app.security import register_security_headers


def create_app(
    config_name: str | None = None,
    *,
    instance_path: str | None = None,
    overrides: dict[str, Any] | None = None,
) -> Flask:
    instance_path = instance_path or os.environ.get("APP_INSTANCE_PATH")
    app = Flask(
        __name__,
        instance_path=str(Path(instance_path).resolve()) if instance_path else None,
        instance_relative_config=True,
    )
    app.config.from_object(get_config(config_name))
    if overrides:
        app.config.update(overrides)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        db_path = Path(app.instance_path) / "app.db"
        app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
    if not app.config.get("DATA_DIR"):
        app.config["DATA_DIR"] = str(Path(app.instance_path) / "data")
    Path(app.config["DATA_DIR"]).mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.DEBUG if app.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    db.init_app(app)
    migrate.init_app(app, db, directory=str(Path(__file__).resolve().parent.parent / "migrations"))
    csrf.init_app(app)

    from app import models  # noqa: F401
    from app.api import api_bp
    from app.web import web_bp

    app.register_blueprint(api_bp)
    app.register_blueprint(web_bp)

    register_error_handlers(app)
    register_security_headers(app)
    return app
