"""Application error types and HTTP error handlers."""

from __future__ import annotations

import logging
from typing import Any

from flask import Flask, Response, jsonify, render_template, request
from flask_wtf.csrf import CSRFError
from werkzeug.exceptions import HTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base error carrying an HTTP status and a stable machine-readable code."""

    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, *, details: Any = None, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details
        if code:
            self.code = code


class ValidationError(AppError):
    status_code = 422
    code = "validation_error"


class UnsupportedFileError(AppError):
    status_code = 400
    code = "unsupported_file"


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class PayloadTooLargeError(AppError):
    status_code = 413
    code = "payload_too_large"


def _wants_json() -> bool:
    if request.path.startswith("/api/"):
        return True
    best = request.accept_mimetypes.best_match(["application/json", "text/html"])
    return best == "application/json"


def error_response(
    status: int, code: str, message: str, details: Any = None
) -> tuple[Response | str, int]:
    if _wants_json():
        payload: dict[str, Any] = {"code": code, "message": message}
        if details is not None:
            payload["details"] = details
        return jsonify({"error": payload}), status
    template = f"errors/{status}.html" if status in (404, 413) else "errors/generic.html"
    return render_template(template, status=status, message=message), status


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(AppError)
    def handle_app_error(err: AppError):
        return error_response(err.status_code, err.code, err.message, err.details)

    @app.errorhandler(CSRFError)
    def handle_csrf(err: CSRFError):
        return error_response(400, "csrf_failed", "Missing or invalid CSRF token.")

    @app.errorhandler(413)
    def handle_too_large(err: HTTPException):
        limit = app.config["MAX_UPLOAD_MB"]
        return error_response(413, "payload_too_large", f"File exceeds the {limit} MB limit.")

    @app.errorhandler(HTTPException)
    def handle_http(err: HTTPException):
        code = (err.name or "error").lower().replace(" ", "_")
        return error_response(err.code or 500, code, err.description or err.name)

    @app.errorhandler(Exception)
    def handle_unexpected(err: Exception):
        logger.exception("Unhandled error on %s %s", request.method, request.path)
        return error_response(500, "internal_error", "An unexpected error occurred.")
