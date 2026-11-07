from urllib.parse import urlsplit

from flask import flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.blueprints.model import model_bp
from app.services import training_service
from app.utils.decorators import role_required
from ml import config as ml_config


@model_bp.route("/model")
@login_required
def index():
    run = training_service.active_run()
    return render_template(
        "model/index.html",
        run=run,
        reading=training_service.error_reading(run.metrics) if run else [],
        runs=training_service.recent_runs(),
        feature_labels=ml_config.FEATURE_LABELS,
        levels=ml_config.RISK_LEVELS,
        running=training_service.is_running(),
    )


@model_bp.route("/crisp-dm")
def crisp_dm():
    return redirect(url_for("main.home", _anchor="phases"))


@model_bp.post("/model/retrain")
@role_required("admin")
def retrain():
    if training_service.start("manual"):
        flash("Training started. Refresh this page in a minute to see the new run.", "success")
    else:
        flash("A training run is already in progress.", "error")
    # The admin panel posts here too, so return to the page the button was on.
    target = request.form.get("next", "")
    if not target.startswith("/") or target.startswith("//") or urlsplit(target).netloc:
        target = url_for("model.index")
    return redirect(target)