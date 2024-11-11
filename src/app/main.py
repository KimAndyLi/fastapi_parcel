from fastapi import FastAPI, Request, Form, HTTPException, Response, Query, Path, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from app.models import ParcelRegistrationRequest, parcel, parceltype, metadata
from uuid import uuid4
from sqlalchemy import create_engine, select, insert
from sqlalchemy_utils import database_exists, create_database
from app.celery_app import celery
from sqlalchemy import update
from app.utils import redis_client
from decimal import Decimal
from app.db.dbconfig import DATABASE_URL, database
import requests


app = FastAPI()

templates = Jinja2Templates(directory="templates")


# Эндпоинт для получения всех типов посылок
@app.on_event("startup")
async def startup():
    # Ensure database connection
    if not database.is_connected:
        await database.connect()

    engine = create_engine(DATABASE_URL)

    # Create database if it does not exist
    if not database_exists(engine.url):
        create_database(engine.url)

    # Create tables if they do not exist
    metadata.create_all(engine)

    # Insert default data into ParcelType if it is empty
    query = select(parceltype.c.id)
    result = await database.fetch_all(query)
    if not result:  # If ParcelType table is empty
        parcel_types = [
            {"id": 1, "name": "Clothes"},
            {"id": 2, "name": "Electronics"},
            {"id": 3, "name": "Others"}
        ]
        query = insert(parceltype)
        await database.execute_many(query, parcel_types)


@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()


@app.get("/", response_class=HTMLResponse)
@app.get("/entry", response_class=HTMLResponse)
async def entry_page(request: Request):
    """
    Гланая страница с формой заполнения
    """
    return templates.TemplateResponse(
        request=request, name="entry.html")


@app.post('/reg_parcel', response_class=JSONResponse)
async def reg_parcel(
    request: Request,
    response: Response,
    name: str = Form(...),
    weight: float = Form(...),
    type_id: int = Form(...),
    value: float = Form(...),
):
    """
    Регистрирует новую посылку с заданными параметрами.
    - **name**: название посылки
    - **weight**: вес посылки в килограммах
    - **type_id**: ID типа посылки
    - **value**: стоимость содержимого посылки
    """
    try:
        parcel_data = ParcelRegistrationRequest(
            name=name,
            weight=weight,
            type_id=type_id,
            value=value
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Генерация уникального ID для посылки
    parcel_id = str(uuid4())

    # Получение текущей сессии или создание новой
    session_cookie = request.cookies.get("session_id")
    if not session_cookie:
        session_id = str(uuid4())
        response.set_cookie(key="session_id", value=session_id)
    else:
        session_id = session_cookie

    # Сохранение данных посылки в базе данных с session_id
    query = insert(parcel).values(
        parcel_id=parcel_id,
        name=parcel_data.name,
        weight=parcel_data.weight,
        type_id=parcel_data.type_id,
        value=parcel_data.value,
        delivery_cost=None,  # Пока стоимость доставки не рассчитана
        session_id=session_id  # Сохранение session_id для фильтрации
    )
    await database.execute(query)

    # Возвращаем ID посылки для текущей сессии и id сессии
    return {"message": "Parcel registered successfully", "parcel_id": parcel_id, "session_id": session_id}


@app.get("/parcel-types")
async def get_parcel_types():
    """
    Типы посылок
    """
    query = select(parceltype.c.id, parceltype.c.name)
    results = await database.fetch_all(query)
    if not results:
        raise HTTPException(status_code=404, detail="No parcel types found")
    return [{"id": result["id"], "name": result["name"]} for result in results]


@app.get("/parcels")
async def get_parcels(
    request: Request,
    page: int = Query(1, description="Номер страницы"),
    page_size: int = Query(10, description="Размер страницы"),
    type_id: int = Query(None, description="Фильтр по типу посылки"),
    has_delivery_cost: bool = Query(None, description="Фильтр по наличию рассчитанной стоимости доставки"),
    min_weight: float = Query(None, description="Минимальный вес посылки"),
    max_weight: float = Query(None, description="Максимальный вес посылки"),
    min_value: float = Query(None, description="Минимальная стоимость содержимого"),
    max_value: float = Query(None, description="Максимальная стоимость содержимого")
):

    """
    Возвращает список посылок с фильтрацией и пагинацией.

    - **page**: номер страницы
    - **page_size**: количество элементов на странице
    - **type_id**: фильтр по типу посылки
    - **has_delivery_cost**: фильтр по наличию рассчитанной стоимости доставки
    """

    # Извлечение session_id из куков
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(status_code=403, detail="Session ID not found in cookies")

    # Фильтрация по session_id
    query = parcel.select().where(parcel.c.session_id == session_id)

    # Дополнительные фильтры, как ранее
    if type_id is not None:
        query = query.where(parcel.c.type_id == type_id)
    if has_delivery_cost is not None:
        query = query.where(parcel.c.delivery_cost.isnot(None) if has_delivery_cost else parcel.c.delivery_cost.is_(None))
    if min_weight is not None:
        query = query.where(parcel.c.weight >= min_weight)
    if max_weight is not None:
        query = query.where(parcel.c.weight <= max_weight)
    if min_value is not None:
        query = query.where(parcel.c.value >= min_value)
    if max_value is not None:
        query = query.where(parcel.c.value <= max_value)

    # Пагинация
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    # Выполнение запроса и формирование ответа
    results = await database.fetch_all(query)
    return [
        {
            "id": result["id"],
            "name": result["name"],
            "weight": result["weight"],
            "type_id": result["type_id"],
            "value": result["value"],
            "delivery_cost": result["delivery_cost"] if result["delivery_cost"] else "Не рассчитано"
        }
        for result in results
    ]


@app.get("/parcel/{parcel_id}")
async def get_parcel(parcel_id: str = Path(..., description="Уникальный ID посылки")):
    """
    Поиск информации о посылке по ее ID
    """
    # Запрос к базе данных для получения информации о посылке
    query = parcel.select().where(parcel.c.parcel_id == parcel_id)
    result = await database.fetch_one(query)

    # Проверка, что посылка найдена
    if result is None:
        raise HTTPException(status_code=404, detail="Parcel not found")

    # Формирование ответа
    return {
        "id": result["id"],
        "parcel_id": result["parcel_id"],
        "name": result["name"],
        "weight": result["weight"],
        "type_id": result["type_id"],
        "value": result["value"],
        "delivery_cost": result["delivery_cost"] if result["delivery_cost"] else "Не рассчитано"
    }


# Функция для получения курса доллара
def get_usd_to_rub_exchange_rate():
    cached_rate = redis_client.get("usd_to_rub")
    if cached_rate:
        return float(cached_rate)

    response = requests.get("https://www.cbr-xml-daily.ru/daily_json.js")
    data = response.json()
    usd_to_rub = data["Valute"]["USD"]["Value"]

    # Кэшируем курс на 5 минут
    redis_client.setex("usd_to_rub", 300, usd_to_rub)
    return usd_to_rub


# Асинхронная функция для расчета стоимости доставки
async def calculate_delivery_cost_async():
    # Подключаемся к базе данных, если это необходимо
    if not database.is_connected:
        await database.connect()

    usd_to_rub = Decimal(get_usd_to_rub_exchange_rate())  # Приводим курс к Decimal
    query = parcel.select().where(parcel.c.delivery_cost.is_(None))
    parcels = await database.fetch_all(query)

    for p in parcels:
        weight = Decimal(p["weight"])  # Приводим к Decimal
        value = Decimal(p["value"])  # Приводим к Decimal
        delivery_cost = (weight * Decimal('0.5') + value * Decimal('0.01')) * usd_to_rub

        # Обновляем стоимость доставки
        update_query = (
            update(parcel)
            .where(parcel.c.id == p["id"])
            .values(delivery_cost=delivery_cost)
        )
        await database.execute(update_query)

    # Отключаемся от базы данных после выполнения
    await database.disconnect()


# Предполагая, что Celery поддерживает асинхронные задачи
@celery.task(name="calculate_delivery_cost")
async def calculate_delivery_cost():
    await calculate_delivery_cost_async()


# Эндпоинт для ручного запуска задачи расчета стоимости доставки
@app.get("/trigger-delivery-cost-calculation")
async def trigger_delivery_cost_calculation(background_tasks: BackgroundTasks):
    background_tasks.add_task(calculate_delivery_cost_async)
    return {"message": "Delivery cost calculation triggered."}