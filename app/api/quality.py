from __future__ import annotations

from flask import jsonify, request
from flask.typing import ResponseReturnValue

from app.api import api_bp
from app.core.quality import duplicates, missing_summary, parse_columns_param
from app.schemas import DuplicatesQuerySchema, FilterQuerySchema, load
from app.services.dataset_service import get_dataset_service


@api_bp.get("/datasets/<dataset_id>/quality/missing")
def quality_missing(dataset_id: str) -> ResponseReturnValue:
    args = load(FilterQuerySchema(), request.args)
    view = get_dataset_service().view(dataset_id, args["filters"])
    result = missing_summary(view.frame, view.kinds)
    result.update(
        total_rows=len(view.full), matched_rows=len(view.frame), filters=view.filter_summary
    )
    return jsonify(result)


@api_bp.get("/datasets/<dataset_id>/quality/duplicates")
def quality_duplicates(dataset_id: str) -> ResponseReturnValue:
    args = load(DuplicatesQuerySchema(), request.args)
    view = get_dataset_service().view(dataset_id, args["filters"])
    columns = parse_columns_param(args["columns"], view.frame)
    result = duplicates(
        view.frame, columns, normalize=args["normalize"], max_groups=args["max_groups"]
    )
    result.update(
        total_rows=len(view.full), matched_rows=len(view.frame), filters=view.filter_summary
    )
    return jsonify(result)
