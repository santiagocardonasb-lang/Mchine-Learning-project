from datetime import date, datetime, timedelta, timezone

import pytest

from app.extensions import db
from app.models import ModelRun, Report, RiskPrediction, Upz
from app.services import auth_service, report_service, risk_service

KENNEDY = (4.6280, -74.1630)


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "now, period, bounds",
    [
        (utc(2026, 11, 7, 15), "this_month", (utc(2026, 11, 1), utc(2026, 12, 1))),
        (utc(2026, 11, 7, 15), "last_month", (utc(2026, 10, 1), utc(2026, 11, 1))),
        (utc(2026, 11, 7, 15), "3m", (utc(2026, 9, 1), utc(2026, 12, 1))),
        (utc(2026, 11, 7, 15), "12m", (utc(2025, 12, 1), utc(2026, 12, 1))),
        (utc(2027, 1, 1), "last_month", (utc(2026, 12, 1), utc(2027, 1, 1))),
        (utc(2027, 1, 31, 23, 59), "3m", (utc(2026, 11, 1), utc(2027, 2, 1))),
        (utc(2026, 12, 31, 23, 59), "this_month", (utc(2026, 12, 1), utc(2027, 1, 1))),
        (utc(2026, 3, 30), "last_month", (utc(2026, 2, 1), utc(2026, 3, 1))),
    ],
)
def test_period_bounds_follow_utc_calendar_months(now, period, bounds):
    assert risk_service.period_bounds(period, now) == bounds


def test_periods_are_the_four_map_chips():
    assert risk_service.PERIODS == ("this_month", "last_month", "3m", "12m")


@pytest.fixture
def ana(app, db_session):
    assert app.test_cli_runner().invoke(args=["load-zones"]).exit_code == 0
    return auth_service.register("Ana", "ana@mail.com", "secret123")


@pytest.fixture
def signed_in(client, ana):
    client.post("/auth/login", data={"email": "ana@mail.com", "password": "secret123"})
    return client


def add_report(user, reported_at):
    report = report_service.create(user, *KENNEDY, "household", "small", False, False, False, False, None)
    report.reported_at = reported_at
    db.session.commit()
    return report


def test_this_month_is_the_default_and_excludes_last_month(signed_in, ana):
    this_month, _ = risk_service.period_bounds("this_month")
    add_report(ana, this_month + timedelta(minutes=1))
    add_report(ana, this_month - timedelta(seconds=1))

    def total(query=""):
        return signed_in.get(f"/api/risk{query}").get_json()["totals"]["reports"]

    assert total() == 1
    assert total("?period=this_month") == 1
    assert total("?period=last_month") == 1
    assert total("?period=3m") == 2
    assert signed_in.get("/api/risk").get_json()["report_period"] == "this_month"
    assert len(signed_in.get("/api/heatmap").get_json()["points"]) == 1


def test_zone_without_reports_in_period_has_no_figures_but_keeps_its_risk(signed_in, ana):
    report = add_report(ana, risk_service.period_bounds("last_month")[0] + timedelta(days=2))
    run = ModelRun(trigger="cli", n_rows=1, is_active=True)
    db.session.add(RiskPrediction(model_run=run, upz_id=report.upz_id, period=date(2026, 12, 1),
                                  level="high", probability=0.8))
    db.session.commit()
    code = db.session.get(Upz, report.upz_id).code

    zones = {z["code"]: z for z in signed_in.get("/api/risk?period=this_month").get_json()["zones"]}
    last = {z["code"]: z for z in signed_in.get("/api/risk?period=last_month").get_json()["zones"]}

    assert zones[code]["reports"] == 0
    assert zones[code]["open"] is None
    assert zones[code]["vectors_share"] is None and zones[code]["top_type"] is None
    assert zones[code]["level"] == "high"
    assert last[code]["reports"] == 1 and last[code]["open"] == 1
    assert signed_in.get("/api/heatmap?period=this_month").get_json()["points"] == []


def test_rejected_reports_stay_out_of_every_period(signed_in, ana):
    report = add_report(ana, datetime.now(timezone.utc))
    report.status = "rejected"
    db.session.commit()

    for period in risk_service.PERIODS:
        assert signed_in.get(f"/api/risk?period={period}").get_json()["totals"]["reports"] == 0
    assert Report.query.count() == 1


def test_map_offers_this_month_first_and_selected(signed_in):
    html = signed_in.get("/map").get_data(as_text=True)

    chips = html[html.index('id="period"'):html.index("</div>", html.index('id="period"'))]
    assert chips.index('data-period="this_month"') < chips.index('data-period="last_month"')
    assert '<button type="button" data-period="this_month" class="on">This month</button>' in chips
    assert "No reports in this period" in html


def test_map_side_panel_has_one_reports_figure_for_the_period(signed_in):
    html = signed_in.get("/map").get_data(as_text=True)

    assert "Reports this month" not in html
    assert html.count('id="statReports"') == 1
    assert '<span class="label" id="reportsLabel">Reports · this month</span>' in html


def test_results_css_has_no_stray_markdown(client):
    css = client.get("/static/css/results.css").get_data(as_text=True)

    assert "```" not in css
    assert css.lstrip().startswith("/*")
    assert ".high-ink { color: var(--high-ink); }" in css
