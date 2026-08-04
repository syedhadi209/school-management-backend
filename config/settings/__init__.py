import os

# Default to local development settings. Production containers set
# DJANGO_SETTINGS_MODULE=config.settings.prod explicitly.
_env = os.getenv("DJANGO_ENV", "dev").lower()
if _env in {"prod", "production"}:
    from .prod import *  # noqa: F401,F403
else:
    from .dev import *  # noqa: F401,F403
