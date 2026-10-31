import pytest
from flask import session
from flask_login import current_user

from app.extensions import db
from app.models import User
from app.services import auth_service
from app.services.auth_service import EmailTaken
from app.utils.decorators import role_required


def register_via_form(client, email="ana@mail.com", password="secret123", confirm=None, **extra):
    return client.post(
        "/auth/register",
        data={
            "name": "Ana",
            "email": email,
            "password": password,
            "confirm": password if confirm is None else confirm,
            **extra,
        },
    )


def login_via_form(client, email="ana@mail.com", password="secret123", **extra):
    return client.post("/auth/login", data={"email": email, "password": password, **extra})


def test_register_then_login_redirects_home_with_session(client, db_session):
    response = register_via_form(client)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/login")

    response = login_via_form(client)
    assert response.status_code == 302
    assert response.headers["Location"] == "/"
    with client:
        client.get("/")
        assert current_user.is_authenticated
        assert current_user.email == "ana@mail.com"
        assert session["_user_id"]


def test_register_rejects_duplicate_email_ignoring_case(db_session):
    auth_service.register("Ana", "ana@mail.com", "secret123")
    with pytest.raises(EmailTaken):
        auth_service.register("Ana", "Ana@Mail.com", "secret123")


def test_register_normalizes_email(db_session):
    user = auth_service.register("Ana", "  Ana@Mail.COM ", "secret123")
    assert user.email == "ana@mail.com"
    assert user.role == "citizen"


def test_register_form_shows_duplicate_email_error(client, db_session):
    register_via_form(client)
    response = register_via_form(client, email="ANA@mail.com")
    assert response.status_code == 200
    assert b"already registered" in response.data


def test_wrong_password_shows_generic_error(client, db_session):
    auth_service.register("Ana", "ana@mail.com", "secret123")
    response = login_via_form(client, password="wrong-password")
    assert response.status_code == 200
    assert b"Invalid email or password" in response.data


def test_unknown_email_shows_same_error(client, db_session):
    response = login_via_form(client, email="nobody@mail.com")
    assert b"Invalid email or password" in response.data


def test_authenticate_normalizes_email(db_session):
    auth_service.register("Ana", "ana@mail.com", "secret123")
    assert auth_service.authenticate(" ANA@mail.com ", "secret123") is not None
    assert auth_service.authenticate("ana@mail.com", "nope") is None


def test_short_password_is_rejected(client, db_session):
    response = register_via_form(client, password="short")
    assert response.status_code == 200
    assert b"at least 8 characters" in response.data
    assert User.query.count() == 0


def test_password_confirmation_must_match(client, db_session):
    response = register_via_form(client, confirm="different123")
    assert response.status_code == 200
    assert User.query.count() == 0


def test_login_next_allows_relative_path(client, db_session):
    auth_service.register("Ana", "ana@mail.com", "secret123")
    response = client.post(
        "/auth/login?next=/api/zones", data={"email": "ana@mail.com", "password": "secret123"}
    )
    assert response.headers["Location"] == "/api/zones"


@pytest.mark.parametrize(
    "target",
    [
        "https://evil.example/",
        "//evil.example/",
        "///evil.com",
        "////evil.com",
        "evil",
        "/\t/evil.com",
        "/ /evil.com",
        "/\n/x",
        "/\\evil.com",
    ],
)
def test_login_next_ignores_external_targets(client, db_session, target):
    auth_service.register("Ana", "ana@mail.com", "secret123")
    response = client.post(
        "/auth/login", query_string={"next": target},
        data={"email": "ana@mail.com", "password": "secret123"},
    )
    assert response.headers["Location"] == "/"


def test_logout_clears_session(client, db_session):
    auth_service.register("Ana", "ana@mail.com", "secret123")
    login_via_form(client)
    response = client.post("/auth/logout")
    assert response.status_code == 302
    with client:
        client.get("/")
        assert not current_user.is_authenticated


def test_logout_rejects_get(client, db_session):
    assert client.get("/auth/logout").status_code == 405


def test_authenticated_user_visiting_login_is_redirected_home(client, db_session):
    auth_service.register("Ana", "ana@mail.com", "secret123")
    login_via_form(client)
    response = client.get("/auth/login")
    assert response.status_code == 302
    assert response.headers["Location"] == "/"


@pytest.fixture
def admin_app(app, db_session):
    @app.route("/_admin-only")
    @role_required("admin")
    def admin_only():
        return "ok"

    return app


def test_role_required_redirects_guest_to_login(admin_app):
    response = admin_app.test_client().get("/_admin-only")
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/auth/login")
    assert "next=" in response.headers["Location"]


def test_role_required_forbids_wrong_role(admin_app):
    client = admin_app.test_client()
    auth_service.register("Ana", "ana@mail.com", "secret123")
    login_via_form(client)
    assert client.get("/_admin-only").status_code == 403


def test_role_required_allows_matching_role(admin_app):
    client = admin_app.test_client()
    user = auth_service.register("Ana", "ana@mail.com", "secret123")
    user.role = "admin"
    db.session.commit()
    login_via_form(client)
    response = client.get("/_admin-only")
    assert response.status_code == 200
    assert response.data == b"ok"


def test_create_admin_creates_user(app, db_session):
    runner = app.test_cli_runner()
    result = runner.invoke(
        args=["create-admin", "--email", "Boss@Mail.com", "--name", "Boss"],
        input="secret123\nsecret123\n",
    )
    assert result.exit_code == 0, result.output
    user = User.query.filter_by(email="boss@mail.com").one()
    assert user.role == "admin"
    assert user.check_password("secret123")


def test_create_admin_promotion_sets_new_password(app, db_session):
    auth_service.register("Ana", "ana@mail.com", "secret123")
    runner = app.test_cli_runner()
    result = runner.invoke(
        args=["create-admin", "--email", "ana@mail.com", "--name", "Ana"],
        input="newsecret123\nnewsecret123\n",
    )
    assert result.exit_code == 0, result.output
    assert User.query.count() == 1
    user = User.query.one()
    assert user.role == "admin"
    assert user.check_password("newsecret123")
    assert not user.check_password("secret123")


def test_create_admin_rejects_short_password(app, db_session):
    runner = app.test_cli_runner()
    result = runner.invoke(
        args=["create-admin", "--email", "boss@mail.com", "--name", "Boss"],
        input="short\nshort\n",
    )
    assert result.exit_code != 0
    assert User.query.count() == 0
