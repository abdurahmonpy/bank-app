import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

app = Celery("core")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# Periodic Telegram stats report
app.conf.beat_schedule = {
    "send-periodic-telegram-report-hourly": {
        "task": "app.tasks.send_periodic_telegram_report",
        "schedule": crontab(minute=0),
    },
}


@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
