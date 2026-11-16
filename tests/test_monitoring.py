from collections import Counter
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from app.extensions import db
from app.models import AppEvent, ModelRun, Report, RiskPrediction, Upz
from app.services import auth_service, monitoring_service, training_service
from ml import config


def login(client, email):
    client.post("/auth/login", data={"email": email, "password": "secret123"})


def month_start(offset=0) -> datetime:
    now = datetime.now(timezone.utc)
    year, month = divmod(now.year * 12 + now.month - 1 + offset, 12)
    return datetime(year, month + 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def zones(app, db_session):
    assert app.test_cli_runner().invoke(args=["load-zones"]).exit_code == 0


@pytest.fixture
def users(zones):
    ana = auth_service.register("Ana", "ana@mail.com", "secret123")
    boss = auth_service.register("Boss", "boss@mail.com", "secret123")
    boss.role = "admin"
    db.session.commit()
    return ana, boss


def add_reports(upz, offset, n, waste_type="household"):
    db.session.add_all([
        Report(latitude=4.6, longitude=-74.1, upz=upz, waste_type=waste_type, size="small", source="synthetic",
               reported_at=month_start(offset) + timedelta(days=4), updated_at=month_start(offset) + timedelta(days=4))
        for _ in range(n)
    ])


def add_run(cuts=(0.5, 1.0), cv_f1=0.6, trained_at=None, first_month=-4):
    run = ModelRun(trigger="cli", n_rows=1, is_active=True, trained_at=trained_at or datetime.now(timezone.utc),
                   metrics={"chosen_model": "random_forest", "model_names": {"random_forest": "Random forest"},
                            "cuts": list(cuts), "cv": {"random_forest": {"macro_f1": {"mean": cv_f1}}},
                            "months": {"first": month_start(first_month).strftime("%Y-%m")}})
    db.session.add(run)
    return run


def predict(run, levels: dict, period):
    for upz, level in levels.items():
        db.session.add(RiskPrediction(model_run=run, upz=upz, period=period, level=level, probability=0.7))


# Events

def test_requests_are_recorded_with_duration_and_user(client, users):
    login(client, "ana@mail.com")
    client.get("/app")
    client.get("/static/css/app.css")
    client.get("/no-such-page")

    event = AppEvent.query.filter_by(kind="request", path="/app").one()
    assert event.method == "GET" and event.status_code == 200
    assert event.duration_ms > 0 and event.user_id == users[0].id
    assert AppEvent.query.filter(AppEvent.path.like("/static%")).count() == 0
    assert AppEvent.query.filter_by(path="/no-such-page").count() == 0


def test_guest_requests_are_not_recorded(client, users):
    client.get("/auth/login")
    client.get("/")

    assert AppEvent.query.count() == 0


def test_a_failing_event_write_never_breaks_the_request(client, users, monkeypatch):
    def broken(kind, **fields):
        raise RuntimeError("database down")

    monkeypatch.setattr(monitoring_service, "record_event", broken)
    login(client, "ana@mail.com")

    assert client.get("/app").status_code == 200


def test_request_event_does_not_commit_unfinished_changes(app, client, users):
    app.add_url_rule("/half-done", "half_done", lambda: (db.session.add(
        Report(latitude=4.6, longitude=-74.1, waste_type="household", size="small")) or "ok"))

    login(client, "ana@mail.com")
    client.get("/half-done")
    db.session.rollback()

    assert AppEvent.query.filter_by(path="/half-done").count() == 1
    assert Report.query.count() == 0


def test_unhandled_error_is_recorded_and_shows_a_friendly_page(app, client, users):
    app.config["PROPAGATE_EXCEPTIONS"] = False
    app.add_url_rule("/boom", "boom", lambda: 1 / 0)
    login(client, "ana@mail.com")

    response = client.get("/boom")

    assert response.status_code == 500
    assert "Something went wrong" in response.get_data(as_text=True)
    error = AppEvent.query.filter_by(kind="error").one()
    assert error.path == "/boom" and "ZeroDivisionError" in error.message and error.user_id == users[0].id
    assert AppEvent.query.filter_by(kind="request", path="/boom").one().status_code == 500


def test_monitoring_is_admin_only(client, users):
    assert client.get("/admin/monitoring").status_code == 302
    login(client, "ana@mail.com")
    assert client.get("/admin/monitoring").status_code == 403


def test_monitoring_page_without_data(client, users):
    login(client, "boss@mail.com")

    html = client.get("/admin/monitoring").get_data(as_text=True)

    assert "Not trained yet" in html and "No predicted month is complete yet" in html
    assert "Retraining recommended" not in html


def test_indicators_count_the_last_days(users):
    old = datetime.now(timezone.utc) - timedelta(days=config.MONITORING_DAYS + 1)
    db.session.add_all([
        AppEvent(kind="request", duration_ms=10), AppEvent(kind="request", duration_ms=30),
        AppEvent(kind="request", duration_ms=500, created_at=old),
        AppEvent(kind="inference", duration_ms=200), AppEvent(kind="error", message="boom"),
    ])
    add_run(trained_at=datetime.now(timezone.utc) - timedelta(days=3))
    db.session.commit()

    ind = monitoring_service.indicators(datetime.now(timezone.utc))

    assert ind["requests"] == (2, pytest.approx(20))
    assert ind["inferences"] == (1, pytest.approx(200))
    assert ind["errors"] == 1 and ind["latest_errors"][0].message == "boom"
    assert ind["model"]["age_days"] == 3 and ind["model"]["name"] == "Random forest"


# Predictions vs actual outcomes

def test_compare_scores_and_confusion_matrix():
    predicted = {"a": "high", "b": "low", "c": "high", "d": "medium"}
    actual = {"a": "high", "b": "low", "c": "low", "d": "medium", "e": "high"}

    result = monitoring_service.compare(predicted, actual)

    assert result["zones"] == 4
    assert result["accuracy"] == pytest.approx(0.75)
    # F1: low 2/3, medium 1, high 2/3
    assert result["macro_f1"] == pytest.approx((2 / 3 + 1 + 2 / 3) / 3)
    assert result["confusion_matrix"] == [[1, 0, 1], [0, 1, 0], [0, 0, 1]]


def test_actual_levels_use_the_runs_cut_points():
    panel = pd.DataFrame({"upz_code": ["a", "b", "c", "a"], "rate": [0.2, 0.8, 3.0, 9.0],
                          "month": pd.to_datetime(["2026-09-01"] * 3 + ["2026-08-01"])})

    assert monitoring_service.actual_levels(panel, date(2026, 9, 1), [0.5, 1.0]) == {
        "a": "low", "b": "medium", "c": "high"}


def test_prediction_outcomes_for_complete_months(users):
    a, b, c = Upz.query.order_by(Upz.id).limit(3).all()
    add_reports(a, -2, 1)
    add_reports(a, -1, 40)  # far above any cut; b and c have no reports, so their rate is 0
    old = add_run(trained_at=datetime.now(timezone.utc) - timedelta(days=40))
    new = add_run()
    predict(old, {a: "low", b: "low", c: "low"}, month_start(-1).date())
    predict(new, {a: "high", b: "low", c: "high"}, month_start(-1).date())
    predict(new, {a: "high"}, month_start(0).date())  # the current month is not complete
    db.session.commit()
    panel = monitoring_service.build_panel(training_service.reports_frame(), training_service.zones_frame())

    outcomes = monitoring_service.prediction_outcomes(panel, datetime.now(timezone.utc))

    assert len(outcomes) == 1
    outcome = outcomes[0]
    assert outcome["run_id"] == new.id and outcome["zones"] == 3
    assert outcome["accuracy"] == pytest.approx(2 / 3)
    assert outcome["confusion_matrix"] == [[1, 0, 1], [0, 0, 0], [0, 0, 1]]


# Drift and performance

def test_psi_is_zero_for_the_same_distribution_and_flags_a_shift():
    rng = np.random.RandomState(0)
    base = rng.gamma(2.0, 1.0, 2000)

    assert monitoring_service.psi(base, base) == pytest.approx(0, abs=1e-9)
    assert monitoring_service.psi(base, rng.gamma(2.0, 1.0, 2000)) < 0.1
    assert monitoring_service.psi(base, base * 2.5) > config.DRIFT_PSI_THRESHOLD


def test_share_shifts():
    rows = monitoring_service.share_shifts(Counter(household=75, bulky=25), Counter(household=40, bulky=60))

    assert [(r["category"], round(r["change"], 2)) for r in rows] == [("bulky", 0.35), ("household", -0.35)]


@pytest.mark.parametrize("live, flagged", [(0.30, True), (0.55, False)])
def test_performance_flag_against_the_cv_score(live, flagged):
    outcomes = [{"period": date(2026, 10, 1), "run_id": 1, "cv_macro_f1": 0.6, "macro_f1": live},
                {"period": date(2026, 9, 1), "run_id": 1, "cv_macro_f1": 0.6, "macro_f1": 0.1}]

    check = monitoring_service.performance(outcomes)

    assert check["live"] == live and check["floor"] == pytest.approx(0.6 * config.PERFORMANCE_DROP_FRACTION)
    assert check["flag"] is flagged


def test_drift_flags_a_new_waste_mix_and_recommends_retraining(client, users):
    zones = Upz.query.order_by(Upz.id).limit(5).all()
    for offset in (-4, -3, -2):
        for upz in zones:
            add_reports(upz, offset, 3)
    for upz in zones:
        add_reports(upz, -1, 3, waste_type="construction_debris")
    run = add_run()
    predict(run, {upz: "low" for upz in zones}, month_start(0).date())
    db.session.commit()
    login(client, "boss@mail.com")

    data = monitoring_service.overview()
    html = client.get("/admin/monitoring").get_data(as_text=True)

    drift = data["drift"]
    assert drift["month"] == month_start(-1).date()
    assert drift["share_flag"] and drift["max_shift"] > config.DRIFT_SHARE_THRESHOLD
    debris = next(r for r in drift["shares"]["waste_type"] if r["category"] == "construction_debris")
    # The reference stops before the recent month, which is the only one with debris.
    assert debris["recent"] == 1.0 and debris["train"] == 0
    assert drift["train_to"] == month_start(-1).date() - timedelta(days=1)
    assert "Retraining recommended" in html and "construction debris" in html


def test_drift_waits_for_an_active_model(users):
    add_reports(Upz.query.first(), -1, 3)
    db.session.commit()

    assert monitoring_service.overview()["drift"] is None


def test_prune_keeps_only_the_retention_window(users):
    now = datetime.now(timezone.utc)
    db.session.add_all([
        AppEvent(kind="request", created_at=now - timedelta(days=config.APP_EVENT_RETENTION_DAYS + 1)),
        AppEvent(kind="error", created_at=now - timedelta(days=config.APP_EVENT_RETENTION_DAYS - 1)),
    ])
    db.session.commit()

    assert monitoring_service.prune_events(now) == 1
    assert [e.kind for e in AppEvent.query.all()] == ["error"]


def test_pruning_runs_after_training_and_from_the_cli(app, users):
    assert monitoring_service.prune_after_training in training_service.on_trained
    old = datetime.now(timezone.utc) - timedelta(days=config.APP_EVENT_RETENTION_DAYS + 1)
    db.session.add_all([AppEvent(kind="request", created_at=old), AppEvent(kind="request", created_at=old)])
    db.session.commit()

    monitoring_service.prune_after_training(None)
    assert AppEvent.query.count() == 0

    db.session.add(AppEvent(kind="error", created_at=old))
    db.session.commit()
    result = app.test_cli_runner().invoke(args=["prune-events"])
    assert result.exit_code == 0 and "Deleted 1 monitoring events." in result.output


def test_runs_with_minimal_metrics_do_not_break_the_page(client, users):
    upz = Upz.query.order_by(Upz.id).first()
    add_reports(upz, -1, 3)
    run = ModelRun(trigger="cli", n_rows=1, is_active=True, metrics={})
    db.session.add(run)
    predict(run, {upz: "high"}, month_start(-1).date())
    db.session.commit()
    login(client, "boss@mail.com")

    response = client.get("/admin/monitoring")

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "did not store the cut points" in html and "Unknown model" in html
    assert monitoring_service.performance(monitoring_service.overview()["outcomes"]) is None
