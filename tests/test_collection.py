from datetime import date

import pytest

from app.extensions import db
from app.models import CollectionTask, ModelRun, Report, RiskPrediction, Upz
from app.services import auth_service, collection_service

PERIOD = date(2026, 12, 1)


def login(client, email):
    client.post("/auth/login", data={"email": email, "password": "secret123"})


@pytest.fixture
def setup(app, db_session):
    assert app.test_cli_runner().invoke(args=["load-zones"]).exit_code == 0
    ana = auth_service.register("Ana", "ana@mail.com", "secret123")
    boss = auth_service.register("Boss", "boss@mail.com", "secret123")
    boss.role = "admin"
    run = ModelRun(trigger="cli", n_rows=1, is_active=True, metrics={
        "chosen_model": "random_forest", "model_names": {"random_forest": "Random forest"},
        "test": {"macro_f1": 0.5}})
    db.session.add(run)
    db.session.commit()
    return ana, boss, run


def predictions(run, *levels, period=PERIOD):
    zones = Upz.query.order_by(Upz.id).limit(len(levels)).all()
    rows = [RiskPrediction(model_run=run, upz_id=z.id, period=period, level=level, probability=0.8)
            for z, level in zip(zones, levels)]
    db.session.add_all(rows)
    return rows


def make_task(run, status="pending", upz=None):
    upz = upz or Upz.query.order_by(Upz.id).first()
    task = CollectionTask(upz=upz, model_run=run, period=PERIOD, level="high", probability=0.8, status=status)
    db.session.add(task)
    db.session.commit()
    return task


def test_tasks_only_for_high_risk_zones(setup):
    run = setup[2]

    tasks = collection_service.create_tasks(run, predictions(run, "high", "medium", "low", "high"))
    db.session.commit()

    assert len(tasks) == 2
    assert {t.level for t in CollectionTask.query} == {"high"}


def test_no_duplicate_while_a_task_is_open(setup):
    run = setup[2]
    collection_service.create_tasks(run, predictions(run, "high", "high"))
    db.session.commit()
    first = CollectionTask.query.order_by(CollectionTask.id).first()
    first.status = "scheduled"
    db.session.commit()

    assert collection_service.create_tasks(run, predictions(run, "high", "high")) == []
    db.session.commit()
    assert CollectionTask.query.count() == 2


@pytest.mark.parametrize("status", ["done", "dismissed"])
def test_a_handled_task_is_not_recreated_for_the_same_period(setup, status):
    run = setup[2]
    make_task(run, status=status)

    assert collection_service.create_tasks(run, predictions(run, "high")) == []
    assert len(collection_service.create_tasks(run, predictions(run, "high", period=date(2027, 1, 1)))) == 1


@pytest.mark.parametrize("method, path", [("get", "/admin/priorities"), ("post", "/admin/priorities/1")])
def test_priorities_are_admin_only(client, setup, method, path):
    make_task(setup[2])

    assert getattr(client, method)(path).status_code == 302
    login(client, "ana@mail.com")
    assert getattr(client, method)(path, data={"action": "done"}).status_code == 403
    assert CollectionTask.query.one().status == "pending"


def test_admin_lists_and_filters_tasks(client, setup):
    run = setup[2]
    zones = Upz.query.order_by(Upz.id).limit(2).all()
    make_task(run, upz=zones[0])
    make_task(run, status="dismissed", upz=zones[1])
    login(client, "boss@mail.com")

    html = client.get("/admin/priorities").get_data(as_text=True)
    assert zones[0].name in html and zones[1].name in html and "December 2026" in html

    html = client.get("/admin/priorities?status=pending").get_data(as_text=True)
    assert zones[0].name in html and zones[1].name not in html


def test_schedule_needs_a_date(client, setup):
    task = make_task(setup[2])
    login(client, "boss@mail.com")

    response = client.post(f"/admin/priorities/{task.id}", data={"action": "schedule", "filter": "pending"})
    assert response.headers["Location"] == "/admin/priorities?status=pending&page=1"
    assert db.session.get(CollectionTask, task.id).status == "pending"

    client.post(f"/admin/priorities/{task.id}", data={"action": "schedule", "scheduled_for": "2026-12-03"})
    task = db.session.get(CollectionTask, task.id)
    assert task.status == "scheduled" and task.scheduled_for == date(2026, 12, 3)
    assert task.updated_by.email == "boss@mail.com"


def test_dismiss_needs_a_note(client, setup):
    task = make_task(setup[2])
    login(client, "boss@mail.com")

    html = client.post(f"/admin/priorities/{task.id}", data={"action": "dismiss"},
                       follow_redirects=True).get_data(as_text=True)
    assert "Add a note" in html and db.session.get(CollectionTask, task.id).status == "pending"

    client.post(f"/admin/priorities/{task.id}", data={"action": "dismiss", "note": "Cleaned by the locality"})
    task = db.session.get(CollectionTask, task.id)
    assert task.status == "dismissed" and task.notes == "Cleaned by the locality"


def test_done_can_close_the_zones_open_citizen_reports(client, setup):
    ana, _, run = setup
    upz, other = Upz.query.order_by(Upz.id).limit(2).all()
    task = make_task(run, upz=upz)

    def report(zone, status="open", source="user"):
        r = Report(user=ana if source == "user" else None, latitude=4.6, longitude=-74.1, upz=zone,
                   waste_type="household", size="small", status=status, source=source)
        db.session.add(r)
        return r

    reports = [report(upz), report(upz, "in_progress"), report(upz, "rejected"), report(upz, source="synthetic"),
               report(other)]
    db.session.commit()
    ids = [r.id for r in reports]
    login(client, "boss@mail.com")

    assert "Close its 2 open reports" in client.get("/admin/priorities").get_data(as_text=True)
    html = client.post(f"/admin/priorities/{task.id}", data={"action": "done", "close_reports": "1"},
                       follow_redirects=True).get_data(as_text=True)

    assert "2 open reports closed" in html
    db.session.expire_all()
    assert [db.session.get(Report, i).status for i in ids] == ["closed", "closed", "rejected", "open", "open"]
    assert db.session.get(CollectionTask, task.id).status == "done"


def test_done_without_the_checkbox_leaves_reports_open(client, setup):
    ana, _, run = setup
    upz = Upz.query.order_by(Upz.id).first()
    task = make_task(run, upz=upz)
    db.session.add(Report(user=ana, latitude=4.6, longitude=-74.1, upz=upz, waste_type="household", size="small"))
    db.session.commit()
    login(client, "boss@mail.com")

    client.post(f"/admin/priorities/{task.id}", data={"action": "done"})

    assert Report.query.one().status == "open"


def test_closed_tasks_cannot_change(client, setup):
    task = make_task(setup[2], status="done")
    login(client, "boss@mail.com")

    html = client.post(f"/admin/priorities/{task.id}", data={"action": "dismiss", "note": "x"},
                       follow_redirects=True).get_data(as_text=True)

    assert "already closed" in html
    assert db.session.get(CollectionTask, task.id).status == "done"


def test_pending_count_on_admin_and_app_home(client, setup):
    make_task(setup[2])
    login(client, "ana@mail.com")
    assert "Pending collection priorities" not in client.get("/app").get_data(as_text=True)

    client.post("/auth/logout")
    login(client, "boss@mail.com")
    for path in ("/app", "/admin"):
        html = client.get(path).get_data(as_text=True)
        assert "Pending collection priorities" in html and 'href="/admin/priorities?status=pending"' in html


def test_notes_are_capped(client, setup):
    task = make_task(setup[2])
    login(client, "boss@mail.com")

    html = client.post(f"/admin/priorities/{task.id}", data={"action": "dismiss", "note": "x" * 2001},
                       follow_redirects=True).get_data(as_text=True)

    assert "under 2,000 characters" in html
    assert db.session.get(CollectionTask, task.id).status == "pending"
