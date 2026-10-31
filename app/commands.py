import csv
from pathlib import Path

import click
from flask import Flask

from app.extensions import db
from app.models import Locality, Upz

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def read_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def to_float(value: str) -> float | None:
    return float(value) if value != "" else None


def load_zones() -> tuple[int, int]:
    """Upsert localities and UPZ by code from the prepared CSV files."""
    localities = {}
    for row in read_csv(DATA_DIR / "raw" / "locality_population.csv"):
        locality = Locality.query.filter_by(code=row["code"]).first() or Locality(code=row["code"])
        locality.name = row["name"]
        locality.population = int(row["population"])
        db.session.add(locality)
        localities[row["code"]] = locality

    stats = read_csv(DATA_DIR / "zone_stats.csv")
    for row in stats:
        upz = Upz.query.filter_by(code=row["upz_code"]).first() or Upz(code=row["upz_code"])
        upz.name = row["upz_name"]
        upz.locality = localities[row["locality_code"]]
        upz.critical_points = int(row["critical_points"])
        upz.public_space_m2_per_inhabitant = to_float(row["public_space_m2_per_inhabitant"])
        upz.area_km2 = to_float(row["area_km2"])
        db.session.add(upz)

    db.session.commit()
    return len(localities), len(stats)


def register_commands(app: Flask) -> None:
    @app.cli.command("load-zones")
    def load_zones_command():
        """Load localities and UPZ from data/zone_stats.csv and the population CSV."""
        localities, upzs = load_zones()
        click.echo(f"Loaded {localities} localities and {upzs} UPZ.")
