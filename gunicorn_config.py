import threading
import os
from monitor import start_monitoring

def on_starting(server):
    """
    Called just before the master process is initialized.
    This is the perfect place to start background threads.
    """
    print("🚀 Starting background monitor...")
    monitor_thread = threading.Thread(target=start_monitoring, daemon=True)
    monitor_thread.start()
    print("✅ Monitor thread started successfully!")

# Gunicorn configuration
bind = f"0.0.0.0:{os.environ.get('PORT', 5000)}"
workers = 1
worker_class = "sync"
timeout = 120
