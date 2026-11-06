from flask import Blueprint

reports_bp = Blueprint("reports", __name__, url_prefix="/reports")

from app.blueprints.reports import mine, routes  # noqa: E402,F401
