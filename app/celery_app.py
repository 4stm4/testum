"""Celery application factory."""
from celery import Celery
from app.config import config

# Create Celery app
celery_app = Celery(
    "ocultum",
    broker=config.CELERY_BROKER_URL,
    backend=config.CELERY_RESULT_BACKEND,
    include=["app.tasks"],
)

# Configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour hard limit
    task_soft_time_limit=3300,  # 55 minutes soft limit
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
)

# Auto-retry configuration
celery_app.conf.task_routes = {
    "app.tasks.*": {"queue": "default"},
}
