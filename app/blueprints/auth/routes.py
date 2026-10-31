from urllib.parse import urlsplit

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.blueprints.auth import auth_bp
from app.forms.auth import LoginForm, RegisterForm
from app.services import auth_service


def safe_next_target() -> str | None:
    """Only follow same-site relative paths so a crafted link can't redirect off-site."""
    target = request.args.get("next", "")
    # Browsers drop tabs/newlines and treat backslash like "/", so a path such as "/<TAB>/evil.com" becomes "//evil.com".
    if not target or any(ord(c) <= 0x20 or ord(c) == 0x7F or c == "\\" for c in target):
        return None
    parts = urlsplit(target)
    if target.startswith("//") or parts.scheme or parts.netloc or not parts.path.startswith("/"):
        return None
    return target


def safe_next_url() -> str:
    return safe_next_target() or url_for("main.home")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))
    form = RegisterForm()
    if form.validate_on_submit():
        try:
            auth_service.register(form.name.data, form.email.data, form.password.data)
        except auth_service.EmailTaken:
            form.email.errors.append("This email is already registered.")
        else:
            flash("Account created. Please log in.", "success")
            return redirect(url_for("auth.login", next=safe_next_target()))
    return render_template("auth/register.html", form=form, next_target=safe_next_target())


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))
    form = LoginForm()
    if form.validate_on_submit():
        user = auth_service.authenticate(form.email.data, form.password.data)
        if user is not None:
            login_user(user, remember=form.remember.data)
            return redirect(safe_next_url())
        flash("Invalid email or password", "error")
    return render_template("auth/login.html", form=form, next_target=safe_next_target())


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return redirect(url_for("main.home"))
