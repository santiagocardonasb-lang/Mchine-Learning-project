from flask import render_template

from app.blueprints.monitoring import monitoring_bp
from app.services import monitoring_service, training_service
from app.utils.decorators import role_required
from ml import config as ml_config


@monitoring_bp.route("")
@role_required("admin")
def index():
    return render_template(
        "monitoring/index.html",
        data=monitoring_service.overview(),
        levels=ml_config.RISK_LEVELS,
        running=training_service.is_running(),
    )
