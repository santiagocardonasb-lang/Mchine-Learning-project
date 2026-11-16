import time
from collections import Counter
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
from flask import current_app, g, request
from flask_login import current_user
from sklearn.metrics import confusion_matrix
from sqlalchemy import delete, func, insert

from app.extensions import db
from app.models import AppEvent, ModelRun, Report, RiskPrediction, Upz
from app.models.user import utcnow
from app.services import risk_service, training_service
from ml import config as ml_config
from ml.features import NotEnoughData, build_panel, label
from ml.train import LEVELS, scores

PSI_FLOOR = 1e-4  # an empty bin would make the logarithm infinite
LATEST_ERRORS = 5


# Events

def record_event(kind: str, **fields) -> None:
    """Write an event on its own connection, so it never commits a request's unfinished changes."""
    with db.engine.begin() as connection:
        connection.execute(insert(AppEvent).values(kind=kind, **fields))


def prune_events(now: datetime) -> int:
    """Delete events older than the retention window. Returns how many were deleted."""
    cutoff = now - timedelta(days=ml_config.APP_EVENT_RETENTION_DAYS)
    with db.engine.begin() as connection:
        return connection.execute(delete(AppEvent).where(AppEvent.created_at < cutoff)).rowcount


def prune_after_training(run: ModelRun) -> None:
    """training_service.on_trained hook: retention runs with training, off the request path."""
    prune_events(utcnow())


def _request_fields(status_code: int) -> dict:
    return {
        "path": request.path[:255],
        "method": request.method,
        "status_code": status_code,
        "duration_ms": (time.perf_counter() - g.request_started) * 1000 if "request_started" in g else None,
        "user_id": current_user.id if current_user.is_authenticated else None,
    }


def record_request(response) -> None:
    """Signed-in app requests only: static files, unknown URLs and guests are not app usage."""
    # Monitoring must never turn a working response into an error.
    try:
        if request.endpoint == "static" or response.status_code == 404 or not current_user.is_authenticated:
            return
        record_event("request", **_request_fields(response.status_code))
    except Exception:
        current_app.logger.warning("Could not record the request event", exc_info=True)


def record_error(error: BaseException) -> None:
    try:
        record_event("error", message=repr(error)[:2000], **_request_fields(500))
    except Exception:
        current_app.logger.warning("Could not record the error event", exc_info=True)


# Indicators

def _utc(value: datetime) -> datetime:
    # SQLite returns timestamps without their offset; they are stored as UTC.
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _active_run():
    """The active run without its artifact, which can be megabytes."""
    return (
        db.session.query(ModelRun.id, ModelRun.trained_at, ModelRun.metrics)
        .filter(ModelRun.is_active.is_(True))
        .order_by(ModelRun.trained_at.desc())
        .first()
    )


def _model_name(metrics: dict) -> str:
    chosen = metrics.get("chosen_model")
    return metrics.get("model_names", {}).get(chosen) or chosen or "Unknown model"


def _cv_macro_f1(metrics: dict) -> float | None:
    return metrics.get("cv", {}).get(metrics.get("chosen_model"), {}).get("macro_f1", {}).get("mean")


def indicators(now: datetime) -> dict:
    since = now - timedelta(days=ml_config.MONITORING_DAYS)
    by_kind = {
        kind: (n, avg)
        for kind, n, avg in db.session.query(AppEvent.kind, func.count(AppEvent.id), func.avg(AppEvent.duration_ms))
        .filter(AppEvent.created_at >= since)
        .group_by(AppEvent.kind)
    }
    run = _active_run()
    return {
        "days": ml_config.MONITORING_DAYS,
        "requests": by_kind.get("request", (0, None)),
        "inferences": by_kind.get("inference", (0, None)),
        "errors": by_kind.get("error", (0, None))[0],
        "latest_errors": AppEvent.query.filter_by(kind="error")
        .order_by(AppEvent.created_at.desc(), AppEvent.id.desc()).limit(LATEST_ERRORS).all(),
        "model": None if run is None else {
            "id": run.id,
            "name": _model_name(run.metrics or {}),
            "trained_at": run.trained_at,
            "age_days": (now - _utc(run.trained_at)).days,
        },
    }


# Predictions vs actual outcomes

def actual_levels(panel: pd.DataFrame, period, cuts) -> dict[str, str]:
    """Each UPZ's observed level in `period`, labelled with the cut points of the run that predicted it."""
    rows = panel[panel["month"] == pd.Timestamp(period)]
    return dict(zip(rows["upz_code"], label(rows["rate"], tuple(cuts))))


def compare(predicted: dict[str, str], actual: dict[str, str]) -> dict:
    codes = sorted(predicted.keys() & actual.keys())
    y_true = [actual[c] for c in codes]
    y_pred = [predicted[c] for c in codes]
    return {
        **scores(y_true, y_pred),
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=LEVELS).tolist(),
        "zones": len(codes),
    }


def prediction_outcomes(panel: pd.DataFrame | None, now: datetime) -> list[dict]:
    """Accuracy of every predicted month that is now complete, newest first.

    When several runs predicted the same month, the latest of them speaks for it.
    """
    current_month = risk_service.period_bounds("this_month", now)[0].date()
    latest = {}
    for period, run_id, trained_at in (
        db.session.query(RiskPrediction.period, RiskPrediction.model_run_id, ModelRun.trained_at)
        .join(ModelRun, RiskPrediction.model_run_id == ModelRun.id)
        .filter(RiskPrediction.period < current_month)
        .distinct()
    ):
        if period not in latest or trained_at > latest[period][1]:
            latest[period] = (run_id, trained_at)
    if not latest:
        return []

    run_ids = {run_id for run_id, _ in latest.values()}
    metrics = dict(db.session.query(ModelRun.id, ModelRun.metrics).filter(ModelRun.id.in_(run_ids)))
    predicted = {}
    for run_id, period, code, level in (
        db.session.query(RiskPrediction.model_run_id, RiskPrediction.period, Upz.code, RiskPrediction.level)
        .join(Upz, RiskPrediction.upz_id == Upz.id)
        .filter(RiskPrediction.model_run_id.in_(run_ids), RiskPrediction.period.in_(latest))
    ):
        if latest[period][0] == run_id:
            predicted.setdefault(period, {})[code] = level

    months = set(panel["month"]) if panel is not None else set()
    outcomes = []
    for period in sorted(latest, reverse=True):
        run_id = latest[period][0]
        m = metrics[run_id] or {}
        outcome = {"period": period, "run_id": run_id, "cv_macro_f1": _cv_macro_f1(m)}
        if len(m.get("cuts") or []) != 2:
            outcome["note"] = "This run did not store the cut points needed to label the actual levels."
        elif pd.Timestamp(period) not in months:
            outcome["note"] = "There are no reports from this month yet to compare with."
        else:
            outcome.update(compare(predicted.get(period, {}), actual_levels(panel, period, m["cuts"])))
        outcomes.append(outcome)
    return outcomes


def performance(outcomes: list[dict]) -> dict | None:
    """Live macro F1 of the latest evaluated month against the CV macro F1 of the run behind it."""
    evaluated = [o for o in outcomes if "macro_f1" in o and o["cv_macro_f1"] is not None]
    if not evaluated:
        return None
    latest = evaluated[0]
    floor = latest["cv_macro_f1"] * ml_config.PERFORMANCE_DROP_FRACTION
    return {"period": latest["period"], "live": latest["macro_f1"], "reference": latest["cv_macro_f1"],
            "floor": floor, "flag": latest["macro_f1"] < floor}


# Drift

def psi(expected, actual) -> float:
    """Population stability index of `actual` against `expected`, with quantile bins of `expected`."""
    expected, actual = np.asarray(expected, dtype=float), np.asarray(actual, dtype=float)
    edges = np.unique(np.quantile(expected, np.linspace(0, 1, ml_config.PSI_BINS + 1)[1:-1]))

    def shares(values):
        counts = np.bincount(np.searchsorted(edges, values, side="right"), minlength=len(edges) + 1)
        return np.clip(counts / len(values), PSI_FLOOR, None)

    e, a = shares(expected), shares(actual)
    return float(np.sum((a - e) * np.log(a / e)))


def share_shifts(train: Counter, recent: Counter) -> list[dict]:
    train_total, recent_total = sum(train.values()) or 1, sum(recent.values()) or 1
    rows = []
    for category in sorted(train.keys() | recent.keys()):
        before, after = train[category] / train_total, recent[category] / recent_total
        rows.append({"category": category, "train": before, "recent": after, "change": after - before})
    return rows


def _category_counts(start: datetime, end: datetime) -> dict[str, Counter]:
    counts = {"waste_type": Counter(), "size": Counter(), "vectors": Counter()}
    for waste_type, size, rodents, insects, odor, n in (
        db.session.query(Report.waste_type, Report.size, Report.has_rodents, Report.has_insects,
                         Report.has_odor, func.count(Report.id))
        .filter(Report.status != "rejected", Report.reported_at >= start, Report.reported_at < end)
        .group_by(Report.waste_type, Report.size, Report.has_rodents, Report.has_insects, Report.has_odor)
    ):
        counts["waste_type"][waste_type] += n
        counts["size"][size] += n
        counts["vectors"]["with vectors" if rodents or insects or odor else "without vectors"] += n
    return counts


def _month(moment: datetime) -> pd.Timestamp:
    """An aware UTC month start as the panel's naive month timestamp."""
    return pd.Timestamp(moment.replace(tzinfo=None))


def drift(panel: pd.DataFrame | None, run, now: datetime) -> dict | None:
    """The last complete month against the months the active run was trained on."""
    if panel is None or run is None:
        return None
    recent_start, recent_end = risk_service.period_bounds("last_month", now)
    first = (run.metrics or {}).get("months", {}).get("first")
    train_start = (pd.Timestamp(first) if first else panel["month"].min()).to_pydatetime().replace(tzinfo=timezone.utc)
    # Training leaves out the month it ran in, which was still partial. The reference also stops
    # before the recent month, so a month is never compared with itself.
    train_end = min(_utc(run.trained_at).replace(day=1, hour=0, minute=0, second=0, microsecond=0), recent_start)

    train_rates = panel.loc[(panel["month"] >= _month(train_start)) & (panel["month"] < _month(train_end)), "rate"]
    recent_rates = panel.loc[panel["month"] == _month(recent_start), "rate"]
    if train_rates.empty or recent_rates.empty:
        return None

    before, after = _category_counts(train_start, train_end), _category_counts(recent_start, recent_end)
    shares = {group: share_shifts(before[group], after[group]) for group in before}
    max_shift = max((abs(row["change"]) for rows in shares.values() for row in rows), default=0.0)
    rate_psi = psi(train_rates, recent_rates)
    return {
        "month": recent_start.date(),
        "train_from": train_start.date(),
        "train_to": (train_end - timedelta(days=1)).date(),
        "psi": rate_psi,
        "psi_flag": rate_psi > ml_config.DRIFT_PSI_THRESHOLD,
        "shares": shares,
        "max_shift": max_shift,
        "share_flag": max_shift > ml_config.DRIFT_SHARE_THRESHOLD,
    }


def overview(now: datetime | None = None) -> dict:
    """Everything the Monitoring page shows."""
    now = now or datetime.now(timezone.utc)
    try:
        panel = build_panel(training_service.reports_frame(), training_service.zones_frame(), now=pd.Timestamp(now))
    except NotEnoughData:
        panel = None
    outcomes = prediction_outcomes(panel, now)
    drift_check = drift(panel, _active_run(), now)
    performance_check = performance(outcomes)
    reasons = []
    if drift_check and drift_check["psi_flag"]:
        reasons.append(f"The report rate of {drift_check['month']:%B %Y} drifted from the training data "
                       f"(PSI {drift_check['psi']:.2f}).")
    if drift_check and drift_check["share_flag"]:
        reasons.append(f"The mix of waste types, sizes or vectors shifted by up to {drift_check['max_shift']:.0%}.")
    if performance_check and performance_check["flag"]:
        reasons.append(f"Live macro F1 in {performance_check['period']:%B %Y} ({performance_check['live']:.2f}) "
                       f"fell below {ml_config.PERFORMANCE_DROP_FRACTION:.0%} of the cross-validation score.")
    return {
        "indicators": indicators(now),
        "outcomes": outcomes,
        "drift": drift_check,
        "performance": performance_check,
        "retrain_reasons": reasons,
        "thresholds": {
            "psi": ml_config.DRIFT_PSI_THRESHOLD,
            "share": ml_config.DRIFT_SHARE_THRESHOLD,
            "performance": ml_config.PERFORMANCE_DROP_FRACTION,
        },
    }
