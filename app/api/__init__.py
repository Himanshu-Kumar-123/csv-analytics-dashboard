from flask import Blueprint, jsonify

api_bp = Blueprint("api", __name__, url_prefix="/api/v1")


@api_bp.get("/health")
def health():
    return jsonify({"status": "ok"})
