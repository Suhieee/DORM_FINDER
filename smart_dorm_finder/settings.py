from pathlib import Path
import os
from django.core.exceptions import ImproperlyConfigured

# Load environment variables from .env file (optional)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not installed, continue without it
    pass



# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    if DEBUG:
        # Only allow fallback in development mode
        import warnings
        warnings.warn(
            'SECRET_KEY not set. Using a development-only fallback. '
            'Set SECRET_KEY environment variable for production!',
            UserWarning
        )
        SECRET_KEY = 'django-insecure-dev-only-key-change-in-production-05gc*o_f_4$62!kmpj!d+ddrz=!pxy7%!8)j(=ln2li4el7+b3'
    else:
        # In production, SECRET_KEY is REQUIRED
        raise ValueError(
            'SECRET_KEY environment variable must be set for production! '
            'Set it in your environment variables or .env file.'
        )

# Update ALLOWED_HOSTS for better security
ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1,.railway.app').split(',')

# CSRF settings for Railway deployment
CSRF_TRUSTED_ORIGINS = os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',') if os.environ.get('CSRF_TRUSTED_ORIGINS') else []
if not CSRF_TRUSTED_ORIGINS and not DEBUG:
    # Auto-generate from ALLOWED_HOSTS if not set
    CSRF_TRUSTED_ORIGINS = [f'https://{host}' for host in ALLOWED_HOSTS if host and host != 'localhost' and host != '127.0.0.1']

# ADD THIS CRITICAL LINE FOR RAILWAY
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')  # ← ADD THIS LINE

# Session and CSRF cookie settings for HTTPS
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# Session timeout settings (15 minutes of inactivity)
SESSION_COOKIE_AGE = 900  # 15 minutes in seconds
SESSION_SAVE_EVERY_REQUEST = True  # Update session on every request to reset timeout
SESSION_EXPIRE_AT_BROWSER_CLOSE = True  # Session ends when browser closes
# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'cloudinary_storage',
    'cloudinary',
    'accounts',
    'dormitory',
    'user_profile'
]

AUTH_USER_MODEL = 'accounts.CustomUser'


LOGIN_REDIRECT_URL = '/accounts/dashboard/'  # Redirect to dashboard after login
LOGOUT_REDIRECT_URL = '/accounts/login/'  # Redirect to login page after logout


MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'accounts.middleware.SessionTimeoutMiddleware',  # Session timeout warning
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# Rate limiting cache (for django-ratelimit)
RATELIMIT_ENABLE = True  # Can be disabled in testing
RATELIMIT_USE_CACHE = 'default'  # Use default cache for rate limiting

ROOT_URLCONF = 'smart_dorm_finder.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'dormitory.views.user_context',
                'accounts.context_processors.notifications',
            ],
        },
    },
]

WSGI_APPLICATION = 'smart_dorm_finder.wsgi.application'


database_url = os.environ.get('DATABASE_URL', '')
print(f"DATABASE_URL present: {'Yes' if database_url else 'No'}")

if database_url:
    # Mask password for security in logs
    from urllib.parse import urlparse
    parsed = urlparse(database_url)
    if parsed.password:
        masked_url = database_url.replace(parsed.password, '***')
        print(f"Database URL (masked): {masked_url}")

# Handle database configuration WITH SQLITE FALLBACK
if database_url and 'postgres' in database_url.lower():
    # Use PostgreSQL if DATABASE_URL is provided and is PostgreSQL
    try:
        import dj_database_url
        
        DATABASES = {
            'default': dj_database_url.parse(
                database_url,
                conn_max_age=600,
                conn_health_checks=True,
                ssl_require=True
            )
        }
        
        # For psycopg3, we need to update ENGINE
        DATABASES['default']['ENGINE'] = 'django.db.backends.postgresql'
        
        print(f"✅ Using PostgreSQL database: {DATABASES['default']['NAME']}")
        
    except Exception as e:
        print(f"❌ PostgreSQL connection failed: {e}")
        print("⚠️  Falling back to SQLite...")
        # Fallback to SQLite
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': BASE_DIR / 'db.sqlite3',
            }
        }
else:
    # Use SQLite for local development (when DATABASE_URL is empty or not PostgreSQL)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
    print(f"✅ Using SQLite database for local development: {DATABASES['default']['NAME']}")

# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/

STATIC_URL = '/static/'

if DEBUG:
    STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
else:
    STATIC_ROOT = os.path.join(BASE_DIR, 'static')

# Media files configuration - Use Cloudinary in production, local in development
CLOUDINARY_CLOUD_NAME = os.environ.get('CLOUDINARY_CLOUD_NAME', '')
CLOUDINARY_API_KEY = os.environ.get('CLOUDINARY_API_KEY', '')
CLOUDINARY_API_SECRET = os.environ.get('CLOUDINARY_API_SECRET', '')

if CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET:
    # Use Cloudinary for production
    import cloudinary
    import cloudinary.uploader
    import cloudinary.api
    
    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET,
        secure=True
    )
    
    DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'
    MEDIA_URL = '/media/'  # Cloudinary will handle the actual URLs
else:
    # Use local storage for development
    MEDIA_URL = '/media/'
    MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Email backend configuration
# Railway blocks direct SMTP, so we use SendGrid or Mailgun for production
# For local development, use Gmail SMTP

# Check if we're using a service like SendGrid or Mailgun
SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY', '')
MAILGUN_API_KEY = os.environ.get('MAILGUN_API_KEY', '')
MAILGUN_DOMAIN = os.environ.get('MAILGUN_DOMAIN', '')

# Use SendGrid if API key is set
# Use HTTP API instead of SMTP (works on Railway free tier - SMTP ports are blocked)
if SENDGRID_API_KEY:
    # Use custom SendGrid HTTP API backend (works on free tier)
    EMAIL_BACKEND = 'accounts.email_backend.SendGridHTTPBackend'
    DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@dormfinder.com')
# Use Mailgun if API key is set
elif MAILGUN_API_KEY and MAILGUN_DOMAIN:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = 'smtp.mailgun.org'
    EMAIL_PORT = 587
    EMAIL_USE_TLS = True
    EMAIL_HOST_USER = os.environ.get('MAILGUN_SMTP_LOGIN', '')
    EMAIL_HOST_PASSWORD = MAILGUN_API_KEY
    DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', f'noreply@{MAILGUN_DOMAIN}')
# Fallback to Gmail SMTP (for local development)
else:
    EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
    EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
    EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
    EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True').lower() == 'true'
    EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
    EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
    DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER)

# Email timeout settings to prevent worker timeouts
EMAIL_TIMEOUT = 10  # 10 seconds timeout for email sending

# Cache configuration (using local memory cache - no Redis needed)
# This helps reduce database queries from context processors
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
        'OPTIONS': {
            'MAX_ENTRIES': 1000,
        },
        'TIMEOUT': 300,  # 5 minutes default timeout
    }
}

# Site URL for email verification links (use in production)
# Set this to your production domain (e.g., 'https://yourdomain.com')
# If not set, will use request.build_absolute_uri() which may not work correctly in production
SITE_URL = os.environ.get('SITE_URL', '')  # e.g., 'https://yourdomain.com'
if SITE_URL and not SITE_URL.endswith('/'):
    SITE_URL = SITE_URL + '/'