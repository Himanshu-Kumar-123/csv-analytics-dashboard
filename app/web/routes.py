from flask import render_template
from flask.typing import ResponseReturnValue

from app.web import web_bp


@web_bp.get("/")
def index() -> ResponseReturnValue:
    return render_template("index.html")
