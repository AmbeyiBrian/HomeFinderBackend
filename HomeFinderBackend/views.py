from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import connections
from django.db.utils import OperationalError
from redis.exceptions import RedisError
from django.conf import settings
from celery.app.control import Control
from django.core.cache import cache
from .alerts import AlertManager
import redis
import psutil
import logging
import os

logger = logging.getLogger(__name__)

class HealthCheckView(APIView):
    """
    Enhanced health check endpoint for the application.
    Includes system metrics and service status checks.
    """
    permission_classes = []
    MEMORY_THRESHOLD = 90  # Alert when memory usage is above 90%
    DISK_THRESHOLD = 85    # Alert when disk usage is above 85%
    CPU_THRESHOLD = 95     # Alert when CPU usage is above 95%

    def get_system_metrics(self):
        """Get system resource metrics"""
        metrics = {
            'cpu_usage': psutil.cpu_percent(interval=1),
            'memory': {
                'total': psutil.virtual_memory().total / (1024 * 1024 * 1024),  # GB
                'used_percent': psutil.virtual_memory().percent
            },
            'disk': {
                'total': psutil.disk_usage('/').total / (1024 * 1024 * 1024),  # GB
                'used_percent': psutil.disk_usage('/').percent
            }
        }

        # Check for resource threshold breaches
        if metrics['memory']['used_percent'] > self.MEMORY_THRESHOLD:
            AlertManager.send_alert(
                'High Memory Usage',
                f"Memory usage is at {metrics['memory']['used_percent']}%",
                'warning',
                'high_memory'
            )

        if metrics['disk']['used_percent'] > self.DISK_THRESHOLD:
            AlertManager.send_alert(
                'High Disk Usage',
                f"Disk usage is at {metrics['disk']['used_percent']}%",
                'warning',
                'high_disk'
            )

        if metrics['cpu_usage'] > self.CPU_THRESHOLD:
            AlertManager.send_alert(
                'High CPU Usage',
                f"CPU usage is at {metrics['cpu_usage']}%",
                'warning',
                'high_cpu'
            )

        return metrics
        # Check Redis connection
        try:
            redis_client = redis.from_url(settings.CELERY_BROKER_URL)
            redis_client.ping()
        except (RedisError, ConnectionError) as e:
            health_status['status'] = 'unhealthy'
            health_status['services']['redis'] = False
            logger.error(f"Redis health check failed: {str(e)}")

        # Check Celery
        if not self.check_celery_status():
            health_status['status'] = 'unhealthy'
            health_status['services']['celery'] = False
            logger.error("Celery health check failed")

        # Add application version if available
        try:
            with open('version.txt', 'r') as f:
                health_status['version'] = f.read().strip()
        except FileNotFoundError:
            health_status['version'] = os.getenv('APP_VERSION', 'unknown')

        # Add uptime information
        health_status['uptime'] = {
            'boot_time': psutil.boot_time(),
            'process_start_time': psutil.Process().create_time()
        }

        status_code = status.HTTP_200_OK if health_status['status'] == 'healthy' else status.HTTP_503_SERVICE_UNAVAILABLE
        return Response(health_status, status=status_code)