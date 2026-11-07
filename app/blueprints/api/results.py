from flask import jsonify, request
from flask_login import login_required

from app.blueprints.api import api_bp
from app.services import risk_service

PERIOD_ERROR = f"period must be one of {', '.join(risk_service.PERIODS)}"


def _period():
    """The ?period= key, or None when it is not one of the offered periods."""
    period = request.args.get("period", "this_month")
    return period if period in risk_service.PERIODS else None


@api_bp.get("/heatmap")
@login_required
def heatmap():
    period = _period()
    if period is None:
        return jsonify(error=PERIOD_ERROR), 400
    locality = request.args.get("locality") or None
    return jsonify(points=risk_service.heatmap_points(period, locality))


@api_bp.get("/risk")
@login_required
def risk():
    period = _period()
    if period is None:
        return jsonify(error=PERIOD_ERROR), 400
    return jsonify(risk_service.risk_by_zone(period))
