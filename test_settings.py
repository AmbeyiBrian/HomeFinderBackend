from HomeFinderBackend.settings import *

# Use SQLite for tests
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Disable external services during tests
SENTRY_DSN = None

# Configure storage for tests
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {
            "location": "test_media/",
            "base_url": "/media/",
        },
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

MEDIA_ROOT = 'test_media/'
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Configure test specific settings
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']