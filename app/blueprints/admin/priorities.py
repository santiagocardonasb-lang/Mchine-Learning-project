from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.blueprints.admin import admin_bp
from app.models.operations import TASK_STATUSES
from app.services import collection_service
from app.utils.decorators import role_required


@admin_bp.route("/priorities")
@role_required("admin")
def priorities():
    status = request.args.get("status") or None
    tasks = collection_service.task_list(status, request.args.get("page", 1, type=int))
    return render_template(
        "admin/priorities.html",
        tasks=tasks,
        status=status,
        statuses=TASK_STATUSES,
        counts=collection_service.status_counts(),
        open_reports=collection_service.open_reports_by_upz({t.upz_id for t in tasks.items if t.is_open}),
    )


@admin_bp.post("/priorities/<int:task_id>")
@role_required("admin")
def priority_update(task_id):
    try:
        task, closed = collection_service.update(
            current_user._get_current_object(),
            task_id,
            request.form.get("action", ""),
            scheduled_for=request.form.get("scheduled_for", ""),
            note=request.form.get("note", ""),
            close_reports=bool(request.form.get("close_reports")),
        )
    except collection_service.TaskError as error:
        flash(str(error), "error")
    else:
        message = f"{task.upz.name} is now {task.status}."
        if closed:
            message += f" {closed} open report{'s' if closed != 1 else ''} closed."
        flash(message, "success")
    return redirect(
        url_for(
            "admin.priorities",
            status=request.form.get("filter") or None,
            page=request.form.get("page", 1, type=int),
        )
    )
