import re
from datetime import date, datetime, timedelta, timezone

import pytest

from app.extensions import db
from app.models import Locality, ModelRun, Report, RiskPrediction, Upz
from app.services import auth_service, stats_service


def month_start() -> datetime:
    return datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def add_report(reported_at, status="open"):
    db.session.add(
        Report(
            latitude=4.6, longitude=-74.1, waste_type="household", size="small",
            status=status, reported_at=reported_at,
        )
    )


def add_run(is_active, predictions):
    """predictions: list of (upz_name, level, probability)."""
    locality = Locality.query.first() or Locality(code="8", name="Kennedy")
    run = ModelRun(trigger="cli", n_rows=10, is_active=is_active)
    db.session.add_all([locality, run])
    for name, level, probability in predictions:
        upz = Upz.query.filter_by(name=name).first() or Upz(
            code=name, name=name, locality=locality
        )
        db.session.add(
            RiskPrediction(
                model_run=run, upz=upz, period=date(2026, 11, 1),
                level=level, probability=probability,
            )
        )
    db.session.commit()


def reports_this_month_on_page(html: str) -> int:
    match = re.search(r"Reports this month</span>\s*<b>(\d+)</b>", html)
    assert match, "Reports this month card not found"
    return int(match.group(1))


@pytest.mark.parametrize("path", ["/", "/about", "/how-it-works"])
def test_pages_return_200(client, db_session, path):
    assert client.get(path).status_code == 200


def test_home_has_headline_and_ctas(client, db_session):
    html = client.get("/").get_data(as_text=True)
    assert "Know where waste" in html
    assert 'href="/reports/new"' in html
    assert 'href="/map"' in html


def test_about_has_project_content(client, db_session):
    html = client.get("/about").get_data(as_text=True)
    assert "General objective" in html
    assert "Research question" in html
    assert "LimpIA" not in html


def test_how_it_works_mentions_data_sources(client, db_session):
    html = client.get("/how-it-works").get_data(as_text=True)
    assert "UAESP" in html
    assert "SDP" in html


def test_nav_shows_sign_in_for_guests(client, db_session):
    html = client.get("/").get_data(as_text=True)
    assert "Sign in" in html
    assert "Sign out" not in html
    assert "Report waste" in html


def test_nav_shows_sign_out_for_logged_in_user(client, db_session):
    auth_service.register("Ana", "ana@mail.com", "secret123")
    client.post("/auth/login", data={"email": "ana@mail.com", "password": "secret123"})
    html = client.get("/").get_data(as_text=True)
    assert "Sign out" in html
    assert "Ana" in html
    assert 'action="/auth/logout"' in html
    assert "Sign in" not in html


def test_home_counts_non_rejected_reports_of_current_month(client, db_session):
    start = month_start()
    add_report(start + timedelta(hours=1))
    add_report(start + timedelta(minutes=5), status="closed")
    add_report(start + timedelta(hours=2), status="rejected")
    add_report(start - timedelta(seconds=1))
    db.session.commit()

    assert stats_service.reports_this_month() == 2
    assert reports_this_month_on_page(client.get("/").get_data(as_text=True)) == 2


def test_home_without_predictions_shows_placeholder(client, db_session):
    html = client.get("/").get_data(as_text=True)
    assert "Predictions appear after the first model run" in html
    assert "Highest risk next month" not in html


def test_top_priority_zones_uses_active_run_high_level_only(db_session):
    add_run(False, [("Old Zone", "high", 0.99)])
    add_run(True, [("Bosa Central", "high", 0.91), ("Patio Bonito", "high", 0.95),
                   ("Chapinero", "medium", 0.97)])

    zones = stats_service.top_priority_zones()

    assert zones == [
        {"upz": "Patio Bonito", "locality": "Kennedy", "probability": 0.95},
        {"upz": "Bosa Central", "locality": "Kennedy", "probability": 0.91},
    ]


def test_top_priority_zones_respects_limit(db_session):
    add_run(True, [(f"Zone {i}", "high", i / 10) for i in range(1, 8)])
    zones = stats_service.top_priority_zones()
    assert [z["upz"] for z in zones] == ["Zone 7", "Zone 6", "Zone 5", "Zone 4", "Zone 3"]


def test_home_shows_priority_zones_and_highest_risk(client, db_session):
    add_run(True, [("Bosa Central", "high", 0.91)])
    html = client.get("/").get_data(as_text=True)
    assert "Predictions appear after the first model run" not in html
    assert "Highest risk next month" in html
    assert "Bosa Central" in html
    assert "91%" in html
