from app.extensions import db


class Locality(db.Model):
    __tablename__ = "localities"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), nullable=False, unique=True)
    name = db.Column(db.String(120), nullable=False)
    population = db.Column(db.Integer)

    upzs = db.relationship("Upz", back_populates="locality")


class Upz(db.Model):
    __tablename__ = "upz"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), nullable=False, unique=True)
    name = db.Column(db.String(120), nullable=False)
    locality_id = db.Column(db.Integer, db.ForeignKey("localities.id"), nullable=False)
    # Real UAESP count of active clandestine-dumping critical points.
    critical_points = db.Column(db.Integer, nullable=False, default=0)
    public_space_m2_per_inhabitant = db.Column(db.Float)
    area_km2 = db.Column(db.Float)

    locality = db.relationship("Locality", back_populates="upzs")
