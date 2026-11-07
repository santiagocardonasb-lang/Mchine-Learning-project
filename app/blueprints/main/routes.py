from flask import redirect, render_template, url_for
from flask_login import login_required

from app import content
from app.blueprints.main import main_bp
from app.services import risk_service, stats_service, training_service


@main_bp.route("/")
def home():
    return render_template(
        "main/index.html",
        content=content,
        run=training_service.active_run(),
        city=risk_service.city_stats(),
        priority_zones=stats_service.top_priority_zones(),
    )


@main_bp.route("/app")
@login_required
def app_home():
    return render_template(
        "main/home.html",
        reports_this_month=stats_service.reports_this_month(),
        priority_zones=stats_service.top_priority_zones(),
        city=risk_service.city_stats(),
    )


@main_bp.route("/about")
def about():
    return redirect(url_for("main.home", _anchor="context"))


@main_bp.route("/how-it-works")
def how_it_works():
    return redirect(url_for("main.home", _anchor="solution"))
