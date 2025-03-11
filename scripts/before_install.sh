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

# Add deadsnakes PPA for Python 3.12
echo "Adding Python 3.12 repository..."
add-apt-repository -y ppa:deadsnakes/ppa || {
    echo "Failed to add Python PPA"
    exit 1
}

# Install system dependencies
echo "Installing system dependencies..."
apt-get update || {
    echo "Failed to update package list"
    exit 1
}

# Install Python 3.12 and other dependencies
apt-get install -y python3.10 python3.10-venv python3.10-dev python3-pip nginx supervisor postgresql postgresql-contrib libpq-dev || {
    echo "Failed to install required packages"
    exit 1
}

# Verify Python installation
python3.12 --version || {
    echo "Python 3.10 installation failed"
    exit 1
}

echo "before_install.sh completed successfully at $(date)"