#!/bin/bash
set -e

# Log all output
exec > >(tee -a /var/log/deploy.log) 2>&1
echo "Starting start_application.sh at $(date)"

# Reload Nginx configuration
echo "Reloading Nginx..."
systemctl reload nginx

# Restart Supervisor and application
echo "Restarting application..."
supervisorctl reread
supervisorctl update
supervisorctl restart django-app

echo "start_application.sh completed at $(date)"
