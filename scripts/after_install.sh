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

# Install certbot if not already installed
echo "Installing certbot..."
apt-get update
apt-get install -y certbot python3-certbot-nginx

# Configure Nginx
echo "Configuring Nginx..."
cat > /etc/nginx/sites-available/django-app <<EOL
server {
    listen 80;
    listen [::]:80;
    server_name api.homefinder254.com;

    # Redirect all HTTP requests to HTTPS
    return 301 https://\$server_name\$request_uri;
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name api.homefinder254.com;

    # SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:50m;
    ssl_stapling on;
    ssl_stapling_verify on;

    # SSL certificates will be managed by Certbot

    location /static/ {
        alias /var/www/django-app/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, no-transform";
    }

    location /media/ {
        alias /var/www/django-app/media/;
        expires 30d;
        add_header Cache-Control "public, no-transform";
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        # Additional security headers
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
        add_header X-Content-Type-Options nosniff;
        add_header X-Frame-Options DENY;
        add_header X-XSS-Protection "1; mode=block";
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
environment=DJANGO_SETTINGS_MODULE="HomeFinderBackend.settings"
EOL

# Create log directory if it doesn't exist
mkdir -p /var/log/django-app
chown -R ubuntu:ubuntu /var/log/django-app

# Create environment file with updated ALLOWED_HOSTS
echo "Setting up environment file..."
cat > /var/www/django-app/.env <<EOL
DEBUG=False
ALLOWED_HOSTS=api.homefinder254.com,localhost,127.0.0.1
DATABASE_URL=postgres://${DB_USERNAME}:${DB_PASSWORD}@${DB_HOST}:5432/${DB_NAME}
SECRET_KEY=${DJANGO_SECRET_KEY}
CSRF_TRUSTED_ORIGINS=https://api.homefinder254.com
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
EOL

# Set proper permissions
chown -R ubuntu:ubuntu /var/www/django-app

# Obtain SSL certificate
echo "Obtaining SSL certificate..."
certbot --nginx \
    -d api.homefinder254.com \
    --non-interactive \
    --agree-tos \
    -m ambeyibrian8@gmail.com \
    --redirect

# Reload Supervisor and Nginx
echo "Reloading services..."
supervisorctl reread
supervisorctl update
supervisorctl restart django-app
nginx -t && systemctl restart nginx

echo "after_install.sh completed at $(date)"