from app.extensions import db
from app.models import User


class EmailTaken(Exception):
    """Raised when registering an email that already has an account."""


def normalize_email(email: str) -> str:
    return email.strip().lower()


def register(name: str, email: str, password: str) -> User:
    email = normalize_email(email)
    if User.query.filter_by(email=email).first():
        raise EmailTaken(email)
    user = User(name=name.strip(), email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def authenticate(email: str, password: str) -> User | None:
    user = User.query.filter_by(email=normalize_email(email)).first()
    if user is not None and user.check_password(password):
        return user
    return None
