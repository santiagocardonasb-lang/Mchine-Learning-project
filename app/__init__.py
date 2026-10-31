import os
from urllib.parse import urlsplit

from dotenv import load_dotenv
from flask import Flask, flash, redirect, request, url_for
from flask_wtf.csrf import CSRFError

from app.extensions import csrf, db, login_manager, migrate


def create_app(config_name: str | None = None) -> Flask:
    load_dotenv()
    # config.py reads the environment at import time, so import it after load_dotenv.
    from config import INSTANCE_DIR, get_config

    config_name = config_name or os.environ.get("FLASK_ENV", "development")
    if config_name == "production":
        for name in ("DATABASE_URL", "SECRET_KEY"):
            if not os.environ.get(name):
                raise RuntimeError(f"{name} must be set in production.")

    if os.environ.get("RENDER") and config_name != "production":
        raise RuntimeError("Set FLASK_ENV=production on Render.")

    INSTANCE_DIR.mkdir(exist_ok=True)
    app = Flask(__name__)
    app.config.from_object(get_config(config_name))

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    login_manager.login_view = "auth.login"

    @login_manager.user_loader
    def load_user(user_id: str):
        from app.models import User

        return db.session.get(User, int(user_id))

    from app import models  # noqa: F401  (registers tables so Flask-Migrate sees them)
    from app.blueprints.api import api_bp
    from app.blueprints.auth import auth_bp
    from app.blueprints.main import main_bp
    from app.blueprints.map import map_bp
    from app.blueprints.reports import reports_bp
    from app.commands import register_commands

    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(map_bp)
    app.register_blueprint(reports_bp)
    register_commands(app)

    @app.errorhandler(CSRFError)
    def csrf_expired(error: CSRFError):
        flash("Your session expired. Please try again.", "error")
        referrer = request.referrer
        if referrer and urlsplit(referrer).netloc == request.host:
            return redirect(referrer)
        return redirect(url_for("main.home"))

    return app
