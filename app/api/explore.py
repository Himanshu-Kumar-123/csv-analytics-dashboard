from __future__ import annotations

from flask import jsonify, request
from flask.typing import ResponseReturnValue

from app.api import api_bp
from app.core.explore import preview, value_counts
from app.core.filters import OPERATORS_BY_KIND
from app.errors import NotFoundError
from app.schemas import PreviewQuerySchema, ValuesQuerySchema, load
from app.services.dataset_service import get_dataset_service


@api_bp.get("/datasets/<dataset_id>/columns")
def list_columns(dataset_id: str) -> ResponseReturnValue:
    dataset = get_dataset_service().get(dataset_id)
    columns = [{**col, "operators": list(OPERATORS_BY_KIND[col["kind"]])} for col in dataset.schema]
    return jsonify({"columns": columns})


@api_bp.get("/datasets/<dataset_id>/preview")
def preview_rows(dataset_id: str) -> ResponseReturnValue:
    args = load(PreviewQuerySchema(), request.args)
    view = get_dataset_service().view(dataset_id, args["filters"])
    result = preview(
        view.frame,
        page=args["page"],
        page_size=args["page_size"],
        sort=args["sort"],
        order=args["order"],
    )
    result["columns"] = [{"name": n, "kind": k} for n, k in view.kinds.items()]
    result["total_rows"] = len(view.full)
    result["filters"] = view.filter_summary
    return jsonify(result)


@api_bp.get("/datasets/<dataset_id>/columns/<path:column>/values")
def column_values(dataset_id: str, column: str) -> ResponseReturnValue:
    args = load(ValuesQuerySchema(), request.args)
    view = get_dataset_service().view(dataset_id, args["filters"])
    if column not in view.frame.columns:
        raise NotFoundError(f"Column {column!r} not found.")
    result = value_counts(view.frame[column], args["top"])
    result["column"] = column
    result["kind"] = view.kinds[column]
    return jsonify(result)
