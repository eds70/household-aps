# DOCKER.md

Устройство Docker-инфраструктуры APS Production Scheduler.

## Связанные файлы

- [README.md](../README.md) — основная документация.
- [DEPLOYMENT.md](DEPLOYMENT.md) — пошаговое развёртывание в облаке.
- [CONFIGURATION.md](CONFIGURATION.md) — переменные окружения.
- [OPERATIONS.md](OPERATIONS.md) — операции с БД.
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — решение проблем.

---

## Обзор

Проект использует **два** compose-файла:

| Файл | Назначение | Что поднимает | Где лежит |
|------|------------|---------------|-----------|
| `docker/docker-compose.yml` | **Dev** | Только PostgreSQL | `docker/` |
| `docker-compose.prod.yml` | **Prod** | PostgreSQL + backend + frontend + nginx | корень |

**Правило выбора:**
- **Разработка локально** → `docker/docker-compose.yml` (backend и frontend — на хосте, hot-reload).
- **Облако / тест пользователем** → `docker-compose.prod.yml` (всё в Docker, единственный вход через nginx).

---

## Архитектура Prod (4 сервиса)

```
┌─────────────────────────────────────────────────────────┐
│  Хост (Ubuntu 22.04 LTS, 2 vCPU, 4 GB RAM)              │
│                                                          │
│  ┌─────────────────────────────────────────────────┐    │
│  │  Docker-сеть: aps_network (bridge)              │    │
│  │                                                  │    │
│  │  ┌───────────────────┐                          │    │
│  │  │  aps_nginx        │  ← ЕДИНСТВЕННЫЙ ВХОД   │    │
│  │  │  nginx:alpine     │    порты 80, 443         │    │
│  │  │  :80 :443         │                          │    │
│  │  └────┬──────────┬───┘                          │    │
│  │       │          │                              │    │
│  │       │ /api/*   │ /                            │    │
│  │       │          │                              │    │
│  │       ▼          ▼                              │    │
│  │  ┌─────────┐  ┌──────────────┐                 │    │
│  │  │ backend │  │  frontend    │                 │    │
│  │  │ :8000   │  │  :80         │                 │    │
│  │  │ FastAPI │  │  nginx+SPA   │                 │    │
│  │  └────┬────┘  └──────────────┘                 │    │
│  │       │                                         │    │
│  │       ▼                                         │    │
│  │  ┌──────────────┐                              │    │
│  │  │  postgres    │                              │    │
│  │  │  :5432       │  ← порт НЕ пробрасывается   │    │
│  │  │  volume:     │    (только внутренняя сеть) │    │
│  │  │  pgdata      │                              │    │
│  │  └──────────────┘                              │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

### Таблица сервисов

| Сервис | Образ | Порт (host) | Порт (внутри) | Объём | Особенности |
|--------|-------|-------------|---------------|-------|-------------|
| `postgres` | `postgres:17` | ❌ не пробрасывается | `5432` | ~100 MB | Volume `pgdata`, healthcheck `pg_isready` |
| `backend` | собственный (`backend/Dockerfile`) | ❌ не пробрасывается | `8000` | ~450 MB | `--workers 2`, без reload, OR-Tools |
| `frontend` | собственный (`frontend/Dockerfile`) | ❌ не пробрасывается | `80` | ~50 MB | Multi-stage: Node build → nginx:alpine |
| `nginx` | `nginx:alpine` | **80, 443** | `80, 443` | ~40 MB | Reverse-proxy, единственная точка входа |

**Ключевые решения:**

- **Только nginx** пробрасывает порты наружу. Остальные — во внутренней сети `aps_network`.
- **PostgreSQL недоступен из интернета.** Это критично для безопасности.
- **Backend использует `--workers 2`** — утилизация 2-vCPU VM. При проблемах с connection pool — см. [TROUBLESHOOTING.md](TROUBLESHOOTING.md) п. 129.
- **Frontend — отдельный сервис** (не через backend). Это позволяет перезапускать frontend без backend и наоборот.

### Зависимости

```
postgres (healthcheck) ──┐
                          ▼
                     backend (depends_on: healthy)
                          │
frontend ────────────────┤
                          ▼
                     nginx (depends_on: backend, frontend)
```

- `backend` ждёт `postgres` (healthcheck `pg_isready`) → не стартует до готовности БД.
- `nginx` ждёт `backend` + `frontend` → не маршрутизирует до готовности.
- `frontend` **не зависит** от backend (статика готова сразу).

---

## Устройство `backend/Dockerfile`

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Системные зависимости (компилятор для C-расширений, libpq, curl для healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq-dev curl postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Python-зависимости (кэшируются отдельно)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Код (только после pip install — сохраняем кэш при изменениях кода)
COPY . .

# Non-root user
RUN useradd -m -u 1000 app && chown -R app:app /app
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "run_server.py"]
```

**Ключевые решения:**

| Решение | Почему |
|---------|--------|
| `python:3.12-slim`, не `alpine` | На `alpine` (musl libc) часть пакетов (OR-Tools, asyncpg) требует пересборки. Slim — ставится из wheels, быстро. Разница ~100 MB — не критична. |
| `--no-install-recommends` + `rm -rf /var/lib/apt/lists/*` | Экономия ~150 MB. Без этих приёмов образ — ~700 MB вместо ~450 MB. |
| `COPY requirements.txt` **до** `COPY . .` | Кэш слоя pip install. При изменении кода — пересобирается только слой с кодом (2 сек), не pip (2 мин). |
| `USER app` (uid 1000) | Non-root. Стандартный UID 1000 упрощает работу с volumes на хосте. |
| `start_period: 60s` | Backend грузит OR-Tools + модель → холодный старт 20–40 сек. |
| `CMD ["python", "run_server.py"]` | Dev-дефолт (uvicorn с `--reload`). В prod-overlay переопределяется через `command:`. |

**Что попадает в образ:**
- ✅ `app/` — код.
- ✅ `migrations/` — для отладки.
- ✅ `scripts/create_admin_user.py` — нужен в облаке.
- ✅ `init_schema_v4.9.sql`, `init_schema_v4.9_seed.sql`, `seed_demo_data.sql`.
- ❌ `.env` — исключён через `.dockerignore`.
- ❌ `.venv/` — исключён.
- ❌ `tests/` — исключён.
- ❌ `*.md` — исключены.

**Переопределение в prod:**

В `docker-compose.prod.yml`:
```yaml
backend:
  command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
```

Это **заменяет** `CMD` из Dockerfile. `run_server.py` (с `reload=True`) используется только в dev.

---

## Устройство `frontend/Dockerfile`

Multi-stage build:

### Stage 1: builder

```dockerfile
FROM node:20-alpine AS builder

WORKDIR /app

# Build-arg для VITE_API_URL (вшивается в бандл)
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=${VITE_API_URL}

# Зависимости (кэшируются отдельно)
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

# Код + сборка
COPY . .
RUN npm run build
# Результат: /app/dist/
```

### Stage 2: runtime

```dockerfile
FROM nginx:alpine

# Внутренний конфиг (SPA-fallback, кэширование /assets/)
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Статика из builder
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
```

**Ключевые решения:**

| Решение | Почему |
|---------|--------|
| **Multi-stage** | Финальный образ ~50 MB (только nginx + статика). Если бы оставили Node — было бы ~250 MB. |
| `node:20-alpine` | Быстрая установка, поддерживает musl-сборки Vite/Rollup. |
| `npm ci`, не `npm install` | Детерминированная установка по `package-lock.json`. |
| `ARG VITE_API_URL` + `ENV` | Vite вшивает `import.meta.env.VITE_*` **при сборке**. После сборки изменить нельзя. |
| `nginx:alpine` в runtime | 40 MB + 2–5 MB статики. |
| `HEALTHCHECK` через `wget` | В `nginx:alpine` нет curl, но есть busybox `wget`. |

**Что НЕ попадает в образ:**
- ❌ `node_modules/` (исключён `.dockerignore` — критично, иначе скопируется Windows-версия).
- ❌ `src/`, `public/`, `vite.config.ts` — только `dist/`.
- ❌ `Dockerfile`, `.dockerignore`, `.git/`.

**Проверка, что VITE_API_URL вшит:**

```bash
docker compose -f docker-compose.prod.yml exec frontend \
    grep -r "your-domain.com" /usr/share/nginx/html/assets/ | head -3
```

**Важно:** после изменения `VITE_API_URL` — **обязательно пересобрать frontend**:
```bash
docker compose -f docker-compose.prod.yml build --no-cache frontend
docker compose -f docker-compose.prod.yml up -d frontend
```

---

## Два nginx-конфига

В проекте **два** nginx. Не путать:

### 1. Внутренний: `frontend/nginx.conf`

- Где работает: **внутри контейнера `aps_frontend`**.
- Что делает: отдаёт SPA-статику из `/usr/share/nginx/html`.
- Слушает: `:80`.
- **Не проксирует API.** Только статика.

**Ключевые блоки:**

```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    # Vite-ассеты с хэшами → кэш на год
    location /assets/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
        try_files $uri =404;  # не fallback на index.html
    }

    # index.html не кэшируется — чтобы при деплое сразу новая версия
    location = /index.html {
        add_header Cache-Control "no-cache, no-store, must-revalidate";
    }

    # SPA-fallback для клиентского роутинга (/audit, /help/:slug)
    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

**Почему важно:** без `try_files ... /index.html` пользователь при F5 на `/audit` получит 404.

**Почему `/assets/*` → `=404` (не fallback):** если файла нет, отдаём чистый 404. Fallback на index.html → браузер распарсит HTML как JS → `Unexpected token <`.

### 2. Внешний: `nginx/nginx.conf`

- Где работает: **в контейнере `aps_nginx`** (в корне проекта).
- Что делает: reverse-proxy — маршрутизация между backend и frontend.
- Слушает: `:80` (и `:443` после настройки HTTPS).
- Единственная точка входа из интернета.

**Ключевые upstream:**

```nginx
upstream aps_backend {
    server backend:8000;   # имя сервиса из compose
    keepalive 32;
}
upstream aps_frontend {
    server frontend:80;
    keepalive 32;
}
```

**Маршрутизация:**

```nginx
location /api/ {
    proxy_pass http://aps_backend;
    proxy_read_timeout 900s;   # solver может работать долго
    proxy_send_timeout 900s;
}
location /docs { proxy_pass http://aps_backend; }
location /redoc { proxy_pass http://aps_backend; }
location /openapi.json { proxy_pass http://aps_backend; }
location = /health { proxy_pass http://aps_backend; }

location / {
    proxy_pass http://aps_frontend;
}
```

**Прокси-заголовки** (критичны):

```nginx
proxy_set_header Host $host;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
```

Backend по `X-Real-IP` видит **реальный IP клиента** (не `172.20.0.x` из Docker-сети). `X-Forwarded-Proto` — важен для корректной работы Swagger за HTTPS.

**WebSocket-ready** (для будущего SSE/WebSocket):

```nginx
map $http_upgrade $connection_upgrade {
    default upgrade;
    ''      close;
}
# в location /api/:
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection $connection_upgrade;
```

**HTTPS-заготовка** (закомментирована в `nginx/nginx.conf`):
- Второй server-block на `:443` с `ssl_certificate`.
- Раскомментировать после получения сертификата через certbot.
- См. [DEPLOYMENT.md](DEPLOYMENT.md), шаг 10.

**Ссылки между конфигами:**
- Внешний nginx (`:80/:443` на хосте) → проксирует `/` на `aps_frontend` → **внутренний** nginx (`:80` в контейнере) отдаёт SPA.
- Двойной nginx даёт разделение: внешний — маршрутизация и TLS, внутренний — отдача статики.

---

## Volumes и данные

### Volume `pgdata`

Единственный **персистентный** volume. Хранит:
- Таблицы БД.
- Индексы.
- WAL-логи.

```bash
# Где лежит (путь на хосте)
docker volume inspect household-aps_pgdata
```

**⚠️ Критично:**
- НЕ использовать `docker compose -f docker-compose.prod.yml down -v` — **удалит volume**, потеряете БД.
- Правильная остановка: `docker compose -f docker-compose.prod.yml down` (без `-v`).

**Размер:**
- Пустая схема (init_schema_v4.9.sql): ~40 MB.
- Демо-данные + снапшоты: ~100–150 MB.
- Рост: ~1–5 MB/месяц при активном планировании.

**Бэкап volume (сырой tar):**

```bash
docker run --rm -v household-aps_pgdata:/data -v $(pwd):/backup \
    alpine tar czf /backup/pgdata_$(date +%Y%m%d).tar.gz -C /data .
```

**Правильный бэкап — через `pg_dump` (см. DEPLOYMENT.md, шаг 11).**

### Данные вне volume

- **Статика frontend** — внутри образа, пересобирается при деплое.
- **Логи nginx/backend** — в stdout/stderr, ограничены `logging: max-size`.
- **Сертификаты HTTPS** — в `nginx/certs/` на хосте (bind mount).

---

## Отладка внутри контейнеров

### Backend (FastAPI)

**Проверить логи:**
```bash
docker compose -f docker-compose.prod.yml logs backend --tail=100 -f
```

**Зайти внутрь (shell):**
```bash
docker compose -f docker-compose.prod.yml exec backend bash
```

**Проверить переменные окружения:**
```bash
docker compose -f docker-compose.prod.yml exec backend env | sort
```

**Проверить, что Python-импорты работают:**
```bash
docker compose -f docker-compose.prod.yml exec backend python -c "
from app.main import app
print('OK:', app.title)
"
```

**Проверить, что миграция применена (с точки зрения backend'а):**
```bash
docker compose -f docker-compose.prod.yml exec backend python -c "
from app.scheduler.snapshot import snapshot_all_catalogs
print('snapshot module OK')
"
```

**Проверить подключение к БД:**
```bash
docker compose -f docker-compose.prod.yml exec backend python -c "
import asyncio
from app.auth.dependencies import _engine
from sqlalchemy import text

async def check():
    async with _engine.connect() as conn:
        result = await conn.execute(text('SELECT version()'))
        print(result.fetchone())

asyncio.run(check())
"
```

### Frontend (nginx + SPA)

**Проверить, что nginx работает:**
```bash
docker compose -f docker-compose.prod.yml exec frontend \
    nginx -t
# Ожидаемо: syntax is ok / test is successful
```

**Проверить, что dist/ на месте:**
```bash
docker compose -f docker-compose.prod.yml exec frontend \
    ls /usr/share/nginx/html/ | head -10
# Ожидаемо: assets/ favicon.svg index.html
```

**Проверить, что VITE_API_URL вшит:**
```bash
docker compose -f docker-compose.prod.yml exec frontend \
    grep -ro "your-domain.com" /usr/share/nginx/html/assets/ | head -3
```

**Логи nginx (внутренний):**
```bash
docker compose -f docker-compose.prod.yml logs frontend --tail=50
```

### Nginx (reverse-proxy)

**Проверить конфиг:**
```bash
docker compose -f docker-compose.prod.yml exec nginx \
    nginx -t
```

**Перечитать конфиг без restart:**
```bash
docker compose -f docker-compose.prod.yml exec nginx \
    nginx -s reload
```

**Проверить, что nginx видит backend:**
```bash
docker compose -f docker-compose.prod.yml exec nginx \
    wget -qO- http://backend:8000/health
# Ожидаемо: {"status":"healthy","version":"4.9.0",...}
```

**Проверить, что nginx видит frontend:**
```bash
docker compose -f docker-compose.prod.yml exec nginx \
    wget -qO- http://frontend:80/ | head -5
# Ожидаемо: HTML с <div id="root">
```

### PostgreSQL

**Зайти в psql:**
```bash
docker compose -f docker-compose.prod.yml exec postgres psql -U aps -d household
```

**Проверить активные соединения:**
```bash
docker compose -f docker-compose.prod.yml exec postgres psql -U aps -d household -c "
SELECT count(*), state FROM pg_stat_activity GROUP BY state;
"
```

**Проверить долгие запросы (> 10 сек):**
```bash
docker compose -f docker-compose.prod.yml exec postgres psql -U aps -d household -c "
SELECT pid, now() - query_start AS duration, query
FROM pg_stat_activity
WHERE state = 'active' AND now() - query_start > interval '10 seconds';
"
```

---

## Правка конфигов без пересборки

### Nginx (`nginx/nginx.conf`)

Конфиг **монтируется** через bind mount:
```yaml
volumes:
  - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
```

**При изменении:**

```bash
# 1. Проверить синтаксис
docker compose -f docker-compose.prod.yml exec nginx nginx -t

# 2. Перечитать без остановки
docker compose -f docker-compose.prod.yml exec nginx nginx -s reload
```

**Пересборка образа nginx не нужна** — используется `nginx:alpine` из Docker Hub с внешним конфигом.

### Внутренний nginx (`frontend/nginx.conf`)

Этот файл **копируется в образ** при сборке:
```dockerfile
COPY nginx.conf /etc/nginx/conf.d/default.conf
```

**При изменении:**

```bash
docker compose -f docker-compose.prod.yml build frontend
docker compose -f docker-compose.prod.yml up -d frontend
```

### Backend env (`.env`)

Файл `.env` **не копируется в образ**. Переменные пробрасываются через `environment:` из `docker-compose.prod.yml`.

**При изменении `.env`:**

```bash
docker compose -f docker-compose.prod.yml up -d backend
# Docker пересоздаст контейнер с новыми env
```

**Пересборка образа не нужна** — изменения только в env.

**⚠️ Исключение:** `VITE_API_URL` (frontend) вшивается **при сборке**. После изменения — **обязательно** `docker compose build frontend`.

### Frontend code (React/TS)

- **Prod:** код вшивается в образ при `docker compose build frontend`. Правка без пересборки **невозможна**.
- **Dev:** `npm run dev` с hot-reload (Vite).

**Обновление в prod:**
```bash
docker compose -f docker-compose.prod.yml build frontend
docker compose -f docker-compose.prod.yml up -d frontend
```

### Backend code (Python)

- **Prod:** код вшивается в образ. `--workers 2` без reload.
- **Dev:** `uvicorn --reload` (в `run_server.py`).

**Обновление в prod:**
```bash
docker compose -f docker-compose.prod.yml build backend
docker compose -f docker-compose.prod.yml up -d backend
```

---

## Обновление образов

### Пошаговое обновление

```bash
cd household-aps

# 1. Бэкап БД (обязательно!)
~/backup_aps.sh

# 2. Получить изменения
git pull

# 3. Пересобрать образы
docker compose -f docker-compose.prod.yml build

# 4. Применить новые миграции (если есть)
docker compose -f docker-compose.prod.yml cp \
    backend/migrations/add_29.sql postgres:/tmp/
docker compose -f docker-compose.prod.yml exec -T postgres \
    psql -U aps -d household -f /tmp/add_29.sql

# 5. Перезапустить
docker compose -f docker-compose.prod.yml up -d

# 6. Проверить
docker compose -f docker-compose.prod.yml ps
curl.exe http://your-server-ip/health
```

### Zero-downtime (для будущего)

Сейчас **есть downtime 10–30 секунд** — Docker пересоздаёт контейнеры. Для production с SLA нужен Docker Swarm / Kubernetes.

**Компромисс для снижения downtime:**

```bash
# Пересобрать один сервис
docker compose -f docker-compose.prod.yml build backend

# Rolling restart: сначала frontend (нет зависимостей),
# потом backend (nginx перестроит upstream автоматически)
docker compose -f docker-compose.prod.yml up -d --no-deps frontend
docker compose -f docker-compose.prod.yml up -d --no-deps backend
```

`nginx` **не перезапускается**, т.к. использует DNS-имена Docker. При пересоздании backend контейнера nginx автоматически увидит новый.

### Rollback

Если обновление сломало:

```bash
# 1. Восстановить БД из бэкапа
gunzip -c ~/backups/household_YYYYMMDD_HHMMSS.sql.gz | \
    docker compose -f docker-compose.prod.yml exec -T postgres \
    psql -U aps -d household

# 2. Откатить код
git reset --hard HEAD~1

# 3. Пересобрать
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d

# 4. Проверить
curl.exe http://your-server-ip/health
```

---

## Логи, метрики, ресурсы

### Логи

**Логи всех сервисов:**
```bash
docker compose -f docker-compose.prod.yml logs -f
```

**Только backend:**
```bash
docker compose -f docker-compose.prod.yml logs -f backend
```

**Фильтр по ошибкам:**
```bash
docker compose -f docker-compose.prod.yml logs backend | grep -i error
```

**Tail N строк:**
```bash
docker compose -f docker-compose.prod.yml logs --tail=200 backend
```

**Логи nginx access:**
```bash
docker compose -f docker-compose.prod.yml logs nginx
# Формат: 'remote_addr - remote_user [time] "request" status body ... rt=X'
```

### Ресурсы

**Мониторинг CPU/RAM контейнеров:**
```bash
docker stats
```

**Свободное место:**
```bash
df -h
```

**Размер Docker-данных:**
```bash
docker system df -v
```

**Размер volume pgdata:**
```bash
docker system df -v | grep pgdata
```

### Healthchecks

Все сервисы имеют `HEALTHCHECK`:

| Сервис | Команда | Интервал | `start_period` |
|--------|---------|----------|----------------|
| `postgres` | `pg_isready -U aps -d household` | 5s | 20s |
| `backend` | `curl -f http://localhost:8000/health` | 30s | 60s |
| `frontend` | `wget --spider http://localhost/` | 30s | 10s |

**Статус healthcheck:**
```bash
docker inspect aps_backend --format='{{.State.Health.Status}}'
# Ожидаемо: healthy
```

---

## Best practices

### Что менять (безопасно)

| Что | Как | Пересборка? |
|-----|-----|-------------|
| `nginx/nginx.conf` | Редактировать + `docker compose exec nginx nginx -s reload` | ❌ |
| `.env` (prod env) | Редактировать + `docker compose up -d backend` | ❌ |
| Содержимое `docs/` | Прямо в БД через SQL или через `docker compose cp` | ❌ |
| Статьи справки | Через UI (`/help` → «Редактировать», роль ADMIN) | ❌ |

### Что требует пересборки

| Что | Команда |
|-----|---------|
| Backend-код (`app/*.py`) | `docker compose build backend && up -d backend` |
| Backend-зависимости (`requirements.txt`) | `docker compose build backend && up -d backend` |
| Frontend-код (`src/*`) | `docker compose build frontend && up -d frontend` |
| Frontend-зависимости (`package.json`) | `docker compose build frontend && up -d frontend` |
| `VITE_API_URL` (build-arg) | `docker compose build --no-cache frontend && up -d frontend` |
| Внутренний nginx (`frontend/nginx.conf`) | `docker compose build frontend && up -d frontend` |

### Чего НЕ делать

- ❌ **`docker compose -f docker-compose.prod.yml down -v`** — удалит volume `pgdata` (потеря БД).
- ❌ **Пробрасывать `5432:5432` для postgres** — БД будет доступна из интернета.
- ❌ **Менять код в контейнере через `docker exec`** — изменения потеряются при следующем `up -d`.
- ❌ **Запускать `docker compose build` без бэкапа БД** — если новая версия сломает миграцию, откатить нечем.
- ❌ **Использовать `latest` теги образов** — версии фиксированы (`postgres:17`, `node:20-alpine`, `nginx:alpine`).
- ❌ **Хранить секреты в `Dockerfile` или `docker-compose.prod.yml`** — только `.env`.

### Что делать

- ✅ **Бэкап БД перед обновлением** (`~/backup_aps.sh`).
- ✅ **Healthcheck в каждом сервисе** (`depends_on: condition: service_healthy`).
- ✅ **Ограничение логов** (`logging: max-size: 10m, max-file: 3`).
- ✅ **Non-root в контейнерах** (`USER app` в backend; `nginx:alpine` уже non-root).
- ✅ **`restart: unless-stopped`** — сервисы поднимаются после ребута VM.
- ✅ **`.env` в `.gitignore`**, `.env.example` — коммитится.

---

## Ссылки

- [README.md](../README.md) — основная документация.
- [DEPLOYMENT.md](DEPLOYMENT.md) — развёртывание в облаке.
- [CONFIGURATION.md](CONFIGURATION.md) — переменные окружения.
- [OPERATIONS.md](OPERATIONS.md) — операции с БД.
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — решение проблем.
- [ARCHITECTURE.md](ARCHITECTURE.md) — архитектура приложения.

---

*Последнее обновление: 2026-10-07*