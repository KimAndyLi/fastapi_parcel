from pydantic import BaseModel, Field, condecimal, constr
from sqlalchemy import MetaData, Table, Column, Integer, String


class ParcelRegistrationRequest(BaseModel):
    name: constr(min_length=1, max_length=100) = Field(..., description="Название посылки")
    weight: condecimal(gt=0) = Field(..., description="Вес посылки в килограммах")
    type_id: int = Field(..., description="ID типа посылки (1 - одежда, 2 - электроника, 3 - разное)")
    value: condecimal(ge=0) = Field(..., description="Стоимость содержимого в долларах")


metadata = MetaData()

# Определение таблицы ParcelType
parceltype = Table(
    "ParcelType",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String(50)),
)

# Определение таблицы Parcel
parcel = Table(
    "Parcel",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("parcel_id", String(36), nullable=False, unique=True),  # Уникальный ID посылки
    Column("name", String(100), nullable=False),
    Column("weight", Integer, nullable=False),
    Column("type_id", Integer, nullable=False),
    Column("value", Integer, nullable=False),
    Column("delivery_cost", Integer, nullable=True),
    Column("session_id", String(36), nullable=False)  # Новый столбец session_id
)
