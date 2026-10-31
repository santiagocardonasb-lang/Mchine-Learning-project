from sqlalchemy.orm import validates

from app.extensions import db
from app.models.user import utcnow

TRIGGERS = ("manual", "auto", "cli")
RISK_LEVELS = ("low", "medium", "high")


class ModelRun(db.Model):
    __tablename__ = "model_runs"

    id = db.Column(db.Integer, primary_key=True)
    trained_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    trigger = db.Column(db.String(20), nullable=False)
    n_rows = db.Column(db.Integer, nullable=False)
    params = db.Column(db.JSON, nullable=False, default=dict)
    metrics = db.Column(db.JSON, nullable=False, default=dict)
    # joblib bytes, stored in the database because Render's disk is wiped on deploy.
    artifact = db.Column(db.LargeBinary)
    is_active = db.Column(db.Boolean, nullable=False, default=False)

    predictions = db.relationship("RiskPrediction", back_populates="model_run")

    @validates("trigger")
    def _validate_trigger(self, key, value):
        if value not in TRIGGERS:
            raise ValueError(f"Invalid trigger: {value!r}")
        return value


class RiskPrediction(db.Model):
    __tablename__ = "risk_predictions"

    id = db.Column(db.Integer, primary_key=True)
    model_run_id = db.Column(
        db.Integer, db.ForeignKey("model_runs.id"), nullable=False, index=True
    )
    upz_id = db.Column(db.Integer, db.ForeignKey("upz.id"), nullable=False, index=True)
    period = db.Column(db.Date, nullable=False)  # first day of the predicted month
    level = db.Column(db.String(10), nullable=False)
    probability = db.Column(db.Float, nullable=False)

    model_run = db.relationship("ModelRun", back_populates="predictions")
    upz = db.relationship("Upz")

    @validates("level")
    def _validate_level(self, key, value):
        if value not in RISK_LEVELS:
            raise ValueError(f"Invalid level: {value!r}")
        return value
