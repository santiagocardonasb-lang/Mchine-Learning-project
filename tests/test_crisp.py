import io
from datetime import datetime, timedelta, timezone

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import RandomForestClassifier

from app.extensions import db
from app.models import InferenceLog, ModelRun, Report, Upz
from app.services import evidence_service
from ml import config

SLUGS = [p["slug"] for p in evidence_service.PHASES]


@pytest.fixture
def zones(app, db_session):
    assert app.test_cli_runner().invoke(args=["load-zones"]).exit_code == 0


def active_run():
    rng = np.random.RandomState(0)
    features = pd.DataFrame(rng.rand(30, len(config.FEATURES)), columns=config.FEATURES)
    model = RandomForestClassifier(n_estimators=3, random_state=0).fit(features, ["low", "medium", "high"] * 10)
    buffer = io.BytesIO()
    joblib.dump(model, buffer)
    run = ModelRun(trigger="cli", n_rows=30, is_active=True, artifact=buffer.getvalue(),
                   metrics={"chosen_model": "random_forest", "model_names": {"random_forest": "Random forest"}})
    db.session.add(run)
    db.session.commit()
    return run


def add_reports(code="80", n=3):
    upz = Upz.query.filter_by(code=code).one()
    last_month = datetime.now(timezone.utc).replace(day=1) - timedelta(days=10)
    for _ in range(n):
        db.session.add(Report(latitude=4.6, longitude=-74.1, upz=upz, locality_id=upz.locality_id,
                              waste_type="household", size="large", reported_at=last_month))
    db.session.commit()


def demo_form(**overrides):
    values = {name: "1" for name in config.FEATURES}
    values.update(month_of_year="10", share_large="0.5")
    values.update(overrides)
    return values


@pytest.mark.parametrize("slug", SLUGS)
def test_every_phase_is_public_and_lists_all_phases(client, zones, slug):
    html = client.get(f"/crisp-ml/{slug}").get_data(as_text=True)

    assert "Phase" in html
    for phase in evidence_service.PHASES:
        assert phase["name"] in html


def test_overview_reads_the_evidence(client, db_session):
    ev = evidence_service.evidence()
    html = client.get("/crisp-ml").get_data(as_text=True)

    assert "{:,}".format(ev["quality"]["panel"]["labelled_rows"]) in html
    assert "%.3f" % ev["final_run"]["metrics"]["test"]["macro_f1"] in html


def test_evidence_matches_the_configured_model():
    ev = evidence_service.evidence()

    assert ev["quality"]["panel"]["features"] == config.FEATURES
    chosen = [e for e in ev["experiments"] if e["current"] and e["model"] == "random_forest"]
    assert chosen and chosen[0]["params"]["n_estimators"] == config.N_ESTIMATORS
    assert all(s["label"] == "SIMULATED" for s in ev["simulated_monitoring"])


def test_unknown_phase_is_404(client, db_session):
    assert client.get("/crisp-ml/nowhere").status_code == 404


def test_demo_without_a_model_says_so(client, zones):
    html = client.get("/crisp-ml/deployment").get_data(as_text=True)

    assert "No trained model is available yet" in html


def test_demo_prefills_a_real_zone_and_predicts_entered_values(client, zones):
    add_reports()
    run = active_run()

    page = client.get("/crisp-ml/deployment?upz=80").get_data(as_text=True)
    assert 'name="reports"' in page and 'value="3.0"' in page

    html = client.post("/crisp-ml/deployment?upz=80", data=demo_form()).get_data(as_text=True)

    assert "risk</b>" in html and "model demo" in html
    log = InferenceLog.query.one()
    assert (log.kind, log.model_run_id, log.user_id, log.status) == ("demo", run.id, None, "ok")


def test_demo_rejects_out_of_range_values(client, zones):
    active_run()

    html = client.post("/crisp-ml/deployment", data=demo_form(share_large="1.5", reports="-2")).get_data(as_text=True)

    assert "Share of large piles must be between 0 and 1." in html
    assert "Reports this month cannot be negative." in html
    assert InferenceLog.query.count() == 0
