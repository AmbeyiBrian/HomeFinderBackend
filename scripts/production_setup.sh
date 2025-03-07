#!/bin/bash
set -e

# Create necessary directories
sudo mkdir -p /var/www/homefinder
sudo mkdir -p /var/log/homefinder
sudo mkdir -p /var/run/homefinder

# Create virtual environment
python -m venv /var/www/homefinder/venv

# Install dependencies
source /var/www/homefinder/venv/bin/activate
pip install -r requirements.txt

# Set up Supervisor config
sudo cp scripts/supervisor/homefinder.conf /etc/supervisor/conf.d/
sudo supervisorctl reread
sudo supervisorctl update

# Set up Nginx config
sudo cp scripts/homefinder.nginx.conf /etc/nginx/sites-available/homefinder
sudo ln -sf /etc/nginx/sites-available/homefinder /etc/nginx/sites-enabled/
sudo nginx -t  # Test configuration
sudo systemctl reload nginx

# Set up systemd service
sudo cp scripts/homefinder.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable homefinder

# Create and set permissions for directories
sudo chown -R www-data:www-data /var/www/homefinder
sudo chown -R www-data:www-data /var/log/homefinder
sudo chown -R www-data:www-data /var/run/homefinder

# Set proper permissions
sudo chmod 755 /var/www/homefinder
sudo chmod 755 /var/log/homefinder
sudo chmod 755 /var/run/homefinder

# Create log files
sudo -u www-data touch /var/log/homefinder/app.log
sudo -u www-data touch /var/log/homefinder/error.log
sudo -u www-data touch /var/log/homefinder/celery_worker.log
sudo -u www-data touch /var/log/homefinder/celery_beat.log

# Copy production environment file
sudo cp .env.production /var/www/homefinder/.env

echo "Installation complete. Please update the .env file with your production settings."
echo "Then start the services with:"
echo "sudo systemctl start homefinder"
echo "sudo supervisorctl start homefinder:*"