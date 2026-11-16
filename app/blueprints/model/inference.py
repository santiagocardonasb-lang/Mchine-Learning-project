from flask import flash, render_template, request
from flask_login import current_user, login_required

from app.blueprints.model import model_bp
from app.models import Upz
from app.services import inference_service, training_service
from ml import config as ml_config


@model_bp.route("/risk-check", methods=["GET", "POST"])
@login_required
def risk_check():
    code = request.values.get("upz", "")
    result = None
    if request.method == "POST":
        upz = Upz.query.filter_by(code=code).one_or_none()
        if upz is None:
            flash("Choose a UPZ to check.", "error")
        else:
            try:
                result = inference_service.predict_zone(current_user._get_current_object(), upz)
            except inference_service.InferenceUnavailable as error:
                flash(str(error), "error")
    run = result.run if result else training_service.active_run()
    return render_template(
        "model/risk_check.html",
        zones=inference_service.zones(),
        selected=code,
        result=result,
        run=run,
        levels=ml_config.RISK_LEVELS,
        feature_labels=ml_config.FEATURE_LABELS,
    )


@model_bp.route("/inferences")
@login_required
def inference_history():
    return render_template(
        "model/inference_history.html",
        logs=inference_service.history(current_user, request.args.get("page", 1, type=int)),
    )
