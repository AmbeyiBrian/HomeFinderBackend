#!/bin/bash
set -e

# Log all output
exec > >(tee -a /var/log/deploy.log) 2>&1
echo "Starting before_install.sh at $(date)"

# Create application directory
echo "Creating application directory..."
mkdir -p /var/www/django-app
mkdir -p /var/www/django-app/staticfiles
mkdir -p /var/www/django-app/media
mkdir -p /var/log/django-app

# Set proper permissions
chown -R ubuntu:ubuntu /var/www/django-app
chmod -R 755 /var/www/django-app

# Install system dependencies
echo "Installing system dependencies..."
apt-get update
apt-get install -y python3.10 python3.10-venv python3-pip nginx supervisor

echo "before_install.sh completed at $(date)"