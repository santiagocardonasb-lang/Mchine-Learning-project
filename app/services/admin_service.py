from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import STATUSES, Report, User
from app.models.user import ROLES

PAGE_SIZE = 25


class AdminError(Exception):
    """An admin action that is not allowed; the message is shown to the admin."""


def report_queue(status: str | None, page: int):
    """Citizen reports, newest first, optionally of one status. Synthetic history is not moderated."""
    query = Report.query.filter_by(source="user").options(
        joinedload(Report.user), joinedload(Report.upz), joinedload(Report.locality)
    )
    if status in STATUSES:
        query = query.filter_by(status=status)
    return query.order_by(Report.reported_at.desc()).paginate(
        page=page, per_page=PAGE_SIZE, error_out=False
    )


def status_counts() -> dict[str, int]:
    rows = (
        db.session.query(Report.status, db.func.count(Report.id))
        .filter(Report.source == "user")
        .group_by(Report.status)
    )
    counts = dict.fromkeys(STATUSES, 0)
    counts.update(dict(rows))
    return counts


def set_status(report_id: int, status: str) -> Report:
    if status not in STATUSES:
        raise AdminError("Unknown status.")
    report = db.session.get(Report, report_id)
    if report is None or report.source != "user":
        raise AdminError("Report not found.")
    report.status = status
    db.session.commit()
    return report


def users() -> list[User]:
    return User.query.order_by(User.created_at.desc()).all()


def set_role(acting: User, user_id: int, role: str) -> User:
    if role not in ROLES:
        raise AdminError("Unknown role.")
    user = db.session.get(User, user_id)
    if user is None:
        raise AdminError("User not found.")
    if user.id == acting.id:
        raise AdminError("You can't change your own role.")
    user.role = role
    db.session.commit()
    return user