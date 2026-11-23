from sqlalchemy.orm import validates

from app.extensions import db
from app.models.model_run import RISK_LEVELS
from app.models.user import utcnow

INFERENCE_KINDS = ("zone", "batch", "demo")
INFERENCE_STATUSES = ("ok", "error")
TASK_STATUSES = ("pending", "scheduled", "done", "dismissed")
OPEN_TASK_STATUSES = ("pending", "scheduled")
EVENT_KINDS = ("request", "inference", "error")
FEEDBACK_KINDS = ("incident", "bug", "suggestion")
FEEDBACK_STATUSES = ("open", "in_review", "resolved")


def _check(value, allowed, field):
    if value not in allowed:
        raise ValueError(f"Invalid {field}: {value!r}. Allowed: {', '.join(allowed)}")
    return value


class InferenceLog(db.Model):
    __tablename__ = "inference_logs"

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, index=True)
    # Null for automatic and command-line runs.
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    # Null only when no model was available.
    model_run_id = db.Column(db.Integer, db.ForeignKey("model_runs.id"))
    # Null for batch runs, which predict every UPZ.
    upz_id = db.Column(db.Integer, db.ForeignKey("upz.id"))
    kind = db.Column(db.String(10), nullable=False)
    level = db.Column(db.String(10))
    probability = db.Column(db.Float)
    duration_ms = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(10), nullable=False, default="ok")
    error = db.Column(db.Text)

    user = db.relationship("User")
    model_run = db.relationship("ModelRun")
    upz = db.relationship("Upz")

    @validates("kind")
    def _validate_kind(self, key, value):
        return _check(value, INFERENCE_KINDS, key)

    @validates("status")
    def _validate_status(self, key, value):
        return _check(value, INFERENCE_STATUSES, key)

    @validates("level")
    def _validate_level(self, key, value):
        return value if value is None else _check(value, RISK_LEVELS, key)


class CollectionTask(db.Model):
    __tablename__ = "collection_tasks"

    id = db.Column(db.Integer, primary_key=True)
    upz_id = db.Column(db.Integer, db.ForeignKey("upz.id"), nullable=False, index=True)
    model_run_id = db.Column(db.Integer, db.ForeignKey("model_runs.id"), nullable=False)
    period = db.Column(db.Date, nullable=False)  # first day of the predicted month
    level = db.Column(db.String(10), nullable=False)
    probability = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    scheduled_for = db.Column(db.Date)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    updated_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    upz = db.relationship("Upz")
    model_run = db.relationship("ModelRun")
    updated_by = db.relationship("User")

    @validates("level")
    def _validate_level(self, key, value):
        return _check(value, RISK_LEVELS, key)

    @validates("status")
    def _validate_status(self, key, value):
        return _check(value, TASK_STATUSES, key)

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_TASK_STATUSES


class AppEvent(db.Model):
    __tablename__ = "app_events"

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, index=True)
    kind = db.Column(db.String(20), nullable=False, index=True)
    path = db.Column(db.String(255))
    method = db.Column(db.String(10))
    status_code = db.Column(db.Integer)
    duration_ms = db.Column(db.Float)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    message = db.Column(db.Text)

    @validates("kind")
    def _validate_kind(self, key, value):
        return _check(value, EVENT_KINDS, key)


class Feedback(db.Model):
    __tablename__ = "feedback"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    kind = db.Column(db.String(20), nullable=False)
    message = db.Column(db.Text, nullable=False)
    page = db.Column(db.String(255))  # the app page the ticket was sent from
    status = db.Column(db.String(20), nullable=False, default="open", index=True)
    response = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    user = db.relationship("User")

    @validates("kind")
    def _validate_kind(self, key, value):
        return _check(value, FEEDBACK_KINDS, key)

    @validates("status")
    def _validate_status(self, key, value):
        return _check(value, FEEDBACK_STATUSES, key)
