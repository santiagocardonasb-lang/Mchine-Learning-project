from flask import render_template

from app.blueprints.map import map_bp
from app.services import stats_service


@map_bp.route("/map")
def index():
    return render_template(
        "map/index.html",
        reports_this_month=stats_service.reports_this_month(),
        priority_zones=stats_service.top_priority_zones(),
    )
