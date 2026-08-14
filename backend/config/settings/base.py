import os
import sys
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent.parent

sys.path.insert(0, str(BASE_DIR / "apps"))

ENVIRONMENT = os.environ.get("ENVIRONMENT", "local")

DEBUG = os.environ.get("DEBUG", "0") == "1"
REQUIRE_SECRETS = not DEBUG or ENVIRONMENT.lower() in {"prod", "production"}

_PLACEHOLDER_PREFIXES = (
    "change-me",
    "local-development",
    "replace-me",
    "todo",
    "fixme",
)


def _is_placeholder(value: str) -> bool:
    lowered = value.strip().lower()
    return not lowered or any(lowered.startswith(p) for p in _PLACEHOLDER_PREFIXES)


def _require_secret(name: str) -> str:
    value = os.environ.get(name, "")
    if REQUIRE_SECRETS and _is_placeholder(value):
        raise ValueError(
            f"{name} must be set to a real value for this environment "
            f"(ENVIRONMENT={ENVIRONMENT})."
        )
    return value


SECRET_KEY = _require_secret("SECRET_KEY")

PROVIDER_WEBHOOK_SECRET = _require_secret("PROVIDER_WEBHOOK_SECRET")

ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "rest_framework",
    "corsheaders",
    "drf_spectacular",
    "core",
    "transfers",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

WSGI_APPLICATION = "config.wsgi.application"

DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    _pg_db = os.environ.get("POSTGRES_DB")
    _pg_user = os.environ.get("POSTGRES_USER")
    _pg_password = os.environ.get("POSTGRES_PASSWORD")
    _pg_host = os.environ.get("POSTGRES_HOST")
    _pg_port = os.environ.get("POSTGRES_PORT")

    if REQUIRE_SECRETS and not all([_pg_db, _pg_user, _pg_password, _pg_host]):
        raise ValueError(
            "DATABASE_URL or complete POSTGRES_* settings are required "
            "for this environment."
        )

    if all([_pg_db, _pg_user, _pg_password, _pg_host]):
        if REQUIRE_SECRETS and _is_placeholder(_pg_password):
            raise ValueError(
                "POSTGRES_PASSWORD must be set to a real value for this environment."
            )

        from urllib.parse import quote_plus

        _encoded_password = quote_plus(_pg_password)
        _port = _pg_port or "5432"
        DATABASE_URL = (
            f"postgres://{_pg_user}:{_encoded_password}@{_pg_host}:{_port}/{_pg_db}"
        )
    else:
        DATABASE_URL = f"sqlite:///{BASE_DIR / 'db.sqlite3'}"

DATABASES = {"default": dj_database_url.parse(DATABASE_URL)}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOWED_ORIGINS = os.environ.get(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:3000",
).split(",")

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "UNAUTHENTICATED_USER": None,
    "DEFAULT_PAGINATION_CLASS": "core.pagination.StandardResultsSetPagination",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Oneremit Assessment API",
    "DESCRIPTION": "Payout dashboard API",
    "VERSION": "1.0.0",
}
