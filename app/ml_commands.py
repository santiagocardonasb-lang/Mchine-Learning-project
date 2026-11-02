
import click
import pandas as pd
from flask import Flask
from sqlalchemy import insert

from app.extensions import db
from app.models import Report, Upz
from app.services import training_service
from ml.synthetic import OUTPUT as SYNTHETIC_CSV
from ml.train import NotEnoughData

BOOL_COLUMNS = ["has_rodents", "has_insects", "has_odor", "near_water"]


def seed_synthetic(replace: bool = False) -> int:
    """Load data/synthetic_reports.csv as source='synthetic'. Returns the rows inserted."""
    existing = Report.query.filter_by(source="synthetic")
    if existing.count():
        if not replace:
            return 0
        existing.delete()

    zones = {code: (upz_id, locality_id)
             for code, upz_id, locality_id in db.session.query(Upz.code, Upz.id, Upz.locality_id)}
    if not zones:
        raise click.ClickException("Zones are not loaded; run `flask load-zones` first.")

    df = pd.read_csv(SYNTHETIC_CSV, dtype={"upz_code": str}, keep_default_na=False)
    rows = []
    for r in df.to_dict("records"):
        upz_id, locality_id = zones[r["upz_code"]]
        rows.append({
            "latitude": r["latitude"], "longitude": r["longitude"],
            "upz_id": upz_id, "locality_id": locality_id,
            "neighborhood": r["neighborhood"] or None,
            "reported_at": pd.Timestamp(r["reported_at"]).to_pydatetime(),
            "updated_at": pd.Timestamp(r["updated_at"]).to_pydatetime(),
            "waste_type": r["waste_type"], "size": r["size"], "status": r["status"],
            **{c: r[c] in (True, "True") for c in BOOL_COLUMNS},
            "source": "synthetic",
        })
    # Core insert in chunks: one round trip per chunk instead of one per report.
    for start in range(0, len(rows), 2000):
        db.session.execute(insert(Report), rows[start:start + 2000])
    db.session.commit()
    return len(rows)


def register_ml_commands(app: Flask) -> None:
    @app.cli.command("seed-synthetic")
    @click.option("--replace", is_flag=True, help="Delete the synthetic reports already loaded first.")
    def seed_synthetic_command(replace):
        """Load the synthetic report history from data/synthetic_reports.csv."""
        inserted = seed_synthetic(replace)
        if inserted == 0:
            click.echo("Synthetic reports are already loaded (use --replace to reload).")
        else:
            click.echo(f"Loaded {inserted} synthetic reports.")

    @app.cli.command("train")
    def train_command():
        """Train the models now and make the new run active."""
        try:
            run = training_service.run("cli")
        except NotEnoughData as error:
            raise click.ClickException(str(error)) from None
        test = run.metrics["test"]
        click.echo(f"Run {run.id}: {run.metrics['chosen_model']} on {run.n_rows} rows, "
                   f"test macro-F1 {test['macro_f1']:.2f}, recall high {test['recall_high']:.2f}.")
