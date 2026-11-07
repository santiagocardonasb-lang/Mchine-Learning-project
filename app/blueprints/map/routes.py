from flask import render_template
from flask_login import login_required

from app.blueprints.map import map_bp
from app.services import stats_service


@map_bp.route("/map")
@login_required
def index():
    return render_template(
        "map/index.html",
        priority_zones=stats_service.top_priority_zones(),
    )
