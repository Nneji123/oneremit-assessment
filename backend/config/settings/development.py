"""Development settings.

Defaults are injected into the environment before importing the base
settings so the existing env-driven DEBUG/REQUIRE_SECRETS guard logic in
:mod:`config.settings.base` behaves exactly as it did in the old single
``config/settings.py`` module.
"""

import os

os.environ.setdefault("DEBUG", "1")
os.environ.setdefault("ALLOWED_HOSTS", "localhost,127.0.0.1")
os.environ.setdefault("CORS_ALLOWED_ORIGINS", "http://localhost:3000")

from .base import *  # noqa: F403
