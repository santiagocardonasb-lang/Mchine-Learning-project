
import pytest

from app.extensions import db
from app.models import ModelRun
from app.services import auth_service, training_service
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


def login(client, email, password="secret123"):
    client.post("/auth/login", data={"email": email, "password": password})


def make_admin():
    user = auth_service.register("Admin", "admin@mail.com", "secret123")
    user.role = "admin"
    db.session.commit()
    return user


def test_model_page_without_run(client, db_session):
    html = client.get("/model").get_data(as_text=True)

    assert "Metrics appear after the first model run" in html
    assert "Retrain" not in html


def test_model_page_shows_params_metrics_and_baseline(seeded, client):
    training_service.run("cli")
    html = client.get("/model").get_data(as_text=True)

    assert "Baseline (most frequent)" in html
    assert "N_ESTIMATORS" in html and "<b>20</b>" in html
    assert " ± " in html
    assert "Reading the errors" in html
    assert "Retrain" not in html


def test_retrain_requires_admin(seeded, client):
    auth_service.register("Ana", "ana@mail.com", "secret123")

    assert client.post("/model/retrain").status_code == 302  # guest → login
    login(client, "ana@mail.com")
    assert client.post("/model/retrain").status_code == 403
    assert ModelRun.query.count() == 0


def test_admin_retrain_starts_a_manual_run(seeded, client):
    make_admin()
    login(client, "admin@mail.com")

    assert "Retrain" in client.get("/model").get_data(as_text=True)
    response = client.post("/model/retrain", data={"next": "/admin"})

    assert response.status_code == 302
    assert response.headers["Location"] == "/admin"
    assert ModelRun.query.one().trigger == "manual"


def test_retrain_ignores_external_next(seeded, client):
    make_admin()
    login(client, "admin@mail.com")

    response = client.post("/model/retrain", data={"next": "https://evil.example"})

    assert response.headers["Location"] == "/model"


def test_crisp_dm_page(client, db_session):
    html = client.get("/crisp-dm").get_data(as_text=True)

    assert "Business understanding" in html and "Deployment" in html
    assert "Synthetic history" in html


def test_nav_links_to_model(client, db_session):
    assert 'href="/model"' in client.get("/").get_data(as_text=True)
