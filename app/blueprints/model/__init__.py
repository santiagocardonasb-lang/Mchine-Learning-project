from flask import Blueprint

model_bp = Blueprint("model", __name__)

from app.blueprints.model import inference, routes  # noqa: E402,F401
