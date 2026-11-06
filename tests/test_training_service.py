
import io
from datetime import datetime, timedelta, timezone

import joblib
import pandas as pd
import pytest

from app import ml_commands
from app.extensions import db
from app.models import ModelRun, Report, RiskPrediction, Upz
from app.services import auth_service, report_service, risk_service, training_service
from ml import config


@pytest.fixture
def seeded(app, db_session, monkeypatch):
    # Fewer trees keep the suite fast; the stored params show the value actually used.
    monkeypatch.setattr(config, "N_ESTIMATORS", 20)
    app.config["TRAIN_IN_BACKGROUND"] = False
    runner = app.test_cli_runner()
    assert runner.invoke(args=["load-zones"]).exit_code == 0
    result = runner.invoke(args=["seed-synthetic"])
    assert result.exit_code == 0, result.output
    return runner


def test_seed_synthetic_loads_reports_once(seeded):
    total = Report.query.filter_by(source="synthetic").count()

    assert 15_000 < total < 21_000
    assert Report.query.filter(Report.user_id.isnot(None)).count() == 0
    assert "already loaded" in seeded.invoke(args=["seed-synthetic"]).output
    assert Report.query.count() == total


def test_seed_synthetic_requires_zones(app, db_session):
    result = app.test_cli_runner().invoke(args=["seed-synthetic"])

    assert result.exit_code != 0
    assert "load-zones" in result.output


def test_train_command_stores_an_active_run_with_all_models(seeded):
    result = seeded.invoke(args=["train"])
    assert result.exit_code == 0, result.output

    run = ModelRun.query.one()
    assert run.is_active and run.trigger == "cli"
    assert set(run.metrics["cv"]) == {"baseline", "logistic_regression", "random_forest"}
    assert run.metrics["cv"]["baseline"]["macro_f1"]["std"] >= 0
    assert run.params["N_ESTIMATORS"] == 20
    assert run.params["AUTO_RETRAIN_THRESHOLD"] == config.AUTO_RETRAIN_THRESHOLD
    assert RiskPrediction.query.filter_by(model_run_id=run.id).count() == Upz.query.count()
    model = joblib.load(io.BytesIO(run.artifact))
    assert hasattr(model, "predict_proba")


def test_new_run_replaces_the_active_one(seeded):
    first = training_service.run("cli")
    second = training_service.run("manual")

    assert not db.session.get(ModelRun, first.id).is_active
    assert training_service.active_run().id == second.id


def test_new_run_drops_the_artifacts_of_previous_runs(seeded):
    first = training_service.run("cli")
    second = training_service.run("manual")

    old = db.session.get(ModelRun, first.id)
    assert old.artifact is None
    assert old.metrics["chosen_model"] and old.params["N_SPLITS"] == config.N_SPLITS
    assert db.session.get(ModelRun, second.id).artifact is not None


def test_latest_active_run_wins_when_two_are_active(app, db_session):
    app.test_cli_runner().invoke(args=["load-zones"])
    upz = Upz.query.first()
    now = datetime.now(timezone.utc)
    runs = [ModelRun(trigger="cli", n_rows=1, is_active=True, trained_at=now - timedelta(days=d))
            for d in (1, 0)]
    db.session.add_all(runs)
    for run, level in zip(runs, ("low", "high")):
        db.session.add(RiskPrediction(model_run=run, upz=upz, period=now.date(), level=level, probability=0.9))
    db.session.commit()

    assert training_service.active_run().id == runs[1].id
    run, predictions = risk_service.active_predictions()
    assert run.id == runs[1].id
    assert predictions[upz.code]["level"] == "high"


def test_train_command_without_history_fails_cleanly(app, db_session):
    app.test_cli_runner().invoke(args=["load-zones"])
    result = app.test_cli_runner().invoke(args=["train"])

    assert result.exit_code != 0
    assert "months" in result.output
    assert ModelRun.query.count() == 0


def test_auto_retrain_after_threshold(seeded, monkeypatch):
    monkeypatch.setattr(config, "AUTO_RETRAIN_THRESHOLD", 3)
    user = auth_service.register("Ana", "ana@mail.com", "secret123")
    training_service.run("cli")

    for _ in range(2):
        report_service.create(user, 4.6280, -74.1630, "household", "small", False, False, False, False, None)
    assert ModelRun.query.count() == 1

    report_service.create(user, 4.6280, -74.1630, "household", "small", False, False, False, False, None)
    runs = ModelRun.query.order_by(ModelRun.id).all()
    assert [r.trigger for r in runs] == ["cli", "auto"]
    assert runs[-1].is_active


def test_failed_retrain_waits_for_another_threshold(seeded, monkeypatch):
    monkeypatch.setattr(config, "AUTO_RETRAIN_THRESHOLD", 2)
    monkeypatch.setattr(training_service, "_last_attempt", None)
    attempts = []

    def failing_run(trigger):
        attempts.append(trigger)
        raise RuntimeError("boom")

    user = auth_service.register("Ana", "ana@mail.com", "secret123")
    training_service.run("cli")
    monkeypatch.setattr(training_service, "run", failing_run)

    def report():
        report_service.create(user, 4.6280, -74.1630, "household", "small", False, False, False, False, None)

    for _ in range(2):
        report()
    assert attempts == ["auto"]

    report()
    assert attempts == ["auto"]
    report()
    assert attempts == ["auto", "auto"]


def test_seed_synthetic_rejects_invalid_values(app, db_session, monkeypatch, tmp_path):
    app.test_cli_runner().invoke(args=["load-zones"])
    rows = pd.read_csv(ml_commands.SYNTHETIC_CSV, dtype={"upz_code": str}, keep_default_na=False).head(3)
    rows.loc[1, "size"] = "huge"
    bad_csv = tmp_path / "synthetic_reports.csv"
    rows.to_csv(bad_csv, index=False)
    monkeypatch.setattr(ml_commands, "SYNTHETIC_CSV", bad_csv)

    result = app.test_cli_runner().invoke(args=["seed-synthetic"])

    assert result.exit_code != 0
    assert "Invalid size 'huge'" in result.output
    assert Report.query.count() == 0


def test_rejected_reports_do_not_count_toward_retrain(seeded):
    user = auth_service.register("Ana", "ana@mail.com", "secret123")
    training_service.run("cli")
    report = report_service.create(user, 4.6280, -74.1630, "household", "small",
                                   False, False, False, False, None)
    assert training_service.reports_since_last_run() == 1

    report.status = "rejected"
    db.session.commit()
    assert training_service.reports_since_last_run() == 0
