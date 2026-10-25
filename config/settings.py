import os
from pathlib import Path
import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
env = os.environ.get

DEBUG = env("DEBUG", "False") == "True"
SECRET_KEY = env("SECRET_KEY") or ("dev-only-key" if DEBUG else None)
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY must be set in production")
ALLOWED_HOSTS = [h for h in env("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h]

INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "django.contrib.sites",
    "allauth", "allauth.account", "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "allauth.mfa",
    "core", "accounts", "verification", "payouts", "rewards", "marketplace", "bookings", "inventory", "subscriptions", "messaging", "support",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "core.middleware.ReferralCaptureMiddleware",
    "core.middleware.StaffMFAMiddleware",
    "core.middleware.SecurityHeadersMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"], "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
        "core.context.assets",
        "core.context.site",
    ]},
}]
WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {"default": dj_database_url.config(
    default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}", conn_max_age=60, ssl_require=False)}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": f"django.contrib.auth.password_validation.{n}"}
    for n in ("UserAttributeSimilarityValidator", "MinimumLengthValidator",
              "CommonPasswordValidator", "NumericPasswordValidator")]
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
SITE_ID = 1
LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "/"
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_RATE_LIMITS = {"login_failed": "5/5m"}
SOCIALACCOUNT_PROVIDERS = {"google": {"SCOPE": ["profile", "email"]}}
EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")

LANGUAGE_CODE = "en-ke"
TIME_ZONE = "Africa/Nairobi"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
                    if not DEBUG else "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 3600  # raise after confirming HTTPS works
    SECURE_CONTENT_TYPE_NOSNIFF = True

# Business rules (configurable, per PRD section 26)
DEFAULT_DEPOSIT_PERCENT = 50
PENDING_PAYMENT_MINUTES = 10
SLOT_STEP_MINUTES = 30
MIN_ADVANCE_HOURS = 2
BOOKING_HORIZON_DAYS = 60

MPESA = {
    "ENV": env("MPESA_ENV", "sandbox"),
    "KEY": env("MPESA_CONSUMER_KEY", ""),
    "SECRET": env("MPESA_CONSUMER_SECRET", ""),
    "SHORTCODE": env("MPESA_SHORTCODE", "174379"),
    "PASSKEY": env("MPESA_PASSKEY", ""),
    "CALLBACK_BASE": env("MPESA_CALLBACK_BASE", ""),
    "CALLBACK_SECRET": env("MPESA_CALLBACK_SECRET", "dev-secret"),
    # B2C (payouts/withdrawals) needs separate Safaricom approval and its own shortcode
    "B2C_ENABLED": env("MPESA_B2C_ENABLED", "False") == "True",
    "B2C_SHORTCODE": env("MPESA_B2C_SHORTCODE", ""),
    "INITIATOR": env("MPESA_INITIATOR_NAME", ""),
    "SECURITY_CREDENTIAL": env("MPESA_SECURITY_CREDENTIAL", ""),
}

# --- Subscriptions ---
TRIAL_DAYS = 14
SUBSCRIPTION_GRACE_DAYS = 7

# --- Admin 2FA (enforced for staff when DEBUG is False) ---
MFA_SUPPORTED_TYPES = ["totp"]

# --- Email (use a transactional provider in production; set SPF/DKIM/DMARC on the domain) ---
if env("EMAIL_HOST"):
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = env("EMAIL_HOST")
    EMAIL_PORT = int(env("EMAIL_PORT", "587"))
    EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
    EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "GlowHub <no-reply@yourdomain.co.ke>")
SERVER_EMAIL = DEFAULT_FROM_EMAIL
ADMINS = [("Admin", env("ADMIN_EMAIL"))] if env("ADMIN_EMAIL") else []

# --- Shared cache for rate limits (Redis in production) ---
if env("REDIS_URL"):
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": env("REDIS_URL")}}

# --- Logging ---
LOGGING = {"version": 1, "disable_existing_loggers": False,
           "handlers": {"console": {"class": "logging.StreamHandler"}},
           "root": {"handlers": ["console"], "level": "INFO"}}
DATA_UPLOAD_MAX_MEMORY_SIZE = 2_000_000

# --- Phone verification & messaging channels ---
REQUIRE_PHONE_FOR_BOOKING = env("REQUIRE_PHONE_FOR_BOOKING", "True") == "True"
AT_USERNAME = env("AT_USERNAME", "sandbox")          # Africa's Talking (SMS)
AT_API_KEY = env("AT_API_KEY", "")
AT_SENDER_ID = env("AT_SENDER_ID", "")
WA_TOKEN = env("WA_TOKEN", "")                       # WhatsApp Cloud API
WA_PHONE_ID = env("WA_PHONE_ID", "")
WA_TEMPLATE = env("WA_TEMPLATE", "")                 # an approved template with one {{1}} text parameter

# --- Private files (identity documents). Use private object storage + signed URLs in production ---
PRIVATE_MEDIA_ROOT = BASE_DIR / "private_media"
VERIFICATION_RETENTION_DAYS = 30
REQUIRE_VERIFICATION_TO_LIST = True

# --- Payouts / settlement (model: platform collects deposits centrally, then pays providers) ---
PLATFORM_FEE_PERCENT = 10
PAYOUT_HOLD_HOURS = 24
MIN_PAYOUT_KES = 500

# --- Diamonds rewards (marketing budget, withdrawable). Withdrawals are OFF until you enable them. ---
REWARDS_ENABLED = env("REWARDS_ENABLED", "True") == "True"
WITHDRAWALS_ENABLED = env("WITHDRAWALS_ENABLED", "False") == "True"
REWARDS = {
    "DIAMONDS_PER_KES": 10, "MIN_WITHDRAW_DIAMONDS": 1000, "HOLD_DAYS": 7, "DAILY_CAP": 1000,
    "MIN_ACCOUNT_AGE_DAYS": 7, "MIN_BOOKING_KES": 500, "REFERRAL_MONTHLY_CAP": 20,
    "REFERRER_CUSTOMER": 500, "REFERRER_PROVIDER": 1500, "REFEREE_BONUS": 200,
    "BOOKING_CUSTOMER": 50, "BOOKING_PROVIDER": 30, "REVIEW": 20, "PROFILE": 100,
}
if DEBUG:
    MEDIA_ROOT = BASE_DIR / "media"
ID_HASH_KEY = env("ID_HASH_KEY") or SECRET_KEY  # keyed hash of ID numbers (duplicate detection without storing the number)

# --- Images: Cloudinary when CLOUDINARY_URL is set (cloudinary://API_KEY:API_SECRET@CLOUD_NAME), else local disk ---
# ID documents and selfies are NOT stored here: they use private storage (see verification/models.py).
if env("CLOUDINARY_URL"):
    STORAGES["default"] = {"BACKEND": "core.storage.CloudinaryStorage"}
