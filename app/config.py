"""Environment-specific configuration."""

from __future__ import annotations

import os
from pathlib import Path
from typing import ClassVar

MB = 1024 * 1024


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-change-me")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Populated from the instance path in create_app() when not provided.
    SQLALCHEMY_DATABASE_URI: str | None = os.environ.get("DATABASE_URL")
    DATA_DIR: str | None = os.environ.get("DATA_DIR")
    SAMPLE_DATA_DIR = os.environ.get(
        "SAMPLE_DATA_DIR", str(Path(__file__).resolve().parent.parent / "sample_data")
    )

    MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "50"))
    MAX_CONTENT_LENGTH = MAX_UPLOAD_MB * MB + 64 * 1024  # small allowance for multipart overhead
    MAX_COLUMNS = int(os.environ.get("MAX_COLUMNS", "1000"))
    MAX_HEADER_LENGTH = 256
    MAX_CELL_LENGTH = int(os.environ.get("MAX_CELL_LENGTH", "10000"))

    PREVIEW_MAX_PAGE_SIZE = 200
    CHART_MAX_POINTS = 10_000
    DATAFRAME_CACHE_SIZE = int(os.environ.get("DATAFRAME_CACHE_SIZE", "3"))

    WTF_CSRF_TIME_LIMIT = None
    WTF_CSRF_HEADERS: ClassVar[list[str]] = ["X-CSRFToken", "X-CSRF-Token"]

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    JSON_SORT_KEYS = False


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class TestingConfig(BaseConfig):
    TESTING = True
    SECRET_KEY = "test-secret"  # noqa: S105
    WTF_CSRF_ENABLED = True


class ProductionConfig(BaseConfig):
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true"


CONFIGS: dict[str, type[BaseConfig]] = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(name: str | None) -> type[BaseConfig]:
    return CONFIGS.get(
        (name or os.environ.get("APP_ENV", "development")).lower(), DevelopmentConfig
    )
