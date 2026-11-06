from flask import jsonify, request

from app.blueprints.api import api_bp
from app.services import risk_service


def _months():
    """The ?months= window, or None when it is not one of the offered periods."""
    try:
        months = int(request.args.get("months", 3))
    except ValueError:
        return None
    return months if months in risk_service.PERIOD_MONTHS else None


@api_bp.get("/heatmap")
def heatmap():
    months = _months()
    if months is None:
        return jsonify(error=f"months must be one of {risk_service.PERIOD_MONTHS}"), 400
    locality = request.args.get("locality") or None
    return jsonify(points=risk_service.heatmap_points(months, locality))


@api_bp.get("/risk")
def risk():
    months = _months()
    if months is None:
        return jsonify(error=f"months must be one of {risk_service.PERIOD_MONTHS}"), 400
    return jsonify(risk_service.risk_by_zone(months))