#!/bin/bash

# Enable error handling
set -e

# Log all output
exec > >(tee -a /var/log/deploy.log) 2>&1
echo "Starting after_install.sh at $(date)"

# Load environment variables from AWS Parameter Store or .env file
if [ -f .env ]; then
    echo "Loading .env file..."
    set -a
    source .env
    set +a
else
    echo "No .env file found. Using AWS Parameter Store variables."
fi

# Ensure script is run as root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root"
   exit 1
fi

# Ensure application directory exists
mkdir -p /var/www/django-app
cd /var/www/django-app || {
    echo "Failed to change to application directory"
    exit 1
}

# Set correct permissions
echo "Setting correct permissions..."
chown -R ubuntu:ubuntu /var/www/django-app
chmod -R 755 /var/www/django-app

# Create and activate virtual environment
echo "Setting up Python virtual environment..."
sudo -u ubuntu python3.10 -m venv venv || {
    echo "Failed to create virtual environment"
    exit 1
}

# Install Python dependencies with error handling
echo "Installing Python dependencies..."
sudo -u ubuntu /var/www/django-app/venv/bin/pip install --upgrade pip wheel setuptools || {
    echo "Failed to upgrade pip and install basic tools"
    exit 1
}

sudo -u ubuntu /var/www/django-app/venv/bin/pip install -r requirements.txt || {
    echo "Failed to install project dependencies"
    exit 1
}

# Create environment file with error handling
#echo "Setting up environment file..."
#cat > /var/www/django-app/.env <<EOL || {
#    echo "Failed to create .env file"
#    exit 1
#}
#DJANGO_DEBUG=${DJANGO_DEBUG:-False}
#CORS_ALLOW_ALL_ORIGINS=${CORS_ALLOW_ALL_ORIGINS:-False}
#ALLOWED_HOSTS=${ALLOWED_HOSTS:-'.homefinder254.com,localhost,127.0.0.1'}
#DB_NAME=${DB_NAME}
#DB_USER=${DB_USER}
#DB_PASSWORD=${DB_PASSWORD}
#DB_HOST='homefinderdb.c4ukz2wlcu6n.us-east-1.rds.amazonaws.com'
#DB_PORT=${DB_PORT:-5432}
#EOL
# Set proper permissions for environment file
chmod 600 /var/www/django-app/.env
chown ubuntu:ubuntu /var/www/django-app/.env

# Check database connectivity with timeout
echo "Checking database connectivity..."
timeout 30 bash -c 'until pg_isready -h "$DB_HOST" -p "${DB_PORT:-5432}" -U "$DB_USER" -d "$DB_NAME"; do echo "Waiting for database..."; sleep 2; done' || {
    echo "Database connection timeout after 30 seconds"
    exit 1
}

# Run migrations with error handling
echo "Running database migrations..."
sudo -u ubuntu /var/www/django-app/venv/bin/python manage.py migrate --noinput || {
    echo "Database migration failed"
    exit 1
}

# Collect static files with error handling
echo "Collecting static files..."
sudo -u ubuntu /var/www/django-app/venv/bin/python manage.py collectstatic --noinput || {
    echo "Static file collection failed"
    exit 1
}

# Create log directory with proper permissions
echo "Setting up log directory..."
mkdir -p /var/log/django-app
chown -R ubuntu:ubuntu /var/log/django-app
chmod -R 755 /var/log/django-app

# Configure Nginx
echo "Configuring Nginx..."
cat > /etc/nginx/sites-available/django-app <<EOL || {
    echo "Failed to create Nginx configuration"
    exit 1
}
server {
    listen 80;
    listen [::]:80;
    server_name api.homefinder254.com;
    
    client_max_body_size 100M;
    
    location /static/ {
        alias /var/www/django-app/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, no-transform";
    }
    
    location /media/ {
        alias /var/www/django-app/media/;
        expires 7d;
        add_header Cache-Control "public, no-transform";
    }
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 60s;
        proxy_read_timeout 60s;
        proxy_send_timeout 60s;
    }
}
EOL
# Enable the site and remove default
ln -sf /etc/nginx/sites-available/django-app /etc/nginx/sites-enabled/ || {
    echo "Failed to enable Nginx site"
    exit 1
}
rm -f /etc/nginx/sites-enabled/default

# Configure Supervisor with error handling
echo "Configuring Supervisor..."
mkdir -p /etc/supervisor/conf.d
# shellcheck disable=SC1073
cat > /etc/supervisor/conf.d/django-app.conf <<EOL || {
    echo "Failed to create Supervisor configuration"
    exit 1
}
[program:django-app]
command=/var/www/django-app/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:8000 HomeFinderBackend.wsgi:application --config /var/www/django-app/gunicorn_config.py
directory=/var/www/django-app
user=ubuntu
autostart=true
autorestart=true
stderr_logfile=/var/log/django-app/django-app.err.log
stdout_logfile=/var/log/django-app/django-app.out.log
environment=DJANGO_SETTINGS_MODULE="HomeFinderBackend.settings"
EOL
# Start/restart supervisor with error handling
echo "Starting/restarting supervisor..."
if ! command -v supervisord &> /dev/null; then
    apt-get install -y supervisor || {
        echo "Failed to install supervisor"
        exit 1
    }
fi

# Reload Supervisor and Nginx with error handling
echo "Reloading services..."
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

# Test and reload Nginx
echo "Testing Nginx configuration..."
if nginx -t; then
    systemctl restart nginx || {
        echo "Failed to restart Nginx"
        exit 1
    }
else
    echo "Nginx configuration test failed"
    exit 1
fi

# Set up SSL with error handling
echo "Setting up SSL..."
if command -v certbot &> /dev/null; then
    if nslookup api.homefinder254.com &> /dev/null; then
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

echo "after_install.sh completed successfully at $(date)"
