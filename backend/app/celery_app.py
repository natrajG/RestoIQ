from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery = Celery("restaurant_platform", broker=settings.redis_url, backend=settings.redis_url, include=["app.tasks"])
celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,
    beat_schedule={
        "integration-jobs": {"task": "app.tasks.process_integration_jobs", "schedule": 15.0},
        "retention-cleanup-daily": {
            "task": "app.tasks.cleanup_expired_recordings",
            "schedule": crontab(hour=3, minute=0),
        },
        "renewal-reminders": {
            "task": "app.tasks.send_renewal_reminders", "schedule": crontab(hour=10, minute=0),
        },
        "weekly-reports": {
            "task": "app.tasks.generate_reports", "args": ["weekly"],
            "schedule": crontab(day_of_week="monday", hour=7, minute=0),
        },
        "monthly-reports": {
            "task": "app.tasks.generate_reports", "args": ["monthly"],
            "schedule": crontab(day_of_month=1, hour=7, minute=0),
        },
    },
)
