import multiprocessing
import os

# Server socket
bind = '127.0.0.1:8000'
backlog = 2048

# Worker processes - (2 x num_cores) + 1
workers = multiprocessing.cpu_count() * 2 + 1
threads = 2
worker_class = 'sync'
worker_connections = 1000
timeout = 120  # Increased for long-running processes
keepalive = 5

# Process naming
proc_name = 'homefinder_gunicorn'
pythonpath = '.'

# Logging
accesslog = '/var/log/django-app/gunicorn-access.log'
errorlog = '/var/log/django-app/gunicorn-error.log'
loglevel = 'info'
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(L)s'

# Process management
daemon = False
pidfile = '/var/run/gunicorn/homefinder.pid'
umask = 0
user = None
group = None
tmp_upload_dir = None

# Server mechanics
preload_app = True
max_requests = 1000
max_requests_jitter = 50
graceful_timeout = 30
keepalive = 5

# SSL - Configure in reverse proxy instead
keyfile = None
certfile = None

# Server hooks
def on_starting(server):
    """Log when server starts"""
    server.log.info("Starting Gunicorn server for HomeFinder")

def on_reload(server):
    """Log when server reloads"""
    server.log.info("Reloading HomeFinder server")

def pre_fork(server, worker):
    """Pre-fork handler"""
    pass

def post_fork(server, worker):
    """Post-fork handler"""
    server.log.info(f"Worker spawned (pid: {worker.pid})")

def pre_exec(server):
    """Pre-exec handler"""
    server.log.info("Forked child, re-executing.")

def when_ready(server):
    """When server is ready to accept connections"""
    server.log.info("Server is ready. Spawning workers")

def worker_int(worker):
    """Worker received INT or QUIT signal"""
    worker.log.info(f"Worker received INT or QUIT signal (pid: {worker.pid})")

def worker_abort(worker):
    """Worker received SIGABRT signal"""
    worker.log.info(f"Worker received ABORT signal (pid: {worker.pid})")

def worker_exit(server, worker):
    """Clean up after worker exits"""
    server.log.info(f"Worker exited (pid: {worker.pid})")

# Secure headers
secure_scheme_headers = {
    'X-FORWARDED-PROTOCOL': 'ssl',
    'X-FORWARDED-PROTO': 'https',
    'X-FORWARDED-SSL': 'on'
}