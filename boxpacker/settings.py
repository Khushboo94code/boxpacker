"""
Django settings for the boxpacker project (AI-Assisted Box Selection System).

Kept intentionally small. Secrets and environment-specific values are read from
environment variables so the same settings file works in dev and CI.
"""
import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

# Railway sets RAILWAY_ENVIRONMENT on every deploy; we use it to pick safe
# production defaults without any extra configuration.
ON_RAILWAY = "RAILWAY_ENVIRONMENT" in os.environ

# SECURITY -------------------------------------------------------------------
# Never ship the insecure default to production; set DJANGO_SECRET_KEY in env.
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-dev-key-change-me-in-production",
)

# Debug defaults ON locally, OFF on Railway (override with DJANGO_DEBUG).
DEBUG = os.environ.get("DJANGO_DEBUG", "0" if ON_RAILWAY else "1") == "1"

ALLOWED_HOSTS = os.environ.get(
    "DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1"
).split(",")
CSRF_TRUSTED_ORIGINS = []

if ON_RAILWAY:
    # Trust Railway's own domains: the internal healthcheck host, the private
    # service network, and any generated public domain (*.up.railway.app).
    # This is what lets the platform healthcheck reach "/" without a 400
    # DisallowedHost, even before a public domain is generated.
    ALLOWED_HOSTS += [
        "healthcheck.railway.app",
        ".railway.app",
        ".up.railway.app",
        ".railway.internal",
    ]
    for _var in ("RAILWAY_PUBLIC_DOMAIN", "RAILWAY_PRIVATE_DOMAIN"):
        _dom = os.environ.get(_var)
        if _dom:
            ALLOWED_HOSTS.append(_dom)
    _public = os.environ.get("RAILWAY_PUBLIC_DOMAIN")
    if _public:
        CSRF_TRUSTED_ORIGINS.append(f"https://{_public}")

# APPLICATIONS ---------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "selection",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # WhiteNoise serves static files (admin + DRF browsable API) in production
    # without needing a separate web server / CDN.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "boxpacker.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "boxpacker.wsgi.application"

# DATABASE -------------------------------------------------------------------
# Uses DATABASE_URL when present (Railway's Postgres plugin sets this), and
# falls back to a local SQLite file for development. Railway's disk is
# ephemeral, so Postgres is strongly recommended in production — see README.
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# PASSWORD VALIDATION --------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# INTERNATIONALIZATION -------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# STATIC ---------------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Compressed, hashed static files served by WhiteNoise.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# PRODUCTION SECURITY --------------------------------------------------------
# Railway terminates TLS at its edge and forwards the original scheme in this
# header, so Django can tell it is really being served over HTTPS.
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    # SSL redirect is OPT-IN. Railway's internal healthcheck hits the app over
    # plain HTTP (no X-Forwarded-Proto), so forcing a redirect turns the "/"
    # healthcheck into a 301 and the deploy is marked unhealthy. Public traffic
    # already arrives over HTTPS via Railway's edge. Enable it once the domain
    # is live by setting DJANGO_SSL_REDIRECT=1.
    SECURE_SSL_REDIRECT = os.environ.get("DJANGO_SSL_REDIRECT", "0") == "1"
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True

# DRF ------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
}
