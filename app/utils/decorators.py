from functools import wraps

from flask import abort
from flask_login import current_user

from app.extensions import login_manager


def role_required(role: str):
    """Guests are sent to the login page; logged-in users with another role get a 403."""

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return login_manager.unauthorized()
            if current_user.role != role:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator
