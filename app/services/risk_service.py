from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func

from app.extensions import db
from app.models import Locality, ModelRun, Report, RiskPrediction, Upz

PERIOD_MONTHS = (1, 3, 12)
SIZE_WEIGHT = {"small": 0.5, "medium": 0.75, "large": 1.0}


def since(months: int) -> datetime:
    """Start of the window: the last `months` × 30 days, so 'last month' is never a 2-day stub."""
    return datetime.now(timezone.utc) - timedelta(days=30 * months)


def _visible(months: int):
    return Report.query.filter(Report.status != "rejected", Report.reported_at >= since(months))


def heatmap_points(months: int, locality_code: str | None = None) -> list[list[float]]:
    """[lat, lon, weight] of every non-rejected report in the window; larger piles weigh more."""
    query = _visible(months).with_entities(Report.latitude, Report.longitude, Report.size)
    if locality_code:
        query = query.join(Locality, Report.locality_id == Locality.id).filter(Locality.code == locality_code)
    return [[round(lat, 5), round(lon, 5), SIZE_WEIGHT[size]] for lat, lon, size in query]


def zone_stats(months: int) -> dict[str, dict]:
    """Per UPZ code: reports in the window, open ones, share with vectors and most common type."""
    vectors = case((Report.has_rodents | Report.has_insects | Report.has_odor, 1), else_=0)
    still_open = case((Report.status.in_(("open", "in_progress")), 1), else_=0)
    rows = (
        _visible(months)
        .join(Upz, Report.upz_id == Upz.id)
        .with_entities(Upz.code, func.count(Report.id), func.sum(still_open), func.sum(vectors))
        .group_by(Upz.code)
    )
    stats = {
        code: {
            "reports": n,
            "open": int(n_open or 0),
            "vectors_share": round((n_vec or 0) / n, 2),
            "top_type": None,
        }
        for code, n, n_open, n_vec in rows
    }

    by_type = (
        _visible(months)
        .join(Upz, Report.upz_id == Upz.id)
        .with_entities(Upz.code, Report.waste_type, func.count(Report.id))
        .group_by(Upz.code, Report.waste_type)
        .order_by(Upz.code, func.count(Report.id).desc(), Report.waste_type)
    )
    for code, waste_type, _ in by_type:
        if stats[code]["top_type"] is None:
            stats[code]["top_type"] = waste_type
    return stats


def active_predictions() -> tuple[ModelRun | None, dict[str, dict]]:
    run = ModelRun.query.filter_by(is_active=True).order_by(ModelRun.trained_at.desc()).first()
    if run is None:
        return None, {}
    rows = (
        db.session.query(Upz.code, RiskPrediction.level, RiskPrediction.probability, RiskPrediction.period)
        .join(Upz, RiskPrediction.upz_id == Upz.id)
        .filter(RiskPrediction.model_run_id == run.id)
    )
    return run, {
        code: {"level": level, "probability": round(prob, 2), "period": period}
        for code, level, prob, period in rows
    }


def risk_by_zone(months: int) -> dict:
    """Everything the map needs per UPZ: predicted level and the window's report stats."""
    run, predictions = active_predictions()
    stats = zone_stats(months)
    zones = []
    for code, name, locality in (
        db.session.query(Upz.code, Upz.name, Locality.name).join(Locality).order_by(Upz.name)
    ):
        prediction = predictions.get(code, {})
        zones.append({
            "code": code,
            "name": name,
            "locality": locality,
            "level": prediction.get("level"),
            "probability": prediction.get("probability"),
            **stats.get(code, {"reports": 0, "open": 0, "vectors_share": 0, "top_type": None}),
        })
    period = next(iter(predictions.values()))["period"] if predictions else None
    return {
        "period": period.isoformat() if period else None,
        "run_id": run.id if run else None,
        "months": months,
        "totals": {
            "reports": sum(z["reports"] for z in zones),
            "high": sum(1 for z in zones if z["level"] == "high"),
        },
        "zones": zones,
    }


def city_stats() -> dict:
    """Headline numbers for the home page."""
    run, predictions = active_predictions()
    levels = [p["level"] for p in predictions.values()]
    period = next(iter(predictions.values()))["period"] if predictions else None
    return {
        "reports_12_months": _visible(12).count(),
        "high_zones": levels.count("high"),
        "zones": Upz.query.count(),
        "period": period,
        "last_run": run.trained_at if run else None,
    }