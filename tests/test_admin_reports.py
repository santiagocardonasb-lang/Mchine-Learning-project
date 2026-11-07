import pytest
from sqlalchemy import event

from app.extensions import db
from app.models import Report
from app.services import admin_service, auth_service, report_service

KENNEDY = (4.6280, -74.1630)


@pytest.fixture
def zones(app, db_session):
    assert app.test_cli_runner().invoke(args=["load-zones"]).exit_code == 0


@pytest.fixture
def users(zones):
    ana = auth_service.register("Ana", "ana@mail.com", "secret123")
    luis = auth_service.register("Luis", "luis@mail.com", "secret123")
    boss = auth_service.register("Boss", "boss@mail.com", "secret123")
    boss.role = "admin"
    db.session.commit()
    return ana, luis, boss


def login(client, email):
    client.post("/auth/login", data={"email": email, "password": "secret123"})


def add_report(user, waste_type="household", status="open"):
    report = report_service.create(user, *KENNEDY, waste_type, "small", False, False, False, False, None)
    report.status = status
    db.session.commit()
    return report


def test_all_reports_is_admin_only(client, users):
    assert client.get("/admin/reports").status_code == 302
    login(client, "ana@mail.com")
    assert client.get("/admin/reports").status_code == 403


def test_all_reports_lists_every_users_reports(client, users):
    ana, luis, _ = users
    add_report(ana, "bulky")
    add_report(luis, "organic")
    login(client, "boss@mail.com")

    html = client.get("/admin/reports").get_data(as_text=True)

    assert "Ana" in html and "Luis" in html
    assert "bulky" in html and "organic" in html


def test_all_reports_filters_and_changes_status(client, users):
    ana, _, _ = users
    add_report(ana, "bulky", status="closed")
    report = add_report(ana, "organic")
    login(client, "boss@mail.com")

    html = client.get("/admin/reports?status=closed").get_data(as_text=True)
    assert "bulky" in html and "organic" not in html

    response = client.post(f"/admin/reports/{report.id}/status",
                           data={"status": "in_progress", "filter": "open", "page": "1"})

    assert response.headers["Location"] == "/admin/reports?status=open&page=1"
    assert db.session.get(Report, report.id).status == "in_progress"


def test_all_reports_paginates(client, users, monkeypatch):
    ana, _, _ = users
    monkeypatch.setattr(admin_service, "PAGE_SIZE", 2)
    for _ in range(3):
        add_report(ana)
    login(client, "boss@mail.com")

    assert "Page 1 of 2" in client.get("/admin/reports").get_data(as_text=True)
    assert "Page 2 of 2" in client.get("/admin/reports?page=2").get_data(as_text=True)


def test_report_queue_loads_relations_up_front(users):
    ana, luis, _ = users
    for user in (ana, luis, ana, luis):
        add_report(user)
    db.session.expire_all()

    queue = admin_service.report_queue(None, 1)
    statements = []

    def record(conn, cursor, statement, *rest):
        statements.append(statement)

    event.listen(db.engine, "before_cursor_execute", record)
    try:
        rows = [(r.user.name, r.upz.name, r.locality.name) for r in queue.items]
    finally:
        event.remove(db.engine, "before_cursor_execute", record)

    assert len(rows) == 4
    assert statements == []


def test_admin_page_keeps_users_and_retraining_only(client, users):
    add_report(users[0])
    login(client, "boss@mail.com")

    html = client.get("/admin").get_data(as_text=True)

    assert 'id="users"' in html and 'id="model"' in html
    assert "Report queue" not in html
    assert 'href="/admin/reports"' in html


def test_my_reports_stays_available_to_admins(client, users):
    login(client, "boss@mail.com")
    assert client.get("/reports/mine").status_code == 200
