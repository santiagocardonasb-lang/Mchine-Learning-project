from flask import render_template

from app import content
from app.blueprints.main import main_bp
from app.services import risk_service, stats_service


@main_bp.route("/")
def home():
    return render_template(
        "main/home.html",
        reports_this_month=stats_service.reports_this_month(),
        priority_zones=stats_service.top_priority_zones(),
        city=risk_service.city_stats(),
    )


@main_bp.route("/about")
def about():
    return render_template("main/about.html", content=content)


@main_bp.route("/how-it-works")
def how_it_works():
    return render_template("main/how_it_works.html", content=content)
