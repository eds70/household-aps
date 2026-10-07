# backend/Dockerfile
#
# Образ backend: FastAPI + OR-Tools CP-SAT + asyncpg.
#
# Сборка (из корня проекта):
#   docker build -t aps-backend -f backend/Dockerfile backend/
#
# Или через docker-compose.prod.yml:
#   docker compose -f docker-compose.prod.yml build backend
#
# Особенности:
#   - multi-stage не нужен: один слой, но с кэшем pip.
#   - non-root пользователь для безопасности.
#   - CMD можно переопределить через `command:` в compose.

# ==========================================
# БАЗА
# ==========================================
FROM python:3.12-slim

# ==========================================
# МЕТАДАННЫЕ
# ==========================================
LABEL maintainer="APS Production Scheduler" \
      description="Backend: FastAPI + OR-Tools + asyncpg" \
      version="4.9.0"

# ==========================================
# СИСТЕМНЫЕ ПЕРЕМЕННЫЕ
# ==========================================
# PYTHONDONTWRITEBYTECODE — не создавать .pyc (чище контейнер).
# PYTHONUNBUFFERED — вывод в stdout без буферизации (важно для логов).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ==========================================
# РАБОЧАЯ ДИРЕКТОРИЯ
# ==========================================
WORKDIR /app

# ==========================================
# СИСТЕМНЫЕ ЗАВИСИМОСТИ
# ==========================================
# - build-essential: компиляция C-расширений (asyncpg, ortools и др.)
# - libpq-dev: PostgreSQL клиентская библиотека
# - curl: healthcheck в docker-compose
# - postgresql-client: psql для возможной отладки изнутри контейнера
#   (обычно не нужен, но полезно при troubleshooting)
#
# После установки dev-пакеты удаляются — образ меньше.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
        postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# ==========================================
# PYTHON-ЗАВИСИМОСТИ (ОТДЕЛЬНЫМ СЛОЕМ)
# ==========================================
# Копируем только requirements.txt — если код изменится,
# pip install не переустанавливается (кэш Docker).
COPY requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

# ==========================================
# КОД ПРИЛОЖЕНИЯ
# ==========================================
# Копируется всё содержимое backend/, кроме:
#   - .env (не должен попасть в образ)
#   - .venv
#   - __pycache__
#   - tests/
#   - *.md
# Управляется через .dockerignore (см. соседний файл).
COPY . .

# ==========================================
# NON-ROOT ПОЛЬЗОВАТЕЛЬ
# ==========================================
# Создаём пользователя app, даём ему владение /app.
# Процесс uvicorn запускается от app, не от root.
RUN useradd -m -u 1000 app \
    && chown -R app:app /app
USER app

# ==========================================
# ПОРТ
# ==========================================
# Соответствует host="0.0.0.0", port=8000 в run_server.py.
# Наружу не пробрасывается — доступ через nginx-контейнер.
EXPOSE 8000

# ==========================================
# HEALTHCHECK (ВНУТРЕННИЙ)
# ==========================================
# Проверяет /health каждые 30 секунд.
# Дублирует healthcheck из docker-compose.prod.yml, но работает и без compose.
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# ==========================================
# CMD — DEV-ДЕФОЛТ
# ==========================================
# Запускает run_server.py (uvicorn с reload=True — dev-режим).
# В production через docker-compose.prod.yml переопределяется на:
#   command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
CMD ["python", "run_server.py"]