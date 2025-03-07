#!/bin/bash

# Enable error handling
set -e

# Load environment variables from AWS Parameter Store or .env file
if [ -f .env ]; then
    echo "Loading .env file..."
    set -a
    source .env
    set +a
else
    echo "No .env file found. Ensure environment variables are set through AWS Parameter Store or EC2 instance metadata."
fi

# Log all output
exec > >(tee -a /var/log/deploy.log) 2>&1
echo "Starting after_install.sh at $(date)"

# Ensure script is run as root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root"
   exit 1
fi

# Update package list and install dependencies
echo "Updating package list and installing dependencies..."
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y python3.10-venv nginx supervisor certbot python3-certbot-nginx postgresql-client

# Ensure /var/www/django-app exists
mkdir -p /var/www/django-app
cd /var/www/django-app || exit 1

# Set correct permissions
echo "Setting correct permissions..."
chown -R ubuntu:ubuntu /var/www/django-app

# Create and activate virtual environment
echo "Setting up Python virtual environment..."
sudo -u ubuntu python3.10 -m venv venv

# Install Python dependencies
echo "Installing Python dependencies..."
sudo -u ubuntu /var/www/django-app/venv/bin/pip install -r requirements.txt

# Create environment file
echo "Setting up environment file..."
cat > /var/www/django-app/.env <<EOL
# .env
SECRET_KEY=${SECRET_KEY}
DJANGO_DEBUG=${DJANGO_DEBUG}
CORS_ALLOW_ALL_ORIGINS=${CORS_ALLOW_ALL_ORIGINS}
ALLOWED_HOSTS=${ALLOWED_HOSTS}
DB_NAME=${DB_NAME}
DB_USER=${DB_USER}
DB_PASSWORD=${DB_PASSWORD}
DB_HOST=${DB_HOST}
DB_PORT=${DB_PORT}
EOL

# AWS credentials should be managed through IAM roles, not hardcoded
# Remove any hardcoded AWS credentials

# Set proper permissions for environment file
chmod 600 /var/www/django-app/.env
chown ubuntu:ubuntu /var/www/django-app/.env

# Check database connectivity before proceeding
echo "Checking database connectivity..."
if ! pg_isready -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -t 5; then
    echo "PostgreSQL server is not reachable. Check the database configuration."
    exit 1
fi

# Run migrations
echo "Running database migrations..."
sudo -u ubuntu /var/www/django-app/venv/bin/python manage.py migrate --noinput

# Collect static files
echo "Collecting static files..."
sudo -u ubuntu /var/www/django-app/venv/bin/python manage.py collectstatic --noinput

# Create necessary directories
echo "Creating necessary directories..."
mkdir -p /var/log/django-app
chown -R ubuntu:ubuntu /var/log/django-app

# Configure Nginx
echo "Configuring Nginx..."
cat > /etc/nginx/sites-available/django-app <<EOL
server {
    listen 80;
    listen [::]:80;
    server_name api.homefinder254.com;

    location /static/ {
        alias /var/www/django-app/staticfiles/;
    }

    location /media/ {
        alias /var/www/django-app/media/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOL

# Enable the site
ln -sf /etc/nginx/sites-available/django-app /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Configure Supervisor
echo "Configuring Supervisor..."
mkdir -p /etc/supervisor/conf.d
cat > /etc/supervisor/conf.d/django-app.conf <<EOL
[program:django-app]
command=/var/www/django-app/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:8000 HomeFinderBackend.wsgi:application
directory=/var/www/django-app
user=ubuntu
autostart=true
autorestart=true
stderr_logfile=/var/log/django-app/django-app.err.log
stdout_logfile=/var/log/django-app/django-app.out.log
environment=DJANGO_SETTINGS_MODULE="HomeFinderBackend.settings"
EOL

# Ensure supervisor is running
echo "Starting supervisor..."
if ! command -v supervisord &> /dev/null; then
    apt-get install -y supervisor
fi

# Start/restart supervisor
if ! pgrep -f supervisord > /dev/null; then
    supervisord
else
    echo "Supervisor is already running"
fi

# Reload Supervisor and Nginx
echo "Reloading services..."
supervisorctl reread
supervisorctl update
supervisorctl restart django-app

# Test nginx configuration
nginx -t

# Restart Nginx only if configuration test passed
if [ $? -eq 0 ]; then
    systemctl restart nginx
else
    echo "Nginx configuration test failed"
    exit 1
fi

# Set up SSL after everything else is working
echo "Setting up SSL..."
if command -v certbot &> /dev/null; then
    if nslookup api.homefinder254.com; then
        certbot --nginx \
            -d api.homefinder254.com \
            --non-interactive \
            --agree-tos \
            -m ambeyibrian8@gmail.com \
            --redirect || echo "SSL setup failed, but continuing..."
    else
        echo "Domain api.homefinder254.com is not reachable. Skipping SSL setup."
    fi
else
    echo "Certbot not found, skipping SSL setup"
fi

echo "after_install.sh completed at $(date)"