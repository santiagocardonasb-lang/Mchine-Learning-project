from flask import Blueprint

monitoring_bp = Blueprint("monitoring", __name__, url_prefix="/admin/monitoring")

from app.blueprints.monitoring import routes  # noqa: E402,F401
