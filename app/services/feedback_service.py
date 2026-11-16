from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models import Feedback, User
from app.models.operations import FEEDBACK_STATUSES

PAGE_SIZE = 25


class FeedbackError(Exception):
    """A ticket change that is not allowed; the message is shown to the admin."""


def safe_page(page: str | None) -> str | None:
    """Keep only an app path, so the stored page can be shown as a link without pointing elsewhere."""
    page = (page or "").strip()
    if not page.startswith("/") or page.startswith("//") or len(page) > 255:
        return None
    return page


def create(user: User, kind: str, message: str, page: str | None) -> Feedback:
    ticket = Feedback(user=user, kind=kind, message=message.strip(), page=safe_page(page))
    db.session.add(ticket)
    db.session.commit()
    return ticket


def list_for_user(user: User) -> list[Feedback]:
    return Feedback.query.filter_by(user_id=user.id).order_by(Feedback.created_at.desc(), Feedback.id.desc()).all()


def queue(status: str | None, page: int):
    query = Feedback.query.options(selectinload(Feedback.user))
    if status in FEEDBACK_STATUSES:
        query = query.filter_by(status=status)
    return query.order_by(Feedback.created_at.desc(), Feedback.id.desc()).paginate(
        page=page, per_page=PAGE_SIZE, error_out=False
    )


def status_counts() -> dict[str, int]:
    counts = dict.fromkeys(FEEDBACK_STATUSES, 0)
    counts.update(dict(db.session.query(Feedback.status, db.func.count(Feedback.id)).group_by(Feedback.status)))
    return counts


def respond(ticket_id: int, status: str, response: str) -> Feedback:
    if status not in FEEDBACK_STATUSES:
        raise FeedbackError("Unknown status.")
    ticket = db.session.get(Feedback, ticket_id)
    if ticket is None:
        raise FeedbackError("Ticket not found.")
    ticket.status = status
    ticket.response = response.strip()[:2000] or None
    db.session.commit()
    return ticket
