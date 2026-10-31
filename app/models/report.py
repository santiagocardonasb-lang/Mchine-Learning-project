from sqlalchemy.orm import validates

from app.extensions import db
from app.models.user import utcnow

WASTE_TYPES = ("household", "construction_debris", "bulky", "organic", "mixed")
SIZES = ("small", "medium", "large")
STATUSES = ("open", "in_progress", "closed", "rejected")
SOURCES = ("user", "synthetic")


class Report(db.Model):
    __tablename__ = "reports"

    id = db.Column(db.Integer, primary_key=True)
    # Null for synthetic reports, which have no author.
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    locality_id = db.Column(db.Integer, db.ForeignKey("localities.id"))
    upz_id = db.Column(db.Integer, db.ForeignKey("upz.id"), index=True)
    neighborhood = db.Column(db.String(120))
    reported_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utcnow, index=True
    )
    waste_type = db.Column(db.String(30), nullable=False)
    size = db.Column(db.String(20), nullable=False)
    has_rodents = db.Column(db.Boolean, nullable=False, default=False)
    has_insects = db.Column(db.Boolean, nullable=False, default=False)
    has_odor = db.Column(db.Boolean, nullable=False, default=False)
    near_water = db.Column(db.Boolean, nullable=False, default=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), nullable=False, default="open", index=True)
    source = db.Column(db.String(20), nullable=False, default="user")
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    user = db.relationship("User", back_populates="reports")
    locality = db.relationship("Locality")
    upz = db.relationship("Upz")

    @staticmethod
    def _check(value, allowed, field):
        if value not in allowed:
            raise ValueError(f"Invalid {field}: {value!r}. Allowed: {', '.join(allowed)}")
        return value

    @validates("waste_type")
    def _validate_waste_type(self, key, value):
        return self._check(value, WASTE_TYPES, key)

    @validates("size")
    def _validate_size(self, key, value):
        return self._check(value, SIZES, key)

    @validates("status")
    def _validate_status(self, key, value):
        return self._check(value, STATUSES, key)

    @validates("source")
    def _validate_source(self, key, value):
        return self._check(value, SOURCES, key)
