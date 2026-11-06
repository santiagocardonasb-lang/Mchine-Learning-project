from datetime import datetime, timezone

from app.extensions import db
from app.models import Locality, ModelRun, Report, RiskPrediction, Upz


def _current_month_bounds() -> tuple[datetime, datetime]:
    # Aware UTC bounds: Postgres compares them exactly against timestamptz, and SQLite
    # stores timestamps as UTC text without offset, which is how it formats these bounds too.
    start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


def reports_this_month() -> int:
    start, end = _current_month_bounds()
    return Report.query.filter(
        Report.source == "user",
        Report.status != "rejected",
        Report.reported_at >= start,
        Report.reported_at < end,
    ).count()


def top_priority_zones(limit: int = 5) -> list[dict]:
    # Latest active run only, the same rule as training_service.active_run().
    run = ModelRun.query.filter_by(is_active=True).order_by(ModelRun.trained_at.desc()).first()
    if run is None:
        return []
    rows = (
        db.session.query(Upz.name, Locality.name, RiskPrediction.probability)
        .select_from(RiskPrediction)
        .join(Upz, RiskPrediction.upz_id == Upz.id)
        .join(Locality, Upz.locality_id == Locality.id)
        .filter(RiskPrediction.model_run_id == run.id, RiskPrediction.level == "high")
        .order_by(RiskPrediction.probability.desc())
        .limit(limit)
        .all()
    )
    return [{"upz": upz, "locality": locality, "probability": probability}
            for upz, locality, probability in rows]
