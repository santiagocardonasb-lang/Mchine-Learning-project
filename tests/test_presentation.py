import re
from datetime import date

import pytest

from app import content
from app.extensions import db
from app.models import Locality, ModelRun, RiskPrediction, Upz
from app.services import auth_service

APP_LINKS = ('href="/app"', 'href="/map"', 'href="/model"', 'href="/reports', 'href="/admin')


def add_active_run():
    locality = Locality(code="8", name="Kennedy")
    run = ModelRun(
        trigger="cli", n_rows=2400, is_active=True,
        metrics={
            "chosen_model": "random_forest",
            "model_names": {"baseline": "Baseline (most frequent)", "random_forest": "Random forest"},
            "test": {"macro_f1": 0.71},
            "baseline_test": {"macro_f1": 0.17},
        },
    )
    db.session.add_all([
        RiskPrediction(model_run=run, upz=Upz(code="80", name="Patio Bonito", locality=locality),
                       period=date(2026, 12, 1), level="high", probability=0.9),
        RiskPrediction(model_run=run, upz=Upz(code="81", name="Gran Britalia", locality=locality),
                       period=date(2026, 12, 1), level="low", probability=0.6),
    ])
    db.session.commit()


def test_presentation_has_no_app_links_for_guests(client, db_session):
    response = client.get("/")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'href="/auth/login"' in html and "Sign in" in html
    assert not [link for link in APP_LINKS if link in html]
    assert "Report waste" not in html


def test_presentation_has_the_sections(client, db_session):
    html = client.get("/").get_data(as_text=True)

    for section in ("context", "solution", "definition", "objectives", "results", "phases"):
        assert f'id="{section}"' in html


def test_presentation_has_four_crisp_dm_phase_tabs(client, db_session):
    html = client.get("/").get_data(as_text=True)

    tabs = re.findall(r'<button type="button" role="tab"[^>]*aria-selected="(true|false)"', html)
    assert tabs == ["true", "false", "false", "false"]
    assert html.count('role="tabpanel"') == 4
    for phase in content.PHASES:
        assert phase["name"] in html
        assert f'aria-controls="phase-{phase["slug"]}"' in html
        assert f'id="phase-{phase["slug"]}"' in html
    # Panels are not hidden in the markup, so the page reads in full without JavaScript.
    assert not re.search(r'role="tabpanel"[^>]*hidden', html)
    assert "phase_tabs.js" in html


def test_presentation_results_without_run(client, db_session):
    assert "Results appear after the first model run." in client.get("/").get_data(as_text=True)


def test_presentation_results_read_the_active_run(client, db_session):
    add_active_run()

    html = client.get("/").get_data(as_text=True)

    assert "Results appear after the first model run." not in html
    assert "Random forest" in html
    assert "0.71" in html and "0.17" in html
    assert "High-risk UPZ in December 2026" in html
    assert "Patio Bonito" in html and "Gran Britalia" not in html


def test_presentation_offers_the_app_to_logged_in_users(client, db_session):
    auth_service.register("Ana", "ana@mail.com", "secret123")
    client.post("/auth/login", data={"email": "ana@mail.com", "password": "secret123"})

    html = client.get("/").get_data(as_text=True)

    assert "Go to the app" in html and 'href="/app"' in html
    assert "Sign in" not in html
    assert 'href="/map"' not in html


@pytest.mark.parametrize(
    "old, target",
    [("/about", "/#context"), ("/how-it-works", "/#solution"), ("/crisp-dm", "/#phases")],
)
def test_old_pages_redirect_to_presentation(client, db_session, old, target):
    response = client.get(old)

    assert response.status_code == 302
    assert response.headers["Location"] == target
