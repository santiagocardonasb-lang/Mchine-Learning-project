from datetime import datetime, timedelta, timezone

import pytest

from app.extensions import db
from app.models import ModelRun, Report, RiskPrediction, Upz, User
from app.services import auth_service, report_service

KENNEDY = (4.6280, -74.1630)
CANDELARIA = (4.6097, -74.0817)


@pytest.fixture
def zones(app, db_session):
    assert app.test_cli_runner().invoke(args=["load-zones"]).exit_code == 0


@pytest.fixture
def ana(zones):
    return auth_service.register("Ana", "ana@mail.com", "secret123")


@pytest.fixture
def admin(zones):
    user = auth_service.register("Admin", "admin@mail.com", "secret123")
    user.role = "admin"
    db.session.commit()
    return user


def login(client, email):
    client.post("/auth/login", data={"email": email, "password": "secret123"})


def add_report(user, point=KENNEDY, **fields):
    report = report_service.create(user, *point, fields.pop("waste_type", "household"),
                                   fields.pop("size", "medium"), fields.pop("has_rodents", False),
                                   False, False, False, None)
    for name, value in fields.items():
        setattr(report, name, value)
    db.session.commit()
    return report


def activate_prediction(upz_code, level="high", probability=0.8):
    run = ModelRun(trigger="cli", n_rows=1, params={}, metrics={}, is_active=True)
    upz = Upz.query.filter_by(code=upz_code).one()
    db.session.add(RiskPrediction(model_run=run, upz=upz, period=datetime(2026, 11, 1).date(),
                                  level=level, probability=probability))
    db.session.commit()
    # API

def test_risk_without_model_has_stats_but_no_levels(client, ana):
    add_report(ana, has_rodents=True)
    add_report(ana, waste_type="bulky")

    data = client.get("/api/risk?months=3").get_json()

    assert data["period"] is None and data["run_id"] is None
    assert len(data["zones"]) == 112
    zone = next(z for z in data["zones"] if z["reports"])
    assert zone["level"] is None
    assert zone["reports"] == 2 and zone["open"] == 2
    assert zone["vectors_share"] == 0.5
    assert zone["top_type"] in ("household", "bulky")
    assert data["totals"] == {"reports": 2, "high": 0}


def test_risk_with_active_run(client, ana):
    report = add_report(ana)
    activate_prediction(report.upz.code)

    data = client.get("/api/risk").get_json()

    assert data["period"] == "2026-11-01"
    assert data["totals"]["high"] == 1
    zone = next(z for z in data["zones"] if z["code"] == report.upz.code)
    assert zone["level"] == "high" and zone["probability"] == 0.8


def test_rejected_and_old_reports_are_left_out(client, ana):
    add_report(ana, status="rejected")
    add_report(ana, reported_at=datetime.now(timezone.utc) - timedelta(days=200))
    add_report(ana)

    assert client.get("/api/risk?months=3").get_json()["totals"]["reports"] == 1
    assert client.get("/api/risk?months=12").get_json()["totals"]["reports"] == 2
    assert len(client.get("/api/heatmap?months=3").get_json()["points"]) == 1


def test_heatmap_filters_by_locality_and_weights_size(client, ana):
    add_report(ana, KENNEDY, size="large")
    add_report(ana, CANDELARIA, size="small")
    kennedy_code = Report.query.first().locality.code

    everything = client.get("/api/heatmap?months=1").get_json()["points"]
    kennedy = client.get(f"/api/heatmap?months=1&locality={kennedy_code}").get_json()["points"]

    assert len(everything) == 2
    assert kennedy == [[4.628, -74.163, 1.0]]


@pytest.mark.parametrize("months", ["2", "abc", "-1"])
def test_bad_period_is_rejected(client, db_session, months):
    assert client.get(f"/api/risk?months={months}").status_code == 400
    assert client.get(f"/api/heatmap?months={months}").status_code == 400


def test_public_api_hides_reporters(client, ana):
    add_report(ana)

    for url in ("/api/risk?months=3", "/api/heatmap?months=3"):
        body = client.get(url).get_data(as_text=True)
        assert "user_id" not in body and "ana@mail.com" not in body and "Ana" not in body