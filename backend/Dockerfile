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
# ОПТИМИЗАЦИЯ (2026-10-11):
#   - multi-stage build: builder (build-essential) + runtime (без apt)
#   - BuildKit cache mount для pip: кэш переживает пересборку
#   - ldd-анализ показал: libpq5, libgomp1 НЕ нужны в runtime
#   - libstdc++/libgcc есть в python:3.12-slim из коробки
#   - HEALTHCHECK на Python (без curl, ~10 MB экономии)
#   - убран PIP_NO_CACHE_DIR (ломал кэш pip)
#
# ТРЕБУЕТ Docker BuildKit (включён по умолчанию в Docker 20.10+).

# syntax=docker/dockerfile:1.6

# ==========================================
# STAGE 1: BUILDER
# ==========================================
FROM python:3.12-slim AS builder

# Единственная системная зависимость: build-essential для компиляции
# C-расширений (если есть wheels — не используется, но на всякий случай).
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копируем ТОЛЬКО requirements.txt — слой пересобирается
# только при изменении зависимостей.
COPY requirements.txt ./

# Устанавливаем в /install, чтобы во второй стадии скопировать
# только готовые пакеты, без pip и компиляторов.
#
# --mount=type=cache,target=/root/.cache/pip — кэш pip переживает
# пересборку. Второй раз OR-Tools (~500 MB) НЕ будет скачиваться.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip && \
    pip install --prefix=/install -r requirements.txt

# ==========================================
# STAGE 2: RUNTIME
# ==========================================
# Минимальный образ: python:3.12-slim + установленные Python-пакеты.
# Без apt install — все .so-зависимости есть в slim или самодостаточны.
FROM python:3.12-slim

LABEL maintainer="APS Production Scheduler" \
      description="Backend: FastAPI + OR-Tools + asyncpg" \
      version="4.9.1"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Копируем установленные пакеты из builder-стадии.
# Никаких gcc, pip, apt — только сами .so и .py.
COPY --from=builder /install /usr/local

# Код приложения — отдельный слой. При правке кода pip-слой НЕ сбрасывается.
COPY . .

RUN useradd -m -u 1000 app \
    && chown -R app:app /app
USER app

EXPOSE 8000

# HEALTHCHECK на Python (curl в runtime не нужен — экономит ~10 MB).
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()" || exit 1

# CMD — DEV-ДЕФОЛТ (переопределяется в docker-compose.prod.yml).
CMD ["python", "run_server.py"]