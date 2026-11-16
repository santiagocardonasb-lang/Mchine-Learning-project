from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.blueprints.main import main_bp
from app.forms.feedback import FeedbackForm
from app.models.operations import FEEDBACK_STATUSES
from app.services import feedback_service
from app.utils.decorators import role_required


@main_bp.route("/help", methods=["GET", "POST"])
@login_required
def help_feedback():
    form = FeedbackForm()
    if request.method == "GET":
        form.page.data = feedback_service.safe_page(request.args.get("page"))
    if form.validate_on_submit():
        feedback_service.create(current_user._get_current_object(), form.kind.data, form.message.data, form.page.data)
        flash("Thanks, your ticket was sent. You can follow it below.", "success")
        return redirect(url_for("main.help_feedback", _anchor="tickets"))
    return render_template(
        "feedback/help.html", form=form, tickets=feedback_service.list_for_user(current_user)
    )


@main_bp.route("/admin/feedback")
@role_required("admin")
def feedback_admin():
    status = request.args.get("status") or None
    return render_template(
        "feedback/admin.html",
        queue=feedback_service.queue(status, request.args.get("page", 1, type=int)),
        status=status,
        statuses=FEEDBACK_STATUSES,
        counts=feedback_service.status_counts(),
    )


@main_bp.post("/admin/feedback/<int:ticket_id>")
@role_required("admin")
def feedback_respond(ticket_id):
    try:
        feedback_service.respond(ticket_id, request.form.get("status", ""), request.form.get("response", ""))
    except feedback_service.FeedbackError as error:
        flash(str(error), "error")
    else:
        flash(f"Ticket {ticket_id} updated.", "success")
    return redirect(
        url_for(
            "main.feedback_admin",
            status=request.form.get("filter") or None,
            page=request.form.get("page", 1, type=int),
        )
    )
