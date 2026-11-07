import pytest

from app.extensions import db
from app.services import auth_service

PAGES = ["/app", "/map", "/model", "/reports/new", "/reports/mine", "/admin", "/admin/reports"]
APIS = ["/api/risk", "/api/heatmap", "/api/geo/locate?lat=4.6&lon=-74.1", "/api/neighborhoods?q=tintal"]


def login(client, email):
    client.post("/auth/login", data={"email": email, "password": "secret123"})


@pytest.mark.parametrize("path", PAGES)
def test_app_pages_send_guests_to_login(client, db_session, path):
    response = client.get(path)

    assert response.status_code == 302
    assert response.headers["Location"].startswith("/auth/login?next=")


@pytest.mark.parametrize("path", APIS)
def test_app_api_answers_guests_with_401(client, db_session, path):
    assert client.get(path).status_code == 401


@pytest.mark.parametrize("path", ["/", "/auth/login", "/auth/register", "/api/geo/upz", "/api/geo/localities"])
def test_public_routes_stay_open(client, db_session, path):
    assert client.get(path).status_code == 200


def test_login_then_next_returns_to_protected_page(client, db_session):
    auth_service.register("Ana", "ana@mail.com", "secret123")
    next_url = client.get("/map").headers["Location"]

    response = client.post(next_url, data={"email": "ana@mail.com", "password": "secret123"})

    assert response.headers["Location"] == "/map"
    assert client.get("/map").status_code == 200


@pytest.mark.parametrize("path", ["/auth/login", "/auth/register"])
def test_auth_pages_have_no_app_menu(client, db_session, path):
    html = client.get(path).get_data(as_text=True)

    assert "Back to project" in html and 'href="/"' in html
    for link in ('href="/app"', 'href="/map"', 'href="/model"', 'href="/reports/new"'):
        assert link not in html


def test_app_menu_by_role(client, db_session):
    auth_service.register("Ana", "ana@mail.com", "secret123")
    boss = auth_service.register("Boss", "boss@mail.com", "secret123")
    boss.role = "admin"
    db.session.commit()

    login(client, "ana@mail.com")
    html = client.get("/app").get_data(as_text=True)
    for link in ('href="/app"', 'href="/map"', 'href="/model"', 'href="/reports/mine"'):
        assert link in html
    assert "All reports" not in html and 'href="/admin"' not in html
    assert client.get("/model").status_code == 200

    client.post("/auth/logout")
    login(client, "boss@mail.com")
    html = client.get("/app").get_data(as_text=True)
    assert 'href="/admin/reports"' in html and 'href="/admin"' in html


def test_logout_returns_to_presentation(client, db_session):
    auth_service.register("Ana", "ana@mail.com", "secret123")
    login(client, "ana@mail.com")

    assert client.post("/auth/logout").headers["Location"] == "/"
    assert client.get("/app").status_code == 302
