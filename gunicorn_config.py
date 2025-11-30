# Gunicorn configuration file
# This helps prevent worker timeouts

import multiprocessing

# Server socket
# Railway uses $PORT environment variable, bind is set in command line
# This config file is for worker settings only
backlog = 2048

# Worker processes
workers = 1  # Reduced to 1 for Railway to avoid resource issues
worker_class = "sync"
worker_connections = 1000
timeout = 300  # Increased to 300 seconds (5 minutes) for Railway
keepalive = 5
graceful_timeout = 120  # Time to wait for workers to finish

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Process naming
proc_name = "dorm_finder"

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL (if needed)
keyfile = None
certfile = None

