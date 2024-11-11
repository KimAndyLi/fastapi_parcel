# src/app/celery_config.py
from celery.schedules import crontab

beat_schedule = {
    "calculate_delivery_cost_every_minute": {
        "task": "app.tasks.calculate_delivery_cost",
        "schedule": crontab(minute="*"),
    }
}

beat_max_loop_interval = 60
timezone = "UTC"
