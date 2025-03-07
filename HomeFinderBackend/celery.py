from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from django.conf import settings
from celery.schedules import crontab

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'HomeFinderBackend.settings')

# Create the Celery app
app = Celery('HomeFinderBackend')

# Load configuration from Django settings first
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task-specific configuration from celeryconfig.py
app.config_from_object('HomeFinderBackend.celeryconfig')

# Auto-discover tasks in all installed apps
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

@app.task(bind=True)
def debug_task(self):
    """Task for debugging worker status"""
    print(f'Request: {self.request!r}')

# Configure periodic tasks
app.conf.beat_schedule = {
    'cleanup-abandoned-reservations': {
        'task': 'properties.tasks.cleanup_abandoned_reservations',
        'schedule': crontab(minute='*/15'),  # Run every 15 minutes
    },
    'cleanup-expired-transactions': {
        'task': 'payments.tasks.cleanup_expired_transactions',
        'schedule': 300.0,  # Run every 5 minutes (300 seconds)
    },
}