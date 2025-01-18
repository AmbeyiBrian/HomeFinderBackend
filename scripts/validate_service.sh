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
