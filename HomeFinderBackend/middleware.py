import time
import logging
from django.conf import settings

logger = logging.getLogger('api.monitoring')

class APIMonitoringMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Start timer
        start_time = time.time()

        # Process request
        response = self.get_response(request)

        # Skip non-API requests
        if not request.path.startswith('/api/'):
            return response

        # Calculate duration
        duration = time.time() - start_time

        # Log request details
        log_data = {
            'path': request.path,
            'method': request.method,
            'status_code': response.status_code,
            'duration': round(duration * 1000, 2),  # Convert to milliseconds
            'user': request.user.email if request.user.is_authenticated else 'anonymous'
        }

        # Log slow requests (over 1 second)
        if duration > 1:
            logger.warning(f'Slow API request: {log_data}')
        else:
            logger.info(f'API request: {log_data}')

        # Add performance header in debug mode
        if settings.DEBUG:
            response['X-Response-Time'] = f"{round(duration * 1000, 2)}ms"

        return response

    def process_exception(self, request, exception):
        # Log unhandled exceptions
        logger.error(f'Unhandled exception in {request.path}: {str(exception)}', 
                    exc_info=True,
                    extra={
                        'path': request.path,
                        'method': request.method,
                        'user': request.user.email if request.user.is_authenticated else 'anonymous'
                    })
        return None