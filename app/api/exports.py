from __future__ import annotations

import re

from flask import Response, request
from flask.typing import ResponseReturnValue

from app.api import api_bp
from app.core.exports import EXPORT_KINDS, summary_csv
from app.core.report import build_report
from app.errors import NotFoundError
from app.schemas import FilterQuerySchema, load
from app.services.dataset_service import get_dataset_service


def _slug(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-").lower()[:60] or "dataset"


def _attachment(body: bytes, mimetype: str, filename: str) -> Response:
    response = Response(body, mimetype=mimetype)
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.headers["Cache-Control"] = "no-store"
    return response


@api_bp.get("/datasets/<dataset_id>/export/<kind>.csv")
def export_csv(dataset_id: str, kind: str) -> ResponseReturnValue:
    if kind not in EXPORT_KINDS:
        raise NotFoundError(f"Unknown export {kind!r}.", details={"allowed": list(EXPORT_KINDS)})
    args = load(FilterQuerySchema(), request.args)
    view = get_dataset_service().view(dataset_id, args["filters"])
    body = summary_csv(kind, view.frame, view.kinds)
    return _attachment(body, "text/csv", f"{_slug(view.dataset.display_name)}-{kind}-summary.csv")


@api_bp.get("/datasets/<dataset_id>/export/report.pdf")
def export_pdf(dataset_id: str) -> ResponseReturnValue:
    args = load(FilterQuerySchema(), request.args)
    view = get_dataset_service().view(dataset_id, args["filters"])
    body = build_report(
        view.frame,
        view.kinds,
        title=view.dataset.display_name,
        total_rows=len(view.full),
        filters=view.filter_summary,
    )
    return _attachment(body, "application/pdf", f"{_slug(view.dataset.display_name)}-report.pdf")
