import os
from pathlib import Path

INSTANCE_DIR = Path(__file__).resolve().parent / "instance"


def normalize_db_url(url: str) -> str:
    """Point Postgres URLs at the psycopg 3 driver; leave other URLs alone."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-secret-change-me"
    SQLALCHEMY_DATABASE_URI = normalize_db_url(
        os.environ.get("DATABASE_URL") or f"sqlite:///{INSTANCE_DIR / 'locwaste.db'}"
    )
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}


class DevConfig(Config):
    DEBUG = True


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    WTF_CSRF_ENABLED = False


class ProdConfig(Config):
    pass


_CONFIGS = {
    "development": DevConfig,
    "testing": TestConfig,
    "production": ProdConfig,
}


def get_config(name: str) -> type[Config]:
    try:
        return _CONFIGS[name]
    except KeyError:
        raise ValueError(f"Unknown config name: {name!r}") from None
