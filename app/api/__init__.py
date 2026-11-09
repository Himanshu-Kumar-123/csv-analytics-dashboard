from flask import Blueprint, jsonify
from flask.typing import ResponseReturnValue

api_bp = Blueprint("api", __name__, url_prefix="/api/v1")


@api_bp.get("/health")
def health() -> ResponseReturnValue:
    return jsonify({"status": "ok"})


from app.api import datasets, explore, samples, statistics  # noqa: E402, F401
