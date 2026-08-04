from .base import *  # noqa: F403

DEBUG = False
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

# Railway terminates TLS at the edge and probes over HTTP on $PORT.
# Keep redirect off by default so healthchecks do not get stuck in 301 loops.
SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "false").lower() in ("true", "1", "yes")  # noqa: F405
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "0"))  # noqa: F405
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HSTS_SECONDS > 0
SECURE_HSTS_PRELOAD = SECURE_HSTS_SECONDS > 0
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# Allow Railway public hostnames when ALLOWED_HOSTS is not fully enumerated.
if "*" not in ALLOWED_HOSTS:  # noqa: F405
    ALLOWED_HOSTS.extend([".up.railway.app", ".railway.app"])  # noqa: F405
