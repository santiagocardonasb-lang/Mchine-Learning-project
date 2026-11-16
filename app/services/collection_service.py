from datetime import date

from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models import CollectionTask, ModelRun, Report, RiskPrediction, Upz, User
from app.models.operations import TASK_STATUSES
from app.models.user import utcnow

PAGE_SIZE = 25
NOTE_MAX = 2000
OPEN_REPORT_STATUSES = ("open", "in_progress")


class TaskError(Exception):
    """A collection-priority action that is not allowed; the message is shown to the admin."""


def create_tasks(run: ModelRun, predictions: list[RiskPrediction]) -> list[CollectionTask]:
    """A pending task for every high-risk UPZ that has no task yet for that period. Not committed.

    Done and dismissed tasks count too, so retraining in the same month never reopens a handled priority.
    """
    high = [p for p in predictions if p.level == "high"]
    periods = {p.period for p in high}
    existing = set(
        db.session.query(CollectionTask.upz_id, CollectionTask.period).filter(CollectionTask.period.in_(periods))
    ) if periods else set()
    tasks = [
        CollectionTask(upz_id=p.upz_id, model_run=run, period=p.period, level=p.level, probability=p.probability)
        for p in high
        if (p.upz_id, p.period) not in existing
    ]
    db.session.add_all(tasks)
    return tasks


def task_list(status: str | None, page: int):
    query = CollectionTask.query.options(
        selectinload(CollectionTask.upz).selectinload(Upz.locality), selectinload(CollectionTask.updated_by)
    )
    if status in TASK_STATUSES:
        query = query.filter_by(status=status)
    return query.order_by(
        CollectionTask.period.desc(), CollectionTask.probability.desc(), CollectionTask.id
    ).paginate(page=page, per_page=PAGE_SIZE, error_out=False)


def status_counts() -> dict[str, int]:
    counts = dict.fromkeys(TASK_STATUSES, 0)
    counts.update(dict(
        db.session.query(CollectionTask.status, db.func.count(CollectionTask.id)).group_by(CollectionTask.status)
    ))
    return counts


def pending_count() -> int:
    return CollectionTask.query.filter_by(status="pending").count()


def open_reports_by_upz(upz_ids: set[int]) -> dict[int, int]:
    """Citizen reports still open or in progress, per UPZ."""
    if not upz_ids:
        return {}
    rows = (
        db.session.query(Report.upz_id, db.func.count(Report.id))
        .filter(Report.upz_id.in_(upz_ids), Report.source == "user", Report.status.in_(OPEN_REPORT_STATUSES))
        .group_by(Report.upz_id)
    )
    return dict(rows)


def update(admin: User, task_id: int, action: str, scheduled_for: str = "", note: str = "",
           close_reports: bool = False) -> tuple[CollectionTask, int]:
    """Schedule, complete or dismiss a task. Returns the task and the number of reports closed."""
    task = db.session.get(CollectionTask, task_id)
    if task is None:
        raise TaskError("Task not found.")
    if not task.is_open:
        raise TaskError("This task is already closed.")
    note = note.strip()
    if len(note) > NOTE_MAX:
        raise TaskError("Keep the note under 2,000 characters.")
    closed = 0
    if action == "schedule":
        try:
            task.scheduled_for = date.fromisoformat(scheduled_for)
        except ValueError:
            raise TaskError("Pick a collection date to schedule the task.") from None
        task.status = "scheduled"
    elif action == "done":
        task.status = "done"
        if close_reports:
            # Synthetic history is not moderated, the same rule as the report queue.
            closed = Report.query.filter(
                Report.upz_id == task.upz_id, Report.source == "user", Report.status.in_(OPEN_REPORT_STATUSES)
            ).update({"status": "closed", "updated_at": utcnow()}, synchronize_session=False)
    elif action == "dismiss":
        if not note:
            raise TaskError("Add a note saying why the task is dismissed.")
        task.status = "dismissed"
    else:
        raise TaskError("Unknown action.")
    if note:
        task.notes = note
    task.updated_by = admin
    db.session.commit()
    return task, closed
