import importlib

import pytest

import config

from app import create_app
from config import get_config, normalize_db_url


def test_normalize_postgres_scheme():
    assert (
        normalize_db_url("postgres://u:p@h:5432/db")
        == "postgresql+psycopg://u:p@h:5432/db"
    )


def test_normalize_postgresql_scheme():
    assert (
        normalize_db_url("postgresql://u:p@h:5432/db")
        == "postgresql+psycopg://u:p@h:5432/db"
    )


def test_sqlite_untouched():
    assert normalize_db_url("sqlite:///x.db") == "sqlite:///x.db"


def test_prod_requires_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    # Keep create_app from reloading a developer's local .env.
    monkeypatch.setattr("app.load_dotenv", lambda *a, **k: None)
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        create_app("production")


def test_prod_requires_secret_key(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/db")
    monkeypatch.setattr("app.load_dotenv", lambda *a, **k: None)
    for value in (None, ""):
        if value is None:
            monkeypatch.delenv("SECRET_KEY", raising=False)
        else:
            monkeypatch.setenv("SECRET_KEY", value)
        with pytest.raises(RuntimeError, match="SECRET_KEY"):
            create_app("production")


def test_empty_env_vars_fall_back_to_defaults(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("SECRET_KEY", "")
    try:
        importlib.reload(config)
        assert config.Config.SQLALCHEMY_DATABASE_URI.startswith("sqlite:///")
        assert config.Config.SECRET_KEY
    finally:
        monkeypatch.undo()
        importlib.reload(config)


def test_home_responds(client, db_session):
    assert client.get("/").status_code == 200


def test_production_cookies_are_secure():
    prod = get_config("production")
    assert prod.SESSION_COOKIE_SECURE is True
    assert prod.REMEMBER_COOKIE_SECURE is True
    assert prod.SESSION_COOKIE_SAMESITE == "Lax"
    assert prod.REMEMBER_COOKIE_SAMESITE == "Lax"


def test_render_requires_production_config(monkeypatch):
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setattr("app.load_dotenv", lambda *a, **k: None)
    with pytest.raises(RuntimeError, match="FLASK_ENV=production"):
        create_app("development")


def test_csrf_tokens_do_not_expire():
    assert config.Config.WTF_CSRF_TIME_LIMIT is None
