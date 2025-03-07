"""
WSGI config for HomeFinderBackend project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/wsgi/
"""

import os
import sys
import logging

from django.core.wsgi import get_wsgi_application

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('wsgi')

try:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'HomeFinderBackend.settings')
    application = get_wsgi_application()
    logger.info('WSGI application initialized successfully')
except Exception as e:
    logger.error(f'Error initializing WSGI application: {str(e)}')
    raise
