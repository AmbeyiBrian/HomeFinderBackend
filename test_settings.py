# Override base settings for testing
import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-test-key-not-for-production'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['*']

# Application definition - import from main settings
from HomeFinderBackend.settings import INSTALLED_APPS, MIDDLEWARE, ROOT_URLCONF, TEMPLATES, AUTH_USER_MODEL, REST_FRAMEWORK

# Use SQLite for tests
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Storage Configuration - Use local file system for tests
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {
            "location": os.path.join(BASE_DIR, 'test_media'),
            "base_url": "/media/",
        },
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

# Media/Static files
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'test_media')
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'test_static')

# Disable external services during tests
SENTRY_DSN = None
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Configure test specific settings
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

# Required Django Settings
USE_TZ = True
USE_L10N = True
USE_I18N = True
TIME_ZONE = 'UTC'