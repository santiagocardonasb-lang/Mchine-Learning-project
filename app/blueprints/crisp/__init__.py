from flask import Blueprint

crisp_bp = Blueprint("crisp", __name__, url_prefix="/crisp-ml")

from app.blueprints.crisp import routes  # noqa: E402,F401
