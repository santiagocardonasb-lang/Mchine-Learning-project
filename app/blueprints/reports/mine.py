from flask import render_template
from flask_login import current_user, login_required

from app.blueprints.reports import reports_bp
from app.forms.report import SIZE_CHOICES
from app.services import report_service


@reports_bp.route("/mine")
@login_required
def mine():
    return render_template(
        "reports/mine.html",
        reports=report_service.list_for_user(current_user),
        size_labels={c.value: c.label.lower() for c in SIZE_CHOICES},
    )
