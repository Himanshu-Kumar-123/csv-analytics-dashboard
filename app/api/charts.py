from __future__ import annotations

from flask import current_app, jsonify, request
from flask.typing import ResponseReturnValue

from app.api import api_bp
from app.core.charts import ChartSpec, build_chart
from app.schemas import ChartQuerySchema, load
from app.services.dataset_service import get_dataset_service


@api_bp.get("/datasets/<dataset_id>/chart")
def dataset_chart(dataset_id: str) -> ResponseReturnValue:
    args = load(ChartQuerySchema(), request.args)
    view = get_dataset_service().view(dataset_id, args.pop("filters"))
    spec = ChartSpec(
        type=args["type"],
        x=args["x"] or None,
        y=args["y"] or None,
        color=args["color"] or None,
        agg=args["agg"],
        bins=args["bins"],
        top=args["top"],
        freq=args["freq"],
        method=args["method"],
    )
    result = build_chart(
        view.frame, view.kinds, spec, max_points=current_app.config["CHART_MAX_POINTS"]
    )
    result.update(
        total_rows=len(view.full), matched_rows=len(view.frame), filters=view.filter_summary
    )
    return jsonify(result)
