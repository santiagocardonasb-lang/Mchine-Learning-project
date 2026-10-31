from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.blueprints.reports import reports_bp
from app.forms.report import ReportForm
from app.services import report_service

BOGOTA_CENTER = (4.63, -74.11)


def preset_point() -> tuple[float, float]:
    """The pin's start: ?lat=&lon= from "Report here" when valid, else the city centre."""
    try:
        lat, lon = float(request.args["lat"]), float(request.args["lon"])
    except (KeyError, ValueError):
        return BOGOTA_CENTER
    # NaN fails every comparison, so it falls back too.
    if -90 <= lat <= 90 and -180 <= lon <= 180:
        return lat, lon
    return BOGOTA_CENTER


@reports_bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    form = ReportForm()
    if request.method == "GET":
        form.latitude.data, form.longitude.data = preset_point()
    if form.validate_on_submit():
        try:
            report_service.create(
                current_user._get_current_object(),
                form.latitude.data,
                form.longitude.data,
                form.waste_type.data,
                form.size.data,
                form.has_rodents.data,
                form.has_insects.data,
                form.has_odor.data,
                form.near_water.data,
                (form.description.data or "").strip() or None,
            )
        except report_service.OutsideCoverage:
            form.latitude.errors.append("This point is outside the covered area.")
        except report_service.ZonesNotLoaded:
            flash("Reports are temporarily unavailable. Please try again later.", "error")
        else:
            flash("Report sent", "success")
            return redirect(url_for("map.index"))
    return render_template("reports/new.html", form=form)
