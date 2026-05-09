import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("online_taxi_platform")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    "process-repeating-announcements-every-minute": {
        "task": "apps.taxi.tasks.process_repeating_announcements",
        "schedule": crontab(minute="*"),
    }
}
