from flask import abort, render_template, request
from flask_login import current_user

from app.blueprints.crisp import crisp_bp
from app.models import Upz
from app.services import evidence_service, inference_service, training_service
from ml import config as ml_config


def _context(slug: str, **extra):
    phase = evidence_service.phase(slug)
    if phase is None:
        abort(404)
    index = evidence_service.PHASES.index(phase)
    return dict(
        phase=phase, number=index + 1, phases=evidence_service.PHASES, ev=evidence_service.evidence(),
        previous=evidence_service.PHASES[index - 1] if index else None,
        following=evidence_service.PHASES[index + 1] if index + 1 < len(evidence_service.PHASES) else None,
        config=ml_config, labels=ml_config.FEATURE_LABELS, run=training_service.active_run(), **extra,
    )


@crisp_bp.route("")
def index():
    return render_template("crisp/index.html", phases=evidence_service.PHASES, ev=evidence_service.evidence())


@crisp_bp.route("/<slug>")
def phase(slug):
    return render_template(f"crisp/{slug}.html", **_context(slug))


@crisp_bp.route("/deployment", methods=["GET", "POST"])
def deployment():
    zones = inference_service.zones()
    upz = Upz.query.filter_by(code=request.args.get("upz", "80")).first() or zones[0]
    values, errors, result, unavailable = {}, [], None, None
    try:
        if request.method == "POST":
            values, errors = inference_service.clean_values(request.form)
            if not errors:
                user = current_user if current_user.is_authenticated else None
                result = inference_service.predict_values(user, values)
        else:
            values = inference_service.example_features(upz)
        columns = inference_service.demo_columns()
    except inference_service.InferenceUnavailable as error:
        unavailable, columns = str(error), []
    except inference_service.NotEnoughData:
        unavailable, columns = "There are not enough reports from complete months to fill the example.", []
    return render_template("crisp/deployment.html", **_context(
        "deployment", zones=zones, upz=upz, values=values, errors=errors, result=result,
        unavailable=unavailable, columns=columns))
