from __future__ import annotations

from pathlib import PurePath

from flask import jsonify, request
from flask.typing import ResponseReturnValue
from werkzeug.utils import secure_filename

from app.api import api_bp
from app.errors import UnsupportedFileError, ValidationError
from app.services.dataset_service import get_dataset_service

MAX_NAME_LENGTH = 120


def _display_name(raw: str | None, filename: str) -> str:
    name = (raw or "").strip() or PurePath(filename).stem or "dataset"
    name = " ".join(name.split())
    if len(name) > MAX_NAME_LENGTH:
        raise ValidationError(f"Name must be at most {MAX_NAME_LENGTH} characters.")
    return name


@api_bp.post("/datasets")
def upload_dataset() -> ResponseReturnValue:
    upload = request.files.get("file")
    if upload is None or not upload.filename:
        raise ValidationError("No file was provided. Use the 'file' form field.")
    filename = secure_filename(upload.filename) or "upload.csv"
    if PurePath(filename).suffix.lower() != ".csv":
        raise UnsupportedFileError("Only .csv files are supported.")
    name = _display_name(request.form.get("name"), filename)
    dataset = get_dataset_service().ingest_upload(upload.stream, filename, name)
    return jsonify(dataset.to_dict(include_schema=True)), 201


@api_bp.get("/datasets")
def list_datasets() -> ResponseReturnValue:
    datasets = get_dataset_service().list()
    return jsonify({"datasets": [d.to_dict() for d in datasets]})


@api_bp.get("/datasets/<dataset_id>")
def get_dataset(dataset_id: str) -> ResponseReturnValue:
    return jsonify(get_dataset_service().get(dataset_id).to_dict(include_schema=True))


@api_bp.delete("/datasets/<dataset_id>")
def delete_dataset(dataset_id: str) -> ResponseReturnValue:
    get_dataset_service().delete(dataset_id)
    return "", 204
