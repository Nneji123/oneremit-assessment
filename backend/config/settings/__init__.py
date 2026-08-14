import os

_ENVIRONMENT = os.environ.get("ENVIRONMENT", "local").lower()

if _ENVIRONMENT in {"production", "prod", "staging"}:
    from .production import *  # noqa: F403
else:
    from .development import *  # noqa: F403
