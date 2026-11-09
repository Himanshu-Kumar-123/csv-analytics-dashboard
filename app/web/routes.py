from flask import render_template
from flask.typing import ResponseReturnValue

from app.services.dataset_service import get_dataset_service
from app.web import web_bp


@web_bp.get("/")
def index() -> ResponseReturnValue:
    return render_template("index.html")


def _render_dataset_page(template: str, dataset_id: str) -> ResponseReturnValue:
    dataset = get_dataset_service().get(dataset_id)
    return render_template(template, dataset=dataset)


@web_bp.get("/datasets/<dataset_id>")
def dataset_overview(dataset_id: str) -> ResponseReturnValue:
    return _render_dataset_page("dataset/overview.html", dataset_id)


@web_bp.get("/datasets/<dataset_id>/explore")
def dataset_explore(dataset_id: str) -> ResponseReturnValue:
    return _render_dataset_page("dataset/explore.html", dataset_id)


@web_bp.get("/datasets/<dataset_id>/statistics")
def dataset_statistics(dataset_id: str) -> ResponseReturnValue:
    return _render_dataset_page("dataset/statistics.html", dataset_id)


@web_bp.get("/datasets/<dataset_id>/quality")
def dataset_quality(dataset_id: str) -> ResponseReturnValue:
    return _render_dataset_page("dataset/quality.html", dataset_id)


@web_bp.get("/datasets/<dataset_id>/visualize")
def dataset_visualize(dataset_id: str) -> ResponseReturnValue:
    return _render_dataset_page("dataset/visualize.html", dataset_id)
