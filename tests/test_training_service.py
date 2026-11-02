
import io

import joblib
import pytest

from app.extensions import db
from app.models import ModelRun, Report, RiskPrediction, Upz
from app.services import auth_service, report_service, training_service
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


def test_rejected_reports_do_not_count_toward_retrain(seeded):
    user = auth_service.register("Ana", "ana@mail.com", "secret123")
    training_service.run("cli")
    report = report_service.create(user, 4.6280, -74.1630, "household", "small",
                                   False, False, False, False, None)
    assert training_service.reports_since_last_run() == 1

    report.status = "rejected"
    db.session.commit()
    assert training_service.reports_since_last_run() == 0
