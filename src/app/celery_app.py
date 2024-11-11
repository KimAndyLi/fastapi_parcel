from celery import Celery
import os

celery = Celery(
    __name__,
    broker=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0"),
)

# Загружаем конфигурацию и указываем на модуль с задачами
celery.config_from_object("app.celery_config")
celery.autodiscover_tasks(["app.tasks"])
