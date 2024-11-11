import os
from itsdangerous import URLSafeSerializer
from databases import Database

DATABASE_URL = os.getenv("DATABASE_URL", "mysql+mysqlconnector://parcel:parcelpasswd@db/parceldb")

SECRET_KEY = "secretkey"  # Замените на более безопасный ключ
serializer = URLSafeSerializer(SECRET_KEY)

# Подключение к базе данных MySQL
database = Database(DATABASE_URL)