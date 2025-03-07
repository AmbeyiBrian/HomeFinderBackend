#!/bin/bash
set -e

# Log all output
exec > >(tee -a /var/log/deploy.log) 2>&1
echo "Starting validate_service.sh at $(date)"

# Check if Nginx is running
echo "Checking Nginx status..."
if ! systemctl is-active --quiet nginx; then
    echo "Nginx is not running"
    exit 1
fi

# Wait for application to start
echo "Waiting for application to start..."
sleep 10

# Check if application is responding
echo "Checking application response..."
if ! curl -s http://localhost > /dev/null; then
    echo "Application is not responding"
    exit 1
fi

echo "Application deployment validated successfully"
echo "validate_service.sh completed at $(date)"

echo "Verifying environment variables..."
if [ -f /var/www/django-app/.env ]; then
    echo ".env file exists"
    # Print first character of sensitive values to verify they're set
    echo "AWS_STORAGE_BUCKET_NAME is set: ${AWS_STORAGE_BUCKET_NAME:0:1}*****"
    echo "AWS_S3_REGION_NAME is set: ${AWS_S3_REGION_NAME}"
    echo "AWS_ACCESS_KEY_ID is set: ${AWS_ACCESS_KEY_ID:0:1}*****"
    echo "AWS_SECRET_ACCESS_KEY is set: ${AWS_SECRET_ACCESS_KEY:0:1}*****"
else
    echo ".env file is missing!"
    exit 1
fi

# Check if gunicorn is running
if ! pgrep -f "gunicorn"; then
    echo "ERROR: Gunicorn is not running"
    exit 1
fi

# Check if celery worker is running
if ! pgrep -f "celery.*worker"; then
    echo "ERROR: Celery worker is not running"
    exit 1
fi

# Check if celery beat is running
if ! pgrep -f "celery.*beat"; then
    echo "ERROR: Celery beat is not running"
    exit 1
fi

# Check Redis connection
if ! redis-cli ping; then
    echo "ERROR: Redis is not responding"
    exit 1
fi

# Check database connection using Django
if ! python manage.py dbshell <<< '\q'; then
    echo "ERROR: Database connection failed"
    exit 1
fi

# Check API health endpoint
if ! curl -f http://localhost:8000/health/; then
    echo "ERROR: API health check failed"
    exit 1
fi

echo "All services are running correctly"
exit 0
