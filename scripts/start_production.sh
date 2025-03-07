#!/bin/bash

# Exit on error
set -e

echo "Running database migrations..."
python manage.py migrate --no-input

echo "Collecting static files..."
python manage.py collectstatic --no-input

echo "Starting Celery worker..."
celery -A HomeFinderBackend worker -l info -Q default,payments,cleanup --detach

echo "Starting Celery beat..."
celery -A HomeFinderBackend beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler --detach

echo "Starting Gunicorn..."
gunicorn --config gunicorn_config.py HomeFinderBackend.wsgi:application