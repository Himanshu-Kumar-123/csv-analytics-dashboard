from __future__ import annotations

from flask import jsonify
from flask.typing import ResponseReturnValue

from app.api import api_bp
from app.services.dataset_service import get_dataset_service
from app.services.samples import SAMPLES


@api_bp.get("/samples")
def list_samples() -> ResponseReturnValue:
    return jsonify(
        {
            "samples": [
                {"key": s.key, "title": s.title, "description": s.description}
                for s in SAMPLES.values()
            ]
        }
    )


@api_bp.post("/samples/<key>")
def import_sample(key: str) -> ResponseReturnValue:
    dataset = get_dataset_service().ingest_sample(key)
    return jsonify(dataset.to_dict(include_schema=True)), 201
