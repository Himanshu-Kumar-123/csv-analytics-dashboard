from __future__ import annotations

from flask import jsonify, request
from flask.typing import ResponseReturnValue

from app.api import api_bp
from app.core.statistics import correlations, describe
from app.schemas import CorrelationQuerySchema, FilterQuerySchema, load
from app.services.dataset_service import DatasetView, get_dataset_service


def _envelope(view: DatasetView, payload: dict[str, object]) -> dict[str, object]:
    return {
        **payload,
        "total_rows": len(view.full),
        "matched_rows": len(view.frame),
        "filters": view.filter_summary,
    }


@api_bp.get("/datasets/<dataset_id>/statistics")
def dataset_statistics(dataset_id: str) -> ResponseReturnValue:
    args = load(FilterQuerySchema(), request.args)
    view = get_dataset_service().view(dataset_id, args["filters"])
    return jsonify(_envelope(view, describe(view.frame, view.kinds)))


@api_bp.get("/datasets/<dataset_id>/correlations")
def dataset_correlations(dataset_id: str) -> ResponseReturnValue:
    args = load(CorrelationQuerySchema(), request.args)
    view = get_dataset_service().view(dataset_id, args["filters"])
    return jsonify(_envelope(view, correlations(view.frame, view.kinds, args["method"])))
