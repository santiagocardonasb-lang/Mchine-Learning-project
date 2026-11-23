import io
import math
import time
from dataclasses import dataclass

import joblib
import pandas as pd
from flask import current_app
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models import AppEvent, InferenceLog, ModelRun, Upz, User
from app.services import training_service
from ml import config as ml_config
from ml.features import NotEnoughData, zone_row

PAGE_SIZE = 25
NO_MODEL = "No trained model is available yet. Try again after the first training run."

# Unpickling a forest takes longer than predicting with it, so the active model stays loaded.
# Keyed by id and training time: a recreated database can reuse a run id.
_loaded: tuple[tuple, object] | None = None


class InferenceUnavailable(Exception):
    """The risk check could not run; the message is shown to the user."""


@dataclass
class ZoneRisk:
    upz: Upz
    run: ModelRun
    period: object  # date of the predicted month
    level: str
    probability: float
    probabilities: dict[str, float]
    features: dict[str, float]
    duration_ms: float


def _model(run: ModelRun):
    # The artifact is the joblib dump training_service.run wrote to our own database, never user input.
    global _loaded
    key = (run.id, run.trained_at)
    if _loaded is None or _loaded[0] != key:
        # Only a cache miss reads the blob; active_run() leaves it deferred.
        artifact = db.session.query(ModelRun.artifact).filter_by(id=run.id).scalar()
        if artifact is None:
            raise InferenceUnavailable(NO_MODEL)
        _loaded = (key, joblib.load(io.BytesIO(artifact)))
    return _loaded[1]


def _predict(upz: Upz, run: ModelRun) -> tuple:
    model = _model(run)
    row = zone_row(training_service.reports_frame(), training_service.zones_frame(), upz.code)
    # The columns the model was trained with, so a run trained before a feature change still works.
    columns = list(getattr(model, "feature_names_in_", ml_config.FEATURES))
    probabilities = model.predict_proba(row[columns])[0]
    by_level = {level: float(p) for level, p in zip(model.classes_, probabilities)}
    level = max(by_level, key=by_level.get)
    period = (row["month"].iloc[0] + pd.offsets.MonthBegin(1)).date()
    features = {name: float(row[name].iloc[0]) for name in columns}
    return period, level, by_level, features


def predict_zone(user: User, upz: Upz) -> ZoneRisk:
    """Predict next month's risk of one UPZ with the active model and log the inference."""
    started = time.perf_counter()
    run = training_service.active_run()
    result = failure = logged = None
    try:
        if run is None:
            raise InferenceUnavailable(NO_MODEL)
        result = _predict(upz, run)
    except InferenceUnavailable as error:
        failure, logged = error, str(error)
    except NotEnoughData as error:
        failure = InferenceUnavailable("There are not enough reports from complete months to check this zone yet.")
        logged = str(error)
    except Exception as error:
        current_app.logger.exception("Risk check failed for UPZ %s", upz.code)
        failure = InferenceUnavailable("The risk check failed. The problem was logged; please try again later.")
        logged = repr(error)
    duration_ms = (time.perf_counter() - started) * 1000

    log = InferenceLog(user_id=user.id, model_run_id=run.id if run else None, upz_id=upz.id, kind="zone",
                       duration_ms=duration_ms, status="error" if failure else "ok", error=logged)
    if result:
        period, level, probabilities, features = result
        log.level, log.probability = level, probabilities[level]
    db.session.add(log)
    db.session.add(AppEvent(kind="inference", user_id=user.id, duration_ms=duration_ms,
                            message=f"UPZ {upz.code}: {log.level or logged}"))
    db.session.commit()

    if failure:
        raise failure
    return ZoneRisk(upz, run, period, level, probabilities[level], probabilities, features, duration_ms)


def zones() -> list[Upz]:
    return Upz.query.options(selectinload(Upz.locality)).order_by(Upz.name).all()


def history(user: User, page: int):
    """Inference logs, newest first: every user's for admins, the user's own otherwise."""
    query = InferenceLog.query.options(selectinload(InferenceLog.user), selectinload(InferenceLog.upz))
    if not user.is_admin:
        query = query.filter_by(user_id=user.id)
    return query.order_by(InferenceLog.created_at.desc(), InferenceLog.id.desc()).paginate(
        page=page, per_page=PAGE_SIZE, error_out=False
    )


# Model demonstration: any visitor enters the features of one zone-month and gets a prediction.

BOUNDS = {"share_large": (0, 1), "share_vectors": (0, 1), "share_near_water": (0, 1), "month_of_year": (1, 12)}


def demo_columns() -> list[str]:
    """The inputs of the active model, in the order it was trained with."""
    run = training_service.active_run()
    if run is None:
        raise InferenceUnavailable(NO_MODEL)
    return list(getattr(_model(run), "feature_names_in_", ml_config.FEATURES))


def example_features(upz: Upz) -> dict[str, float]:
    """A real starting point: the zone's last complete month, built as for training."""
    columns = demo_columns()
    row = zone_row(training_service.reports_frame(), training_service.zones_frame(), upz.code)
    return {name: round(float(row[name].iloc[0]), 3) for name in columns}


def clean_values(form) -> tuple[dict[str, float], list[str]]:
    """Numbers within their natural range: shares 0-1, month 1-12, change any sign, counts and rates >= 0."""
    values, errors = {}, []
    for name in demo_columns():
        label = ml_config.FEATURE_LABELS.get(name, name)
        try:
            value = float(form.get(name, ""))
        except ValueError:
            errors.append(f"{label} must be a number.")
            continue
        if not math.isfinite(value):
            errors.append(f"{label} must be a finite number.")
            continue
        low, high = BOUNDS.get(name, (None, None) if name == "change_1" else (0, None))
        if low is not None and value < low or high is not None and value > high:
            errors.append(f"{label} must be between {low} and {high}." if high is not None
                          else f"{label} cannot be negative.")
        values[name] = value
    return values, errors


def predict_values(user: User | None, values: dict[str, float]) -> dict:
    """Predict from entered values with the active model.

    Only signed-in users' demos are saved, as kind "demo", so anonymous visitors cannot fill the
    logs; demos are not app events, so they never change the operational monitoring figures.
    """
    started = time.perf_counter()
    run = training_service.active_run()
    if run is None:
        raise InferenceUnavailable(NO_MODEL)
    model = _model(run)
    columns = list(getattr(model, "feature_names_in_", ml_config.FEATURES))
    probabilities = model.predict_proba(pd.DataFrame([values])[columns])[0]
    by_level = {level: float(p) for level, p in zip(model.classes_, probabilities)}
    level = max(by_level, key=by_level.get)
    duration_ms = (time.perf_counter() - started) * 1000
    if user is not None:
        db.session.add(InferenceLog(user_id=user.id, model_run_id=run.id, kind="demo", level=level,
                                    probability=by_level[level], duration_ms=duration_ms))
        db.session.commit()
    return {"level": level, "probabilities": by_level, "run": run, "duration_ms": duration_ms,
            "logged": user is not None}
