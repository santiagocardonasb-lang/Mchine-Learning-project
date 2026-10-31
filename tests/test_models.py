import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Report, User


def make_user(email="ana@example.com"):
    user = User(name="Ana", email=email)
    user.set_password("secret1")
    return user


def make_report(**overrides):
    fields = dict(
        latitude=4.65,
        longitude=-74.08,
        waste_type="household",
        size="small",
    )
    fields.update(overrides)
    return Report(**fields)


def test_password_hashing(db_session):
    user = make_user()

    assert user.check_password("secret1") is True
    assert user.check_password("wrong") is False
    assert user.password_hash != "secret1"


def test_email_unique(db_session):
    db_session.add(make_user())
    db_session.commit()

    db_session.add(make_user())
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_report_defaults(db_session):
    report = make_report()
    db_session.add(report)
    db_session.commit()

    assert report.status == "open"
    assert report.source == "user"
    assert report.reported_at is not None


def test_report_rejects_unknown_waste_type(db_session):
    with pytest.raises(ValueError):
        make_report(waste_type="plastic")
