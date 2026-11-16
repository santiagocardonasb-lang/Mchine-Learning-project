import pytest

from app.extensions import db
from app.models import Feedback
from app.services import auth_service, feedback_service


def login(client, email):
    client.post("/auth/login", data={"email": email, "password": "secret123"})


@pytest.fixture
def users(db_session):
    ana = auth_service.register("Ana", "ana@mail.com", "secret123")
    luis = auth_service.register("Luis", "luis@mail.com", "secret123")
    boss = auth_service.register("Boss", "boss@mail.com", "secret123")
    boss.role = "admin"
    db.session.commit()
    return ana, luis, boss


def test_help_requires_login(client, db_session):
    assert client.get("/help").status_code == 302
    assert client.post("/help", data={"kind": "bug", "message": "x"}).status_code == 302


@pytest.mark.parametrize("method, path", [("get", "/admin/feedback"), ("post", "/admin/feedback/1")])
def test_feedback_management_is_admin_only(client, users, method, path):
    assert getattr(client, method)(path).status_code == 302
    login(client, "ana@mail.com")
    assert getattr(client, method)(path, data={"status": "resolved"}).status_code == 403


def test_user_sends_a_ticket_with_the_page(client, users):
    login(client, "ana@mail.com")

    form = client.get("/help?page=/map").get_data(as_text=True)
    assert 'name="page" type="hidden" value="/map"' in form

    response = client.post("/help", data={"kind": "incident", "message": " The map is blank ", "page": "/map"})

    assert response.status_code == 302 and response.headers["Location"] == "/help#tickets"
    ticket = Feedback.query.one()
    assert (ticket.user_id, ticket.kind, ticket.message, ticket.page, ticket.status) == (
        users[0].id, "incident", "The map is blank", "/map", "open")


@pytest.mark.parametrize("page", ["https://evil.example", "//evil.example", "map", "/" + "x" * 300])
def test_only_app_paths_are_stored(users, page):
    assert feedback_service.create(users[0], "bug", "x", page).page is None


def test_invalid_ticket_shows_errors(client, users):
    login(client, "ana@mail.com")

    html = client.post("/help", data={"kind": "question", "message": ""}).get_data(as_text=True)

    assert "Write what happened" in html
    assert Feedback.query.count() == 0


def test_my_tickets_lists_only_own(client, users):
    ana, luis, _ = users
    feedback_service.create(ana, "bug", "Ana's bug", "/app")
    feedback_service.create(luis, "suggestion", "Luis's idea", None)
    login(client, "ana@mail.com")

    html = client.get("/help").get_data(as_text=True)

    assert "Ana&#39;s bug" in html and "Luis&#39;s idea" not in html


def test_admin_answers_and_the_user_sees_it(client, users):
    ana, luis, _ = users
    ticket = feedback_service.create(ana, "bug", "Ana's bug", "/app")
    feedback_service.create(luis, "suggestion", "Luis's idea", None)
    login(client, "boss@mail.com")

    html = client.get("/admin/feedback").get_data(as_text=True)
    assert "Ana&#39;s bug" in html and "Luis&#39;s idea" in html and "Luis" in html

    response = client.post(f"/admin/feedback/{ticket.id}",
                           data={"status": "resolved", "response": "Fixed, thanks", "filter": "open", "page": "1"})
    assert response.headers["Location"] == "/admin/feedback?status=open&page=1"
    assert "Luis&#39;s idea" not in client.get("/admin/feedback?status=resolved").get_data(as_text=True)

    client.post("/auth/logout")
    login(client, "ana@mail.com")
    html = client.get("/help").get_data(as_text=True)
    assert "Fixed, thanks" in html and "resolved" in html


def test_unknown_status_is_rejected(client, users):
    ticket = feedback_service.create(users[0], "bug", "x", None)
    login(client, "boss@mail.com")

    html = client.post(f"/admin/feedback/{ticket.id}", data={"status": "closed"},
                       follow_redirects=True).get_data(as_text=True)

    assert "Unknown status." in html
    assert db.session.get(Feedback, ticket.id).status == "open"


def test_blank_message_is_rejected(client, users):
    login(client, "ana@mail.com")

    html = client.post("/help", data={"kind": "bug", "message": "   \n  "}).get_data(as_text=True)

    assert "Write what happened" in html
    assert Feedback.query.count() == 0
