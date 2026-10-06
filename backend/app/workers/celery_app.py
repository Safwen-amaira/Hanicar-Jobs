from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "hanicar_jobs",
    broker=settings.redis_url,
    backend=settings.redis_url,
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "source-health-ping": {
            "task": "app.workers.tasks.ping_sources",
            "schedule": crontab(minute="*/30"),
        },
    },
)

celery_app.autodiscover_tasks(["app.workers"])
