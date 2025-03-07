#!/bin/bash
set -e

# Log all output
exec > >(tee -a /var/log/deploy.log) 2>&1
echo "Starting validate_service.sh at $(date)"

# Function to check service status
check_service() {
    local service=$1
    if ! systemctl is-active --quiet $service; then
        echo "$service is not running"
        return 1
    fi
    return 0
}

# Check if services are running
echo "Validating services..."
services=("nginx" "supervisor")
for service in "${services[@]}"; do
    if ! check_service $service; then
        echo "Service validation failed"
        exit 1
    fi
done

# Check if application is responding
echo "Checking application health..."
max_retries=5
retry_count=0
while [ $retry_count -lt $max_retries ]; do
    if curl -sf http://localhost:8000/health/ > /dev/null; then
        echo "Application is healthy"
        break
    else
        echo "Health check failed, attempt $((retry_count + 1)) of $max_retries"
        retry_count=$((retry_count + 1))
        if [ $retry_count -eq $max_retries ]; then
            echo "Application health check failed after $max_retries attempts"
            exit 1
        fi
        sleep 5
    fi
done

# Check if static files are accessible
echo "Checking static files..."
if ! curl -sf http://localhost/static/admin/css/base.css > /dev/null; then
    echo "Static files are not accessible"
    exit 1
fi

# Check PostgreSQL connection
echo "Checking database connection..."
if ! sudo -u ubuntu /var/www/django-app/venv/bin/python -c "
import psycopg2
import os
try:
    conn = psycopg2.connect(
        dbname=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        host=os.getenv('DB_HOST'),
        port=os.getenv('DB_PORT', '5432')
    )
    conn.close()
    print('Database connection successful')
except Exception as e:
    print(f'Database connection failed: {e}')
    exit(1)
"; then
    echo "Database validation failed"
    exit 1
fi

# Check disk space
echo "Checking disk space..."
df -h / | awk 'NR==2 {print $5}' | cut -d'%' -f1 | (read used
    if [ $used -gt 90 ]; then
        echo "Warning: Disk space usage is above 90%"
        exit 1
    fi
)

# Check memory usage
echo "Checking memory usage..."
free | awk '/Mem:/ {print $3/$2 * 100.0}' | (read used
    if [ ${used%.*} -gt 90 ]; then
        echo "Warning: Memory usage is above 90%"
        exit 1
    fi
)

# Check application logs for errors
echo "Checking application logs for errors..."
if grep -i "error\|exception\|failed" /var/log/django-app/django-app.err.log &> /dev/null; then
    echo "Found errors in application logs"
    tail -n 10 /var/log/django-app/django-app.err.log
    exit 1
fi

echo "All validation checks passed successfully at $(date)"
exit 0
