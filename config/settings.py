"""Configurações do Portal QuIIN (local com SQLite, produção via env/Render + Postgres)."""
import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get("SECRET_KEY", "django-insecure-quiin-demo-local-only-7f3c9a2e")

DEBUG = os.environ.get("DEBUG", "True") == "True"

ALLOWED_HOSTS = ["127.0.0.1", "localhost", "testserver"]
_render_host = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if _render_host:
    ALLOWED_HOSTS.append(_render_host)
_extra_hosts = os.environ.get("ALLOWED_HOSTS", "")
if _extra_hosts:
    ALLOWED_HOSTS.extend(h.strip() for h in _extra_hosts.split(",") if h.strip())

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_cotton.apps.SimpleAppConfig",
    "django_tailwind_cli",
    "django_htmx",
    "template_partials.apps.SimpleAppConfig",
    "apps.accounts",
    "apps.core",
    "apps.pillars",
    "apps.indicators",
    "apps.periods",
    "apps.entries",
    "apps.finance",
    "apps.accountability",
    "apps.projects",
    "apps.reports",
    "apps.audit",
    "apps.highlights",
    "apps.crm_at",
    "apps.talentos",
    "apps.gestao_at",
    "apps.planning",
    "apps.seed",
]

MIDDLEWARE = [
    "apps.entries.effective.OperationalValuesMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        # Loaders explícitos: cotton e template-partials não são composáveis via
        # auto-configuração (ambos reescrevem OPTIONS["loaders"] em ready()).
        # Cadeia: partials → cached → cotton → filesystem/app_directories.
        "APP_DIRS": False,
        "OPTIONS": {
            "loaders": [
                (
                    "template_partials.loader.Loader",
                    [
                        (
                            "django.template.loaders.cached.Loader",
                            [
                                "django_cotton.cotton_loader.Loader",
                                "django.template.loaders.filesystem.Loader",
                                "django.template.loaders.app_directories.Loader",
                            ],
                        )
                    ],
                )
            ],
            "builtins": ["django_cotton.templatetags.cotton"],
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.nav",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
        conn_health_checks=True,
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 4}},
]

AUTH_USER_MODEL = "accounts.User"

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
WHITENOISE_MANIFEST_STRICT = False

# ---------- Mídia em produção (Cloudflare R2 / S3 compatível) ----------
# Sem as variáveis abaixo, o desenvolvimento local continua usando
# FileSystemStorage e MEDIA_ROOT. Com elas, o Django grava e lê as fotos no R2.
_R2_BUCKET = os.environ.get("AWS_STORAGE_BUCKET_NAME", "").strip()
if _R2_BUCKET:
    _R2_ENDPOINT = os.environ.get("AWS_S3_ENDPOINT_URL", "").strip().rstrip("/")
    _R2_ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY_ID", "").strip()
    _R2_SECRET_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "").strip()
    _faltando = [
        nome
        for nome, valor in (
            ("AWS_S3_ENDPOINT_URL", _R2_ENDPOINT),
            ("AWS_ACCESS_KEY_ID", _R2_ACCESS_KEY),
            ("AWS_SECRET_ACCESS_KEY", _R2_SECRET_KEY),
        )
        if not valor
    ]
    if _faltando:
        raise ImproperlyConfigured(
            "Cloudflare R2 configurado parcialmente; defina: " + ", ".join(_faltando)
        )
    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": _R2_BUCKET,
            "endpoint_url": _R2_ENDPOINT,
            "access_key": _R2_ACCESS_KEY,
            "secret_key": _R2_SECRET_KEY,
            "region_name": os.environ.get("AWS_S3_REGION_NAME", "auto"),
            "signature_version": "s3v4",
            # Bucket privado: as URLs de <img> são assinadas e expiram.
            "querystring_auth": os.environ.get("AWS_QUERYSTRING_AUTH", "True").lower() == "true",
            "querystring_expire": int(os.environ.get("AWS_QUERYSTRING_EXPIRE", "3600")),
            "file_overwrite": False,
            "default_acl": None,
        },
    }

_csrf_origins = os.environ.get("CSRF_TRUSTED_ORIGINS", "")
if _csrf_origins:
    CSRF_TRUSTED_ORIGINS = [o.strip() for o in _csrf_origins.split(",") if o.strip()]
elif _render_host:
    CSRF_TRUSTED_ORIGINS = [f"https://{_render_host}"]

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:dashboard"

# No protótipo local, mensagens de recuperação aparecem no console do servidor.
# Um ambiente com envio real pode selecionar o backend SMTP via variáveis.
EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "SIG QuIIN <nao-responda@quiin.local>")
EMAIL_HOST = os.environ.get("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "25"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "False") == "True"
EMAIL_USE_SSL = os.environ.get("EMAIL_USE_SSL", "False") == "True"

# ---------- Front-end (retrofit visual) ----------
TAILWIND_CLI_VERSION = "4.3.3"  # versão pinada após `manage.py tailwind config`
TAILWIND_CLI_SRC_CSS = "assets/styles/input.css"
TAILWIND_CLI_DIST_CSS = "css/tailwind.css"

COTTON_DIR = "components"
COTTON_SNAKE_CASED_NAMES = False
