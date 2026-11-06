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
    report = report_service.create(
        user,
        *point,
        fields.pop("waste_type", "household"),
        fields.pop("size", "medium"),
        fields.pop("has_rodents", False),
        False,
        False,
        False,
        None,
    )
    for name, value in fields.items():
        setattr(report, name, value)
    db.session.commit()
    return report


def activate_prediction(upz_code, level="high", probability=0.8):
    run = ModelRun(trigger="cli", n_rows=1, params={}, metrics={}, is_active=True)
    upz = Upz.query.filter_by(code=upz_code).one()
    db.session.add(
        RiskPrediction(
            model_run=run,
            upz=upz,
            period=datetime(2026, 11, 1).date(),
            level=level,
            probability=probability,
        )
    )
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
    kennedy = client.get(
        f"/api/heatmap?months=1&locality={kennedy_code}"
    ).get_json()["points"]

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
        assert "user_id" not in body
        assert "ana@mail.com" not in body
        assert "Ana" not in body


# Pages

def test_map_page_has_results_controls(client, db_session):
    html = client.get("/map").get_data(as_text=True)

    assert 'id="zoneSearch"' in html
    assert 'data-months="12"' in html
    assert "map_results.js" in html


# My reports

def test_my_reports_lists_only_own_reports(client, ana):
    other = auth_service.register("Luis", "luis@mail.com", "secret123")
    add_report(ana, KENNEDY, waste_type="bulky")
    add_report(other, CANDELARIA)
    login(client, "ana@mail.com")

    html = client.get("/reports/mine").get_data(as_text=True)

    assert "Bulky" in html
    assert "Candelaria" not in html
    assert report_service.list_for_user(ana)[0].user_id == ana.id


def test_map_and_my_reports_have_no_stray_markdown(client, ana):
    login(client, "ana@mail.com")

    for path in ("/map", "/reports/mine"):
        assert "```" not in client.get(path).get_data(as_text=True)


def test_my_reports_requires_login(client, db_session):
    response = client.get("/reports/mine")
    assert response.status_code == 302


# Admin

def test_admin_guard(client, ana):
    assert client.get("/admin").status_code == 302
    login(client, "ana@mail.com")
    assert client.get("/admin").status_code == 403


def test_admin_changes_report_status(client, ana, admin):
    report = add_report(ana)
    login(client, "admin@mail.com")

    assert "Report queue" in client.get("/admin").get_data(as_text=True)
    response = client.post(
        f"/admin/reports/{report.id}/status",
        data={"status": "rejected"},
    )

    assert response.status_code == 302
    assert db.session.get(Report, report.id).status == "rejected"
    assert client.get("/api/risk").get_json()["totals"]["reports"] == 0


def test_admin_rejects_unknown_status(client, ana, admin):
    report = add_report(ana)
    login(client, "admin@mail.com")

    client.post(
        f"/admin/reports/{report.id}/status",
        data={"status": "deleted"},
    )

    assert db.session.get(Report, report.id).status == "open"


def test_citizen_cannot_change_status(client, ana):
    report = add_report(ana)
    login(client, "ana@mail.com")

    response = client.post(
        f"/admin/reports/{report.id}/status",
        data={"status": "closed"},
    )

    assert response.status_code == 403
    assert db.session.get(Report, report.id).status == "open"


def test_admin_promotes_user_but_not_self(client, ana, admin):
    login(client, "admin@mail.com")

    client.post(f"/admin/users/{ana.id}/role", data={"role": "admin"})
    client.post(f"/admin/users/{admin.id}/role", data={"role": "citizen"})

    assert db.session.get(User, ana.id).role == "admin"
    assert db.session.get(User, admin.id).role == "admin"


def test_admin_queue_filters_by_status(client, ana, admin):
    add_report(ana, waste_type="bulky", status="closed")
    add_report(ana, waste_type="organic")
    login(client, "admin@mail.com")

    html = client.get("/admin?status=closed").get_data(as_text=True)

    assert "bulky" in html and "organic" not in html


# City stats

def test_home_shows_city_stats(client, ana):
    add_report(ana)
    report = Report.query.one()
    activate_prediction(report.upz.code)

    html = client.get("/").get_data(as_text=True)

    assert "Reports in the last 12 months" in html
    assert "UPZ at high risk in November" in html


def test_nav_shows_my_reports_and_admin_by_role(client, ana, admin):
    assert "My reports" not in client.get("/").get_data(as_text=True)

    login(client, "ana@mail.com")
    html = client.get("/").get_data(as_text=True)
    assert "My reports" in html and 'href="/admin"' not in html

    client.post("/auth/logout")
    login(client, "admin@mail.com")
    assert 'href="/admin"' in client.get("/").get_data(as_text=True)