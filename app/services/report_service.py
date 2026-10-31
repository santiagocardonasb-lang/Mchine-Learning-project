from collections.abc import Callable

from flask import current_app

from app.extensions import db
from app.models import Locality, Report, Upz, User
from app.services import geo_service

# Called with each new report after it is committed. Part 2 appends the auto-retrain trigger.
on_created: list[Callable[[Report], None]] = []


class OutsideCoverage(Exception):
    """The point is not inside any UPZ of the covered urban area."""


class ZonesNotLoaded(Exception):
    """The point is covered by the GeoJSON but the zone tables are empty or stale."""


def create(
    user: User,
    lat: float,
    lon: float,
    waste_type: str,
    size: str,
    has_rodents: bool,
    has_insects: bool,
    has_odor: bool,
    near_water: bool,
    description: str | None,
) -> Report:
    match = geo_service.locate(lat, lon)
    if match is None:
        raise OutsideCoverage()
    # locate() reads the GeoJSON, so a missing row means the zone tables were never loaded.
    locality = Locality.query.filter_by(code=match.locality_code).one_or_none()
    upz = Upz.query.filter_by(code=match.upz_code).one_or_none()
    if locality is None or upz is None:
        current_app.logger.error("Zones are not loaded; run `flask load-zones`")
        raise ZonesNotLoaded()
    report = Report(
        user=user,
        latitude=lat,
        longitude=lon,
        locality=locality,
        upz=upz,
        neighborhood=match.neighborhood,
        waste_type=waste_type,
        size=size,
        has_rodents=has_rodents,
        has_insects=has_insects,
        has_odor=has_odor,
        near_water=near_water,
        description=description,
    )
    db.session.add(report)
    db.session.commit()
    # The report is already saved; a failing hook must not turn that into an error page.
    for hook in on_created:
        try:
            hook(report)
        except Exception:
            current_app.logger.exception("on_created hook %r failed for report %s", hook, report.id)
    return report


def public_dict(report: Report) -> dict:
    return {
        "id": report.id,
        "latitude": report.latitude,
        "longitude": report.longitude,
        "locality": report.locality.name if report.locality else None,
        "upz": report.upz.name if report.upz else None,
        "neighborhood": report.neighborhood,
        "reported_at": report.reported_at.isoformat(),
        "waste_type": report.waste_type,
        "size": report.size,
        "status": report.status,
    }
