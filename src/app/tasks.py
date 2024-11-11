from celery import Celery
import asyncio
from app.main import calculate_delivery_cost_async  # Ваш асинхронный код

celery = Celery("app")

@celery.task
def calculate_delivery_cost():
    # Запускаем асинхронную функцию в синхронном контексте
    asyncio.run(calculate_delivery_cost_async())
