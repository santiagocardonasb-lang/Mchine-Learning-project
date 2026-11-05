from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.blueprints.admin import admin_bp
from app.models import STATUSES
from app.models.user import ROLES
from app.services import admin_service, training_service
from app.utils.decorators import role_required
from ml import config as ml_config


@admin_bp.route("")
@role_required("admin")
def index():
    status = request.args.get("status") or None
    page = request.args.get("page", 1, type=int)
    return render_template(
        "admin/index.html",
        queue=admin_service.report_queue(status, page),
        status=status,
        statuses=STATUSES,
        counts=admin_service.status_counts(),
        users=admin_service.users(),
        roles=ROLES,
        runs=training_service.recent_runs(5),
        since_last_run=training_service.reports_since_last_run(),
        threshold=ml_config.AUTO_RETRAIN_THRESHOLD,
        running=training_service.is_running(),
    )


@admin_bp.post("/reports/<int:report_id>/status")
@role_required("admin")
def report_status(report_id):
    try:
        admin_service.set_status(report_id, request.form.get("status", ""))
    except admin_service.AdminError as error:
        flash(str(error), "error")
    else:
        flash(f"Report {report_id} updated.", "success")
    return redirect(
        url_for(
            "admin.index",
            status=request.form.get("filter") or None,
            page=request.form.get("page", 1, type=int),
        )
    )


@admin_bp.post("/users/<int:user_id>/role")
@role_required("admin")
def user_role(user_id):
    try:
        user = admin_service.set_role(
            current_user, user_id, request.form.get("role", "")
        )
    except admin_service.AdminError as error:
        flash(str(error), "error")
    else:
        flash(f"{user.name} is now {user.role}.", "success")
    return redirect(url_for("admin.index") + "#users")