#!/bin/bash
set -e

# Log all output
exec > >(tee -a /var/log/deploy.log) 2>&1
echo "Starting start_application.sh at $(date)"

# Function to check service status
check_service() {
    local service=$1
    if ! systemctl is-active --quiet $service; then
        systemctl start $service || {
            echo "Failed to start $service"
            return 1
        }
    fi
    return 0
}

# Reload Nginx with configuration test
echo "Reloading Nginx..."
if nginx -t; then
    systemctl reload nginx || {
        echo "Failed to reload Nginx"
        exit 1
    }
else
    echo "Nginx configuration test failed"
    exit 1
fi

# Check and restart supervisor if needed
echo "Checking supervisor..."
if ! check_service supervisor; then
    echo "Failed to ensure supervisor is running"
    exit 1
fi

# Update and restart application
echo "Updating supervisor and restarting application..."
supervisorctl reread || {
    echo "Failed to reread supervisor configuration"
    exit 1
}

supervisorctl update || {
    echo "Failed to update supervisor"
    exit 1
}

supervisorctl restart django-app || {
    echo "Failed to restart django-app"
    exit 1
}

# Wait for application to become responsive
echo "Waiting for application to become responsive..."
max_retries=12
retry_count=0
while [ $retry_count -lt $max_retries ]; do
    if curl -sf http://localhost:8000/health/ > /dev/null; then
        echo "Application is responding"
        break
    else
        echo "Waiting for application to respond... ($(($retry_count + 1))/$max_retries)"
        retry_count=$((retry_count + 1))
        if [ $retry_count -eq $max_retries ]; then
            echo "Application failed to respond after 60 seconds"
            exit 1
        fi
        sleep 5
    fi
done

# Verify static files are being served
echo "Verifying static files..."
if ! curl -sf http://localhost/static/admin/css/base.css > /dev/null; then
    echo "Static files are not being served correctly"
    exit 1
fi

echo "start_application.sh completed successfully at $(date)"
exit 0
