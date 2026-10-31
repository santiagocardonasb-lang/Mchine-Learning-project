from flask import Blueprint

map_bp = Blueprint("map", __name__)

from app.blueprints.map import routes  # noqa: E402,F401
