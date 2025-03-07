import os
from celery.schedules import crontab
from kombu import Exchange, Queue

# Broker Settings
broker_url = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
result_backend = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')

# Concurrency Settings
worker_concurrency = int(os.getenv('CELERY_WORKER_CONCURRENCY', '4'))
worker_prefetch_multiplier = 1  # One task per worker at a time
worker_max_tasks_per_child = 1000  # Restart worker after 1000 tasks

# Task Settings
task_serializer = 'json'
result_serializer = 'json'
accept_content = ['json']
timezone = 'Africa/Nairobi'
enable_utc = True

# Security Settings
task_create_missing_queues = True
task_default_queue = 'default'
task_queues = (
    Queue('default', Exchange('default'), routing_key='default'),
    Queue('payments', Exchange('payments'), routing_key='payments'),
    Queue('cleanup', Exchange('cleanup'), routing_key='cleanup'),
)

task_routes = {
    'payments.*': {'queue': 'payments'},
    'cleanup.*': {'queue': 'cleanup'},
}

# Error Handling
task_acks_late = True  # Tasks are acknowledged after completion
task_reject_on_worker_lost = True  # Reject tasks if worker is killed
task_default_rate_limit = '10/m'  # Default rate limit per task

# Task Result Settings
result_expires = 60 * 60 * 24  # Results expire after 24 hours
task_ignore_result = True  # Ignore results by default unless explicitly needed

# Logging Settings
worker_hijack_root_logger = False
worker_log_format = '[%(asctime)s: %(levelname)s/%(processName)s] %(message)s'
worker_task_log_format = '[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s] %(message)s'

# Monitor Settings
worker_send_task_events = True
task_send_sent_event = True

# Retry Settings
task_default_retry_delay = 180  # 3 minutes
task_max_retries = 3

# Schedule Settings
beat_schedule = {
    'verify-pending-transactions': {
        'task': 'payments.tasks.verify_pending_transactions',
        'schedule': crontab(minute='*/2'),  # Every 2 minutes
        'options': {'queue': 'payments'}
    },
    'cleanup-old-transactions': {
        'task': 'payments.tasks.cleanup_old_pending_transactions',
        'schedule': crontab(minute=0, hour='*/1'),  # Every hour
        'options': {'queue': 'cleanup'}
    },
}

# SSL/TLS Settings for Redis (if using SSL)
if broker_url.startswith('rediss://'):
    broker_use_ssl = {
        'ssl_cert_reqs': os.getenv('REDIS_SSL_CERT_REQS', 'CERT_REQUIRED'),
        'ssl_ca_certs': os.getenv('REDIS_CA_CERTS_PATH'),
        'ssl_certfile': os.getenv('REDIS_CERT_FILE'),
        'ssl_keyfile': os.getenv('REDIS_KEY_FILE'),
    }
    redis_backend_use_ssl = broker_use_ssl