from flask import current_app, jsonify, request, send_from_directory

from app.blueprints.api import api_bp
from app.services import geo_service


def _geojson(filename: str):
    return send_from_directory(
        current_app.static_folder + "/geo", filename, mimetype="application/json"
    )


@api_bp.get("/geo/localities")
def localities():
    return _geojson("localities.geojson")


@api_bp.get("/geo/upz")
def upz():
    return _geojson("upz.geojson")


@api_bp.get("/geo/locate")
def locate():
    try:
        lat = float(request.args["lat"])
        lon = float(request.args["lon"])
    except (KeyError, ValueError):
        return jsonify(error="lat and lon must be numbers"), 400
    match = geo_service.locate(lat, lon)
    if match is None:
        return jsonify(error="Outside the covered area"), 404
    return jsonify(match.to_dict())


@api_bp.get("/neighborhoods")
def neighborhoods():
    return jsonify(geo_service.search_neighborhoods(request.args.get("q", "")))
