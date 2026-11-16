from datetime import date

import pytest

from app.extensions import db
from app.models import AppEvent, CollectionTask, Feedback, InferenceLog, Locality, ModelRun, Upz, User


@pytest.fixture
def records(db_session):
    user = User(name="Ana", email="ana@mail.com")
    user.set_password("secret123")
    locality = Locality(code="8", name="Kennedy")
    upz = Upz(code="80", name="Corabastos", locality=locality)
    run = ModelRun(trigger="cli", n_rows=1)
    db.session.add_all([user, upz, run])
    db.session.commit()
    return user, upz, run


def test_new_rows_get_their_defaults(records):
    user, upz, run = records
    log = InferenceLog(user=user, model_run_id=run.id, upz=upz, kind="zone", level="high",
                       probability=0.7, duration_ms=12.5)
    task = CollectionTask(upz=upz, model_run_id=run.id, period=date(2026, 12, 1), level="high",
                          probability=0.7)
    event = AppEvent(kind="request", path="/app", method="GET", status_code=200, duration_ms=3.0)
    ticket = Feedback(user=user, kind="bug", message="The map is blank")
    db.session.add_all([log, task, event, ticket])
    db.session.commit()

    assert log.status == "ok" and log.created_at is not None
    assert task.status == "pending" and task.is_open and task.updated_at is not None
    assert event.created_at is not None
    assert ticket.status == "open" and ticket.response is None


@pytest.mark.parametrize("model, field, value", [
    (InferenceLog, "kind", "weekly"),
    (InferenceLog, "status", "failed"),
    (InferenceLog, "level", "extreme"),
    (CollectionTask, "status", "cancelled"),
    (CollectionTask, "level", "urgent"),
    (AppEvent, "kind", "click"),
    (Feedback, "kind", "question"),
    (Feedback, "status", "closed"),
])
def test_enums_reject_unknown_values(model, field, value):
    with pytest.raises(ValueError):
        model(**{field: value})


def test_batch_inference_has_no_level():
    assert InferenceLog(kind="batch", level=None, duration_ms=1.0).level is None
