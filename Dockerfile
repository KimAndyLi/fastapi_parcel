# Установка базового образа Python
FROM python:3.12-slim

# Установка зависимостей для MySQL
RUN apt-get update && apt-get install -y gcc libmariadb-dev && rm -rf /var/lib/apt/lists/*

# Установка Poetry
WORKDIR /app
COPY pyproject.toml poetry.lock ./
#RUN pip install --no-cache-dir poetry && poetry config virtualenvs.create false && poetry install --no-dev
RUN pip install --no-cache-dir poetry && poetry config virtualenvs.create false && poetry install --only main


# Копирование исходного кода
COPY . .

# Переключение в директорию с приложением
WORKDIR /app/src/app

# Запуск приложения
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
