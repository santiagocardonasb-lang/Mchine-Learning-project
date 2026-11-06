
import io
import threading

import joblib
import pandas as pd
from flask import Flask, current_app

from app.extensions import db
from app.models import Locality, ModelRun, Report, RiskPrediction, Upz
from app.models.user import utcnow
from ml import config as ml_config
from ml.features import REPORT_COLUMNS, build_panel, zone_table
from ml.train import NotEnoughData, train

# One training at a time per process; a second request while one runs is skipped.
_lock = threading.Lock()
# Start of the last background attempt, failed or not: a failing run must not retrain on every new report.
_last_attempt = None


def reports_frame() -> pd.DataFrame:
    rows = (
        db.session.query(Upz.code, Report.reported_at, Report.updated_at, Report.size,
                         Report.has_rodents, Report.has_insects, Report.has_odor,
                         Report.near_water, Report.status)
        .join(Upz, Report.upz_id == Upz.id)
        .filter(Report.status != "rejected")
        .all()
    )
    return pd.DataFrame(rows, columns=REPORT_COLUMNS)


def zones_frame() -> pd.DataFrame:
    rows = db.session.query(Upz.code, Locality.code, Upz.area_km2, Upz.critical_points,
                            Upz.public_space_m2_per_inhabitant).join(Locality).all()
    zones = pd.DataFrame(rows, columns=["upz_code", "locality_code", "area_km2", "critical_points",
                                        "public_space_m2_per_inhabitant"])
    localities = pd.DataFrame(db.session.query(Locality.code, Locality.population).all(),
                              columns=["code", "population"])
    return zone_table(zones, localities)


def run(trigger: str) -> ModelRun:
    """Train on every non-rejected report, store the run and make it the active one."""
    result = train(build_panel(reports_frame(), zones_frame()))

    buffer = io.BytesIO()
    joblib.dump(result.model, buffer)
    run = ModelRun(trigger=trigger, n_rows=result.n_rows, params=result.params,
                   metrics=result.metrics, artifact=buffer.getvalue())
    db.session.add(run)

    upz_ids = dict(db.session.query(Upz.code, Upz.id).all())
    for row in result.predictions.itertuples(index=False):
        db.session.add(RiskPrediction(model_run=run, upz_id=upz_ids[row.upz_code], period=row.period,
                                      level=row.level, probability=float(row.probability)))

    # Old artifacts are dropped to save space; their params and metrics stay for the run history.
    db.session.flush()
    ModelRun.query.filter(ModelRun.id != run.id).update({"is_active": False, "artifact": None})
    run.is_active = True
    db.session.commit()
    return run


def active_run() -> ModelRun | None:
    # Latest first: two concurrent runs in different processes can both end up active.
    return ModelRun.query.filter_by(is_active=True).order_by(ModelRun.trained_at.desc()).first()


def recent_runs(limit: int = 10) -> list[ModelRun]:
    return ModelRun.query.order_by(ModelRun.trained_at.desc()).limit(limit).all()


def reports_since_last_run() -> int:
    """Non-rejected citizen reports created after the latest run and the latest attempt."""
    query = Report.query.filter(Report.source == "user", Report.status != "rejected")
    last = ModelRun.query.order_by(ModelRun.trained_at.desc()).first()
    if last is not None:
        query = query.filter(Report.reported_at > last.trained_at)
    if _last_attempt is not None:
        query = query.filter(Report.reported_at > _last_attempt)
    return query.count()


def is_running() -> bool:
    return _lock.locked()


def _run_locked(app: Flask, trigger: str) -> None:
    global _last_attempt
    _last_attempt = utcnow()
    with app.app_context():
        try:
            run(trigger)
        except NotEnoughData as error:
            app.logger.warning("Training skipped: %s", error)
        except Exception:
            db.session.rollback()
            app.logger.exception("Training (%s) failed", trigger)
        finally:
            db.session.remove()
            _lock.release()


def start(trigger: str) -> bool:
    """Train in a background thread so the request returns at once. False if one is running."""
    if not _lock.acquire(blocking=False):
        return False
    app = current_app._get_current_object()
    if app.config.get("TRAIN_IN_BACKGROUND", True):
        threading.Thread(target=_run_locked, args=(app, trigger), daemon=True).start()
    else:
        _run_locked(app, trigger)
    return True


def maybe_retrain(report: Report) -> None:
    """report_service.on_created hook: retrain once enough new citizen reports arrived."""
    if reports_since_last_run() >= ml_config.AUTO_RETRAIN_THRESHOLD:
        start("auto")


def error_reading(metrics: dict) -> list[str]:
    """Plain sentences about where the active model fails on the test months."""
    cm = metrics["test"]["confusion_matrix"]  # rows: true low/medium/high, columns: predicted
    total = sum(map(sum, cm))
    wrong = total - sum(cm[i][i] for i in range(3))
    adjacent = cm[0][1] + cm[1][0] + cm[1][2] + cm[2][1]
    high_total = sum(cm[2])
    sentences = [
        f"{wrong} of {total} zone-months in the test months were misclassified; "
        f"{adjacent} of those errors ({adjacent / wrong:.0%}) are between neighboring levels."
        if wrong else "Every zone-month in the test months was classified correctly.",
        f"A high-risk zone was predicted as low {cm[2][0]} times out of {high_total}, the costliest "
        "error because that zone would not be prioritized for collection.",
        f"A low-risk zone was predicted as high {cm[0][2]} times, which would send collection "
        "where it was not needed.",
    ]
    return sentences
