from flask import Blueprint

main_bp = Blueprint("main", __name__)

from app.blueprints.main import feedback, routes  # noqa: E402,F401
