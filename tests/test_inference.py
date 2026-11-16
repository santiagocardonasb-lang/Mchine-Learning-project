import io
from datetime import datetime, timedelta, timezone

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import RandomForestClassifier
from sqlalchemy import event

from app.extensions import db
from app.models import AppEvent, InferenceLog, ModelRun, Report, RiskPrediction, Upz
from app.services import auth_service, inference_service, training_service
from ml import config
from ml.features import build_panel, latest_month, zone_row

KENNEDY_UPZ = "80"  # Corabastos, where the test reports are placed


def login(client, email):
    client.post("/auth/login", data={"email": email, "password": "secret123"})


@pytest.fixture
def zones(app, db_session):
    assert app.test_cli_runner().invoke(args=["load-zones"]).exit_code == 0


@pytest.fixture
def users(zones):
    ana = auth_service.register("Ana", "ana@mail.com", "secret123")
    luis = auth_service.register("Luis", "luis@mail.com", "secret123")
    boss = auth_service.register("Boss", "boss@mail.com", "secret123")
    boss.role = "admin"
    db.session.commit()
    return ana, luis, boss


def add_reports(upz_code=KENNEDY_UPZ, n=3):
    upz = Upz.query.filter_by(code=upz_code).one()
    last_month = (datetime.now(timezone.utc).replace(day=1) - timedelta(days=10))
    for _ in range(n):
        db.session.add(Report(latitude=4.6, longitude=-74.1, upz=upz, locality_id=upz.locality_id,
                              waste_type="household", size="large", reported_at=last_month))
    db.session.commit()


def fake_run():
    """An active run whose artifact is a tiny forest over the real feature list."""
    rng = np.random.RandomState(0)
    features = pd.DataFrame(rng.rand(30, len(config.FEATURES)), columns=config.FEATURES)
    model = RandomForestClassifier(n_estimators=3, random_state=0).fit(features, ["low", "medium", "high"] * 10)
    buffer = io.BytesIO()
    joblib.dump(model, buffer)
    run = ModelRun(trigger="cli", n_rows=30, is_active=True, artifact=buffer.getvalue(), metrics={
        "chosen_model": "random_forest", "model_names": {"random_forest": "Random forest"},
        "cuts": [1.0, 2.0], "test": {"macro_f1": 0.5, "recall_high": 0.6},
    })
    db.session.add(run)
    db.session.commit()
    return run


def test_zone_row_is_the_training_row_of_that_zone():
    zones = pd.DataFrame({"upz_code": ["1", "2"], "locality_code": ["1", "1"], "area_km2": [1.0, 3.0],
                          "critical_points": [4, 0], "public_space_m2_per_inhabitant": [2.0, 1.0],
                          "population": [10_000, 30_000], "population_density": [10_000, 10_000]})
    reports = pd.DataFrame([
        {"upz_code": code, "reported_at": pd.Timestamp(when, tz="UTC"), "updated_at": pd.Timestamp(when, tz="UTC"),
         "size": "small", "has_rodents": False, "has_insects": False, "has_odor": False,
         "near_water": False, "status": "open"}
        for code, when in [("1", "2026-01-10"), ("1", "2026-02-10"), ("2", "2026-03-03"), ("1", "2026-03-04")]
    ])
    now = pd.Timestamp("2026-04-15", tz="UTC")

    row = zone_row(reports, zones, "1", now=now)
    expected = latest_month(build_panel(reports, zones, now=now))

    assert len(row) == 1 and row["month"].iloc[0] == pd.Timestamp("2026-03-01")
    pd.testing.assert_series_equal(row[config.FEATURES].iloc[0],
                                   expected[expected["upz_code"] == "1"][config.FEATURES].iloc[0])
    assert row["lag_1"].iloc[0] == 1 and row["reports"].iloc[0] == 1


def test_predict_zone_logs_user_version_and_duration(users):
    ana = users[0]
    add_reports()
    run = fake_run()
    upz = Upz.query.filter_by(code=KENNEDY_UPZ).one()

    result = inference_service.predict_zone(ana, upz)

    assert result.level in config.RISK_LEVELS
    assert result.probability == max(result.probabilities.values())
    assert sum(result.probabilities.values()) == pytest.approx(1)
    assert result.features["reports"] == 3
    log = InferenceLog.query.one()
    assert (log.user_id, log.model_run_id, log.upz_id, log.kind, log.status) == (ana.id, run.id, upz.id, "zone", "ok")
    assert log.level == result.level and log.probability == pytest.approx(result.probability)
    assert log.duration_ms > 0
    event = AppEvent.query.filter_by(kind="inference").one()
    assert event.user_id == ana.id and event.duration_ms == pytest.approx(log.duration_ms)


def test_predict_zone_without_a_model_logs_an_error(users):
    upz = Upz.query.filter_by(code=KENNEDY_UPZ).one()

    with pytest.raises(inference_service.InferenceUnavailable, match="No trained model"):
        inference_service.predict_zone(users[0], upz)

    log = InferenceLog.query.one()
    assert log.status == "error" and log.model_run_id is None and log.level is None
    assert "No trained model" in log.error


def test_predict_zone_with_a_pruned_artifact_fails_gracefully(users):
    run = fake_run()
    run.artifact = None
    db.session.commit()

    with pytest.raises(inference_service.InferenceUnavailable):
        inference_service.predict_zone(users[0], Upz.query.filter_by(code=KENNEDY_UPZ).one())
    assert InferenceLog.query.one().model_run_id == run.id


def test_predict_zone_without_complete_months_fails_gracefully(users):
    fake_run()

    with pytest.raises(inference_service.InferenceUnavailable, match="not enough reports"):
        inference_service.predict_zone(users[0], Upz.query.filter_by(code=KENNEDY_UPZ).one())
    assert InferenceLog.query.one().status == "error"


def test_zone_inference_matches_the_training_batch(app, users, monkeypatch):
    monkeypatch.setattr(config, "N_ESTIMATORS", 20)
    assert app.test_cli_runner().invoke(args=["seed-synthetic"]).exit_code == 0
    run = training_service.run("cli")
    upz = Upz.query.filter_by(code=KENNEDY_UPZ).one()

    result = inference_service.predict_zone(users[0], upz)

    batch = RiskPrediction.query.filter_by(model_run_id=run.id, upz_id=upz.id).one()
    assert result.period == batch.period
    assert result.level == batch.level
    assert result.probability == pytest.approx(batch.probability)


@pytest.mark.parametrize("path", ["/risk-check", "/inferences"])
def test_pages_require_login(client, db_session, path):
    assert client.get(path).status_code == 302
    assert client.post("/risk-check", data={"upz": KENNEDY_UPZ}).status_code == 302


def test_risk_check_page_runs_and_explains(client, users):
    add_reports()
    fake_run()
    login(client, "ana@mail.com")

    page = client.get(f"/risk-check?upz={KENNEDY_UPZ}").get_data(as_text=True)
    assert f'value="{KENNEDY_UPZ}" selected' in page
    assert InferenceLog.query.count() == 0

    html = client.post("/risk-check", data={"upz": KENNEDY_UPZ}).get_data(as_text=True)

    assert "What it means" in html and "How to use it" in html and "Limitations" in html
    assert "Corabastos" in html and "Run 1" in html
    assert InferenceLog.query.count() == 1


def test_risk_check_rejects_an_unknown_zone(client, users):
    fake_run()
    login(client, "ana@mail.com")

    html = client.post("/risk-check", data={"upz": "nope"}, follow_redirects=True).get_data(as_text=True)

    assert "Choose a UPZ to check." in html
    assert InferenceLog.query.count() == 0


def test_risk_check_without_model_shows_a_message(client, users):
    login(client, "ana@mail.com")

    html = client.post("/risk-check", data={"upz": KENNEDY_UPZ}).get_data(as_text=True)

    assert "No trained model is available yet" in html
    assert "available after the first model run" in html


def test_history_is_own_for_users_and_all_for_admins(client, users):
    ana, luis, _ = users
    upz = Upz.query.filter_by(code=KENNEDY_UPZ).one()
    db.session.add_all([
        InferenceLog(user=ana, upz=upz, kind="zone", level="high", probability=0.7, duration_ms=10),
        InferenceLog(user=luis, upz=upz, kind="zone", level="low", probability=0.6, duration_ms=10),
        InferenceLog(kind="batch", duration_ms=900),
    ])
    db.session.commit()

    login(client, "ana@mail.com")
    html = client.get("/inferences").get_data(as_text=True)
    assert "High · 70%" in html and "Low · 60%" not in html and "All zones" not in html

    client.post("/auth/logout")
    login(client, "boss@mail.com")
    html = client.get("/inferences").get_data(as_text=True)
    assert "High · 70%" in html and "Low · 60%" in html and "All zones" in html
    assert "Luis" in html and "Automatic" in html


def test_errors_are_detailed_for_admins_only(client, users):
    db.session.add(InferenceLog(user=users[0], kind="zone", duration_ms=1, status="error", error="KeyError('rate')"))
    db.session.commit()

    login(client, "ana@mail.com")
    html = client.get("/inferences").get_data(as_text=True)
    assert "The check could not be completed." in html and "KeyError" not in html

    client.post("/auth/logout")
    login(client, "boss@mail.com")
    assert "KeyError" in client.get("/inferences").get_data(as_text=True)


def test_history_paginates(client, users, monkeypatch):
    monkeypatch.setattr(inference_service, "PAGE_SIZE", 2)
    db.session.add_all([InferenceLog(user=users[0], kind="zone", duration_ms=1, status="error", error="x")
                        for _ in range(3)])
    db.session.commit()
    login(client, "ana@mail.com")

    assert "Page 1 of 2" in client.get("/inferences").get_data(as_text=True)
    assert "Page 2 of 2" in client.get("/inferences?page=2").get_data(as_text=True)


def test_entry_points_link_to_the_risk_check(client, users):
    ana = users[0]
    upz = Upz.query.filter_by(code=KENNEDY_UPZ).one()
    db.session.add(Report(user=ana, latitude=4.6, longitude=-74.1, upz=upz, waste_type="household", size="small"))
    db.session.commit()
    login(client, "ana@mail.com")

    assert f'href="/risk-check?upz={KENNEDY_UPZ}"' in client.get("/reports/mine").get_data(as_text=True)
    assert 'id="detailCheck"' in client.get("/map").get_data(as_text=True)


def test_cached_model_skips_the_artifact_blob(users):
    add_reports()
    fake_run()
    upz = Upz.query.filter_by(code=KENNEDY_UPZ).one()
    inference_service.predict_zone(users[0], upz)
    db.session.expire_all()
    statements = []

    def record(conn, cursor, statement, *rest):
        statements.append(statement)

    event.listen(db.engine, "before_cursor_execute", record)
    try:
        inference_service.predict_zone(users[0], upz)
    finally:
        event.remove(db.engine, "before_cursor_execute", record)

    selects = [s for s in statements if s.lstrip().upper().startswith("SELECT")]
    assert selects and not any("artifact" in s for s in selects)
