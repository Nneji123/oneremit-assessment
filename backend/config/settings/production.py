"""Production settings.

DEBUG is forced off and REQUIRE_SECRETS is forced on so that the secret
guard and database checks in :mod:`config.settings.base` fail closed.
CORS origins are taken only from the environment; there is no SQLite
fallback because REQUIRE_SECRETS makes the base database logic raise
without a real ``DATABASE_URL`` or complete ``POSTGRES_*`` config.
"""

import os

os.environ["DEBUG"] = "0"

from .base import *  # noqa: F403

DEBUG = False
REQUIRE_SECRETS = True

ENVIRONMENT = "production"

CORS_ALLOWED_ORIGINS = [
    origin for origin in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",") if origin
]
