#!/bin/bash
set -e

# Log all output
exec > >(tee -a /var/log/deploy.log) 2>&1
echo "Starting after_install.sh at $(date)"

cd /var/www/django-app

# Create and activate virtual environment
echo "Setting up Python virtual environment..."
python3.10 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Run migrations
echo "Running database migrations..."
python manage.py migrate --noinput

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Configure Nginx
echo "Configuring Nginx..."
cat > /etc/nginx/sites-available/django-app <<EOL
server {
    listen 80;
    server_name _;

    location /staticfiles/ {
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
    }
}
EOL

# Enable the site
ln -sf /etc/nginx/sites-available/django-app /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Configure Supervisor
echo "Configuring Supervisor..."
cat > /etc/supervisor/conf.d/django-app.conf <<EOL
[program:django-app]
command=/var/www/django-app/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:8000 HomeFinderBackend.wsgi:application
directory=/var/www/django-app
user=ubuntu
autostart=true
autorestart=true
stderr_logfile=/var/log/django-app/django-app.err.log
stdout_logfile=/var/log/django-app/django-app.out.log
EOL

# Create environment file
echo "Setting up environment file..."
cat > /var/www/django-app/.env <<EOL
DEBUG=False
ALLOWED_HOSTS=*
DATABASE_URL=postgres://${DB_USERNAME}:${DB_PASSWORD}@${DB_HOST}:5432/${DB_NAME}
SECRET_KEY=${DJANGO_SECRET_KEY}
EOL

echo "after_install.sh completed at $(date)"