# DEPLOYMENT.md

Развёртывание APS Production Scheduler в облаке или на удалённой машине.

## Связанные файлы

- [README.md](../README.md) — основная документация.
- [OPERATIONS.md](OPERATIONS.md) — операции с БД.
- [CONFIGURATION.md](CONFIGURATION.md) — переменные окружения.
- [LICENSE.md](LICENSE.md) — система лицензирования (для вендора и клиента).
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — решение проблем.

**Файлы для развёртывания** (создаются вместе с этим документом):
- `docker-compose.prod.yml` (в корне) — оркестрация сервисов.
- `backend/Dockerfile`, `backend/.dockerignore` — образ backend.
- `frontend/Dockerfile`, `frontend/.dockerignore`, `frontend/nginx.conf` — образ frontend.
- `nginx/nginx.conf` — внешний reverse-proxy.
- `.env.example` (в корне) — шаблон переменных.
- `scripts/deploy_init.sh`, `scripts/deploy_init.ps1` — инициализация БД.
- `backend/init_schema_v4.9.sql`, `backend/init_schema_v4.9_seed.sql` — консолидированная схема.

---

## Архитектура

```
┌─────────────────────────────────────────────┐
│  Облачная VM (Ubuntu 22.04 LTS)             │
│  2 vCPU, 4 GB RAM, 40 GB SSD                │
│                                              │
│  ┌───────────────┐                          │
│  │  Nginx (:80)  │ ← внешний reverse-proxy  │
│  │  (nginx:alpine)│                          │
│  └───────┬───────┘                          │
│          │                                   │
│    ┌─────┴─────┐                            │
│    ▼           ▼                            │
│  ┌──────────┐ ┌──────────────┐              │
│  │ Backend  │ │  Frontend    │              │
│  │ FastAPI  │ │  (nginx:alpine, SPA)       │
│  │ :8000    │ │  :80         │              │
│  └─────┬────┘ └──────────────┘              │
│        │                                     │
│        ▼                                     │
│  ┌──────────────┐                          │
│  │ PostgreSQL 17│                          │
│  │ :5432        │                          │
│  │ volume: pgdata                          │
│  └──────────────┘                          │
│                                              │
│  Всё в Docker Compose                       │
└─────────────────────────────────────────────┘
```

**Особенности:**
- PostgreSQL **не пробрасывает порт** — доступен только backend'у по внутренней Docker-сети.
- Backend и frontend имеют только `expose:` — не видны из интернета.
- Nginx — единственная точка входа.
- Все данные (БД) в Docker-volume `pgdata`.
- `instance_id` (для лицензии) — в Docker-volume `aps_data`.

---

## Требования к VM

### Минимум (для теста 1-2 пользователями)
- **CPU:** 2 vCPU
- **RAM:** 4 GB
- **Диск:** 40 GB SSD
- **ОС:** Ubuntu 22.04 LTS (или 24.04)

⚠️ **Для сборки backend с 1 vCPU нужно 20–30 минут** (OR-Tools тяжёлый). Рекомендуется **минимум 2 vCPU**.

### Рекомендуется (для 5-10 пользователей)
- **CPU:** 4 vCPU
- **RAM:** 8 GB
- **Диск:** 80 GB SSD

### Облачные провайдеры
- **Hetzner Cloud** — CX22 (2×4 GB) — самый дешёвый вариант.
- **Yandex Cloud** — ВМ `standard-v3`.
- **Selectel**, **Timeweb Cloud**, **VK Cloud** — аналогично.
- **AWS** — t3.medium.

---

## ⚠️ PowerShell vs Bash

**Все команды в этом документе написаны для Bash** (Linux, macOS, Git Bash, WSL).
Если вы работаете в **Windows PowerShell** — есть отличия:

| Что | Bash | PowerShell |
|-----|------|------------|
| Перенос строки | `\` в конце | `` ` `` (бэктик) в конце |
| Переменные | `$VAR` | `$env:VAR` или `$VAR` |
| `curl` | настоящий curl | алиас на `Invoke-WebRequest` ⚠️ |
| Настоящий curl в PS | — | `curl.exe` |
| Логические операторы | `&&`, `\|\|` | только в PowerShell 7+; в 5.1 — раздельно |
| Копирование файлов | `cp a b` | `Copy-Item a b` |
| Пути | `/home/user/...` | `C:\Users\...` |

**Рекомендация:** для облачной VM используйте **Linux + Bash**. Для локальной разработки под Windows — PowerShell с `curl.exe` вместо `curl`.

Примеры для PowerShell даны отдельно, где это критично.

---

## Подводные камни

| # | Камень | Решение |
|---|--------|---------|
| 1 | **`init_schema.sql` устарел** — не покрывает Итерации 13.14–16.2 | Использовать `init_schema_v4.9.sql` + `init_schema_v4.9_seed.sql` (см. ниже) |
| 2 | **PostgreSQL доступен из интернета** | НЕ пробрасывать `5432:5432`. Backend общается по внутренней сети |
| 3 | **CORS** | Задать `ALLOWED_ORIGINS` в `.env` — домен/IP облака |
| 4 | **`SECRET_KEY` по умолчанию** | Сгенерировать: `openssl rand -hex 32` |
| 5 | **Frontend стучится на `your-server-ip`** ⚠️ | **Заменить `VITE_API_URL` в `.env`** перед сборкой! Vite вшивает значение в бандл |
| 6 | **PostgreSQL volume** | НЕ использовать `docker compose down -v`. Volume `pgdata` персистентный |
| 7 | **Контейнеры не поднимаются после ребута** | `restart: unless-stopped` (уже в compose) |
| 8 | **Backend стартует раньше БД** | `depends_on: condition: service_healthy` (уже в compose) |
| 9 | **Firewall** | Открыть 22, 80, 443 в Security Group + `ufw` |
| 10 | **Кириллица в SQL** | Только `docker cp` + `psql -f`, не через pipe |
| 11 | **Логи Docker растут** | `logging: max-size: 10m, max-file: 3` (уже в compose) |
| 12 | **HTTPS не настроен** | Let's Encrypt через certbot или Caddy |
| 13 | **`openpyxl` не в образе** | Уже в `requirements.txt` + Dockerfile |
| 14 | **`recharts` не в build** | `npm ci` + `npm run build` в Dockerfile |
| 15 | **`curl` в PowerShell** | Использовать `curl.exe` вместо `curl` |
| 16 | **Обновление `VITE_API_URL` без пересборки** | Vite вшивает в бандл. После изменения — `docker compose build frontend` |
| 17 | **TLS-сертификат истёк** через 3 месяца | Cron + `certbot renew`, или Caddy (автоматически) |
| 18 | **`--workers 2` + asyncpg** | Если проблемы с connection pool — уменьшить до `--workers 1` или настроить `pool_size` |
| 19 | **`LICENSE_VERIFY=false` в проде** ⚠️ | Проверка лицензии отключена → любой может запустить. Для прода — `true` + `LICENSE_KEY` |
| 20 | **`Permission denied: /data/license_instance`** | Volume `aps_data` смонтирован от root. Нужен `backend-init` (уже в compose) или ручной `chown -R 1000:1000` |
| 21 | **После правки `.env` ничего не поменялось** ⚠️ | `docker compose restart` не перечитывает `.env`. Нужен `up -d --force-recreate backend` |
| 22 | **UI: `Objects are not valid as a React child`** | Frontend не пересобран после патчей `api.ts`. `docker compose build frontend` |
| 23 | **Frontend не показывает бейдж лицензии** | Frontend образ устарел. `docker compose build --no-cache frontend` + `up -d --force-recreate frontend nginx` |

---

## Пошаговая инструкция

### Шаг 1. Локально — проверка структуры

Убедиться, что все файлы на месте:

```
household-aps/
├── docker-compose.prod.yml            ← НОВЫЙ
├── .env.example                       ← НОВЫЙ
├── .env                               ← создаётся из .env.example, НЕ коммитить!
├── .gitignore                         ← содержит .env
├── backend/
│   ├── Dockerfile                     ← НОВЫЙ
│   ├── .dockerignore                  ← НОВЫЙ
│   ├── init_schema_v4.9.sql           ← НОВЫЙ
│   ├── init_schema_v4.9_seed.sql      ← НОВЫЙ
│   ├── seed_demo_data.sql
│   ├── requirements.txt
│   └── ...
├── frontend/
│   ├── Dockerfile                     ← НОВЫЙ
│   ├── .dockerignore                  ← НОВЫЙ
│   ├── nginx.conf                     ← НОВЫЙ
│   └── src/config.ts                  ← уже правильный
├── nginx/
│   └── nginx.conf                     ← НОВЫЙ
├── docker/
│   └── docker-compose.yml             ← существующий (dev, только postgres)
└── scripts/
    ├── deploy_init.sh                 ← НОВЫЙ
    └── deploy_init.ps1                ← НОВЫЙ
```

**Проверить `.gitignore`:**
```bash
git check-ignore .env
# Ожидаемо: .env
```

Если пусто — добавить в `.gitignore`:
```
.env
.env.local
backend/.env
```

### Шаг 2. Облако — создание VM

**Через веб-консоль облака:**
- Образ: **Ubuntu 22.04 LTS**.
- SSH-ключ: загрузить публичный ключ (`~/.ssh/id_rsa.pub`).
- **Security Group:** открыть входящие **22, 80, 443**.
- Публичный IP: привязать.

**Проверка SSH:**
```bash
ssh user@your-server-ip
```

### Шаг 3. Облако — установка Docker

```bash
sudo apt update && sudo apt upgrade -y

# Установить Docker
curl -fsSL https://get.docker.com | sudo sh

# Проверить
docker --version
docker compose version

# Добавить пользователя в docker-группу
sudo usermod -aG docker $USER
newgrp docker
```

### Шаг 4. Облако — firewall

```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

**Дополнительно:** проверьте Security Group в облачной консоли.

### Шаг 5. Облако — перенос проекта

**Вариант A — git clone:**
```bash
git clone -b license https://github.com/your-org/household-aps.git
cd household-aps
```

**Вариант B — rsync (с локальной машины):**
```bash
# Локально
rsync -avz \
    --exclude 'node_modules' \
    --exclude '.venv' \
    --exclude '.env' \
    --exclude 'pgdata' \
    --exclude '__pycache__' \
    ./ user@your-server-ip:/home/user/household-aps/
```

**Вариант C — tar + scp:**
```bash
# Локально
tar czf household-aps.tar.gz \
    --exclude=node_modules \
    --exclude=.venv \
    --exclude=pgdata \
    household-aps/

scp household-aps.tar.gz user@your-server-ip:/home/user/

# На сервере
tar xzf household-aps.tar.gz
cd household-aps
```

### Шаг 6. Облако — настройка `.env`

```bash
cd household-aps
cp .env.example .env
nano .env
```

**Обязательно заполнить:**

```bash
# 1. Сгенерировать SECRET_KEY (мин. 32 символа)
openssl rand -hex 32
# Вставить в .env → SECRET_KEY=...

# 2. Придумать сильный POSTGRES_PASSWORD (мин. 16 символов)
openssl rand -base64 24
# Вставить в .env → POSTGRES_PASSWORD=...

# 3. Указать домен/IP облака
ALLOWED_ORIGINS=http://your-server-ip
VITE_API_URL=http://your-server-ip
```

**После HTTPS** — обновить на `https://your-domain.com`.

**⚠️ Не коммитить `.env`!**

### Шаг 6.1. Облако — проверка критичных переменных ⚠️

**Перед сборкой — убедитесь, что все критичные переменные заменились.**

```bash
# Проверить, что нет плейсхолдеров
grep -E "^(POSTGRES_PASSWORD|SECRET_KEY|VITE_API_URL|ALLOWED_ORIGINS)=" .env

# Проверить, что нет "change_me"
grep -c "change_me" .env
# Ожидаемо: 0

# Проверить, что нет "your-server-ip"/"your-domain.com"
grep -E "your-server-ip|your-domain\.com" .env
# Ожидаемо: пусто (или только в комментариях)
```

**⚠️ КРИТИЧНО: `VITE_API_URL`.**

**Vite вшивает `VITE_API_URL` в JS-бандл при сборке frontend.** Если он останется `http://your-server-ip`:
- Frontend будет стучаться на этот адрес.
- Браузер вернёт `ERR_NAME_NOT_RESOLVED`.
- **UI не заработает**, логин не пройдёт.

**Значения:**
- **Локальная VM (VirtualBox):** `VITE_API_URL=http://localhost:8080`
- **Облако по IP:** `VITE_API_URL=http://your-server-ip` (заменить на реальный IP!)
- **Облако по домену:** `VITE_API_URL=https://your-domain.com`

**Если менял `VITE_API_URL` после сборки — пересобрать frontend:**

```bash
docker compose -f docker-compose.prod.yml build frontend
docker compose -f docker-compose.prod.yml up -d frontend
```

### Шаг 7. Облако — сборка и запуск

```bash
# Сборка образов (5-10 минут на 2 vCPU; до 30 минут на 1 vCPU — backend тяжёлый из-за OR-Tools)
docker compose -f docker-compose.prod.yml build

# Запуск
docker compose -f docker-compose.prod.yml up -d

# Проверка статуса
docker compose -f docker-compose.prod.yml ps
```

**Ожидаемо:**
```
NAME              STATUS
aps_postgres      Up (healthy)
aps_backend       Up (healthy)
aps_frontend      Up (health: starting → healthy)
aps_nginx         Up
aps_backend_init  Exited (0)   ← нормально, init-контейнер завершается
```

**Если какой-то сервис `Restarting` — смотреть логи:**
```bash
docker compose -f docker-compose.prod.yml logs backend --tail=50
```

### Шаг 8. Облако — инициализация БД

**Способ 1 — через скрипт (рекомендуется):**

Linux / Git Bash:
```bash
chmod +x scripts/deploy_init.sh
./scripts/deploy_init.sh
```

PowerShell:
```powershell
.\scripts\deploy_init.ps1
```

**Что делает скрипт:**
1. Проверяет окружение (docker, compose, .env, контейнеры).
2. Применяет `init_schema_v4.9.sql`.
3. Применяет `init_schema_v4.9_seed.sql` (31 статья + 8 подсказок).
4. Применяет `seed_demo_data.sql`.
5. Создаёт администратора.
6. Печатает сводку.

**Идемпотентно** — можно запускать повторно.

**Способ 2 — вручную:**

```bash
# 1. Схема
docker cp backend/init_schema_v4.9.sql aps_postgres:/tmp/
docker exec -i aps_postgres psql -U aps -d household -f /tmp/init_schema_v4.9.sql

# 2. Seed-статьи
docker cp backend/init_schema_v4.9_seed.sql aps_postgres:/tmp/
docker exec -i aps_postgres psql -U aps -d household -f /tmp/init_schema_v4.9_seed.sql

# 3. Демо-данные
docker cp backend/seed_demo_data.sql aps_postgres:/tmp/
docker exec -i aps_postgres psql -U aps -d household -f /tmp/seed_demo_data.sql

# 4. Админ
docker exec -i aps_backend python -m scripts.create_admin_user
```

**Проверка:**

```bash
# Статьи справки
docker exec -i aps_postgres psql -U aps -d household -c \
  "SELECT COUNT(*) FROM help_article;"
# Ожидаемо: 31

# Подсказки
docker exec -i aps_postgres psql -U aps -d household -c \
  "SELECT COUNT(*) FROM help_hint;"
# Ожидаемо: 8
```

### Шаг 9. Облако — проверка

```bash
# Health-check (curl в Bash)
curl http://your-server-ip/health
# Ожидаемо: {"status":"healthy","version":"4.9.1",...}
```

**В PowerShell** (если локально проверяешь удалённый сервер):
```powershell
curl.exe http://your-server-ip/health
# Или:
(Invoke-WebRequest -Uri http://your-server-ip/health).Content
```

**Проверка, что `VITE_API_URL` вшит правильно:**

```bash
# Проверить, что в JS-бандле есть правильный URL
docker compose -f docker-compose.prod.yml exec frontend \
    grep -r "your-server-ip\|your-domain.com" /usr/share/nginx/html/assets/ | head -3
# Ожидаемо: ПУСТО (плейсхолдеров нет)
```

**Если найдены плейсхолдеры** — вы **забыли заменить `VITE_API_URL`** перед сборкой. См. Шаг 6.1.

**Открой в браузере:** `http://your-server-ip/`

**Логин:** `admin@household.ru` / `admin123`.

**Проверить:**
- Справка открывается: `http://your-server-ip/help` (31 статья).
- Swagger: `http://your-server-ip/docs`.
- **Сменить пароль админа** (Настройки → Профиль → Сменить пароль).

### Шаг 10. Облако — HTTPS (рекомендуется)

**Вариант A: Let's Encrypt + certbot**

```bash
# Установить certbot
sudo apt install -y certbot

# Остановить nginx (certbot займёт 80-й порт)
docker compose -f docker-compose.prod.yml stop nginx

# Получить сертификат (замените на свой домен)
sudo certbot certonly --standalone -d aps.example.com

# Скопировать сертификаты в проект
sudo mkdir -p nginx/certs
sudo cp /etc/letsencrypt/live/aps.example.com/fullchain.pem nginx/certs/
sudo cp /etc/letsencrypt/live/aps.example.com/privkey.pem nginx/certs/
sudo chown -R $USER:$USER nginx/certs/
```

**Раскомментировать HTTPS-блок** в `nginx/nginx.conf` (второй `server { listen 443 ssl; ... }`).

**В первом HTTP-блоке** заменить содержимое на редирект:
```nginx
server {
    listen 80 default_server;
    server_name _;
    return 301 https://$host$request_uri;
}
```

**Раскомментировать `443:443`** в `docker-compose.prod.yml` → `nginx.ports`.

**Обновить `.env`:**
```
ALLOWED_ORIGINS=https://aps.example.com
VITE_API_URL=https://aps.example.com
```

**Пересобрать и перезапустить:**
```bash
docker compose -f docker-compose.prod.yml build frontend
docker compose -f docker-compose.prod.yml up -d
```

**Автообновление сертификата:**
```bash
sudo crontab -e
# Добавить:
0 3 * * * certbot renew --quiet --deploy-hook "docker compose -f /home/user/household-aps/docker-compose.prod.yml restart nginx"
```

**Вариант B: Caddy (проще)**

Заменить `nginx` на `caddy` в `docker-compose.prod.yml`. Caddy автоматически получает TLS-сертификаты.

Caddyfile:
```
aps.example.com {
    handle /api/* {
        reverse_proxy backend:8000
    }
    handle /docs* {
        reverse_proxy backend:8000
    }
    handle /health {
        reverse_proxy backend:8000
    }
    handle {
        reverse_proxy frontend:80
    }
}
```

### Шаг 11. Облако — cron для бэкапов

```bash
cat > ~/backup_aps.sh << 'EOF'
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR=/home/user/backups
mkdir -p $BACKUP_DIR

docker exec aps_postgres pg_dump -U aps household | \
    gzip > $BACKUP_DIR/household_$DATE.sql.gz

# Удалить бэкапы старше 30 дней
find $BACKUP_DIR -name "*.sql.gz" -mtime +30 -delete
EOF

chmod +x ~/backup_aps.sh

# Cron: каждый день в 2:00
crontab -e
# Добавить:
0 2 * * * /home/user/backup_aps.sh
```

**Восстановление из бэкапа:**
```bash
gunzip -c ~/backups/household_20261007_020000.sql.gz | \
    docker exec -i aps_postgres psql -U aps -d household
```

---

## Обновление версии

```bash
cd household-aps

# 1. Бэкап БД
~/backup_aps.sh

# 2. Получить изменения
git pull
# или rsync с локальной машины

# 3. Пересобрать образы
docker compose -f docker-compose.prod.yml build

# 4. Применить новые миграции (если есть)
# Например:
docker cp backend/migrations/add_29.sql aps_postgres:/tmp/
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_29.sql

# 5. Пересоздать контейнеры (--force-recreate, чтобы перечитать .env, если менялся)
docker compose -f docker-compose.prod.yml up -d --force-recreate

# 6. Проверить
curl http://your-server-ip/health
docker compose -f docker-compose.prod.yml logs -f backend
```

**Downtime:** ~10-30 секунд. Для теста пользователем — приемлемо. Для 24/7 — Kubernetes/Swarm.

---

## Мониторинг

### Логи

```bash
# Все сервисы
docker compose -f docker-compose.prod.yml logs -f

# Только backend
docker compose -f docker-compose.prod.yml logs -f backend --tail=100

# Только БД
docker compose -f docker-compose.prod.yml logs -f postgres --tail=50

# Фильтрация по ошибкам
docker compose -f docker-compose.prod.yml logs backend | grep ERROR

# Лицензия
docker compose -f docker-compose.prod.yml logs backend | grep license
```

### Ресурсы

```bash
# Использование CPU/RAM
docker stats

# Свободное место
df -h

# Размер Docker-данных
docker system df
```

### Состояние БД

```bash
# Активные соединения
docker exec -i aps_postgres psql -U aps -d household -c \
  "SELECT count(*) FROM pg_stat_activity WHERE state = 'active';"

# Размер БД
docker exec -i aps_postgres psql -U aps -d household -c \
  "SELECT pg_size_pretty(pg_database_size('household'));"

# Медленные запросы (> 10 сек)
docker exec -i aps_postgres psql -U aps -d household -c \
  "SELECT pid, now() - query_start AS duration, query
   FROM pg_stat_activity
   WHERE state != 'idle' AND query_start < now() - interval '10 seconds';"
```

---

## Troubleshooting (облако)

### Backend не стартует — `connection refused`

**Причина:** backend стартует раньше PostgreSQL.

**Решение:** проверить `depends_on: condition: service_healthy` в `docker-compose.prod.yml`.

```bash
docker compose -f docker-compose.prod.yml logs backend | grep "connection refused"
```

### Frontend стучится не туда (`your-server-ip`) ⚠️

**Причина:** `VITE_API_URL` не заменён в `.env` перед сборкой frontend.

**Симптом:** в DevTools → Console:
```
POST http://your-server-ip/api/v1/auth/login
net::ERR_NAME_NOT_RESOLVED
```

**Решение:**
1. Проверить `.env`:
   ```bash
   grep VITE_API_URL .env
   ```
2. Если там `your-server-ip` — заменить на правильный:
   ```bash
   sed -i 's|^VITE_API_URL=.*|VITE_API_URL=http://localhost:8080|' .env
   ```
   (или на ваш домен/IP)
3. **Пересобрать frontend:**
   ```bash
   docker compose -f docker-compose.prod.yml build frontend
   docker compose -f docker-compose.prod.yml up -d frontend
   ```
4. Hard reload в браузере (`Ctrl+Shift+R`).

### «Network Error» при логине

**Причина:** CORS.

**Решение:** в `.env`:
```
ALLOWED_ORIGINS=http://your-server-ip,https://your-domain.com
```

Перезапустить backend:
```bash
docker compose -f docker-compose.prod.yml up -d --force-recreate backend
```

### Оборудование не грузится (307 redirect на неправильный порт) ⚠️

**Причина:** `proxy_set_header Host $host;` в `nginx/nginx.conf` — не сохраняет порт при редиректе.

**Симптом:** в DevTools → Network:
```
GET /api/v1/equipment → 307 Temporary Redirect
location: http://localhost/api/v1/equipment/    ← без порта!
```

**Решение:** заменить все `$host` на `$http_host` в `nginx/nginx.conf`:
```bash
sed -i 's|proxy_set_header Host \$host;|proxy_set_header Host $http_host;|g' nginx/nginx.conf
docker compose -f docker-compose.prod.yml up -d --force-recreate nginx
```

### Порт 80 занят

**Причина:** на VM уже стоит nginx или apache.

**Решение:**
```bash
sudo systemctl stop nginx
sudo systemctl disable nginx
# или
sudo lsof -i :80
```

### Место на диске заканчивается

**Причина:** логи Docker или старые образы.

**Решение:**
```bash
# Очистка неиспользуемых образов
docker system prune -a

# Ограничение логов уже в docker-compose.prod.yml:
docker inspect aps_backend | grep -A5 LogConfig
```

### Кириллица отображается как `????`

**Причина:** применено через pipe (`Get-Content | docker exec`) — PowerShell искажает UTF-8.

**Решение:** только `docker cp` + `psql -f`. Пересоздать затронутые данные.

### Ошибка `relation ... does not exist`

**Причина:** не применена схема.

**Решение:**
```bash
docker exec -i aps_postgres psql -U aps -d household -c "\dt plan_settings"
# Если таблицы нет:
docker cp backend/init_schema_v4.9.sql aps_postgres:/tmp/
docker exec -i aps_postgres psql -U aps -d household -f /tmp/init_schema_v4.9.sql
```

### `Permission denied` при `docker`

**Причина:** пользователь не в группе `docker`.

**Решение:**
```bash
sudo usermod -aG docker $USER
newgrp docker
```

### Solver работает слишком долго

**Причина:** большой горизонт, много партий.

**Решение:**
- Настройки → `timeout_seconds = 300`.
- Настройки → `horizon_hours = 336` (14 дней).

---

## Лицензирование при деплое

APS Scheduler использует **offline-лицензирование** (JWT-токен, подписанный вендором). Проверка происходит **на backend при старте**, без обращения к внешним серверам.

Подробное описание системы лицензирования — в [LICENSE.md](LICENSE.md). Здесь — только то, что нужно для деплоя.

### Переменные окружения

Все переменные задаются в **корневом** `.env` (не в `backend/.env`!).

| Переменная | Обязательна | Назначение |
|---|---|---|
| `LICENSE_VERIFY` | да | `true` — проверка включена, `false` — отключена (только для локальной разработки) |
| `LICENSE_KEY` | если `VERIFY=true` | JWT-лицензия от вендора |
| `LICENSE_PUBLIC_KEY` | для **RS256/ES256** (prod) | Публичный ключ вендора (PEM). Клиент не может подписать лицензию этим ключом |
| `LICENSE_MASTER_SECRET` | для **HS256** (dev-only) | Мастер-секрет HS256 (64 hex). Клиент получает тот же ключ, что и подпись, — **только для внутренних тестов** |

**Приоритет:** если задан `LICENSE_PUBLIC_KEY` — используется RS256/ES256, `LICENSE_MASTER_SECRET` игнорируется.

### Volume `aps_data` — критично

Backend сохраняет свой `instance_id` в файл `/data/license_instance` внутри контейнера. **Этот файл должен переживать пересоздание контейнера**, иначе:

- `instance_id` меняется при каждом `up`,
- привязанные (`instance_bound`) лицензии становятся невалидными.

В `docker-compose.prod.yml` для этого есть named volume:

```yaml
services:
  backend:
    volumes:
      - aps_data:/data
```

**⚠️ Никогда не запускайте `docker compose down -v`** — это удалит `pgdata` (БД) и `aps_data` (instance_id). Attached-лицензии придётся перевыпускать.

**⚠️ При смене сервера или переустановке — `instance_id` будет другим.** Attached-лицензию придётся перевыпускать под новый `instance_id`.

### Права на `/data`

Backend работает от непривилегированного пользователя (uid 1000, см. `backend/Dockerfile`). Docker создаёт named volume `aps_data` **от root**. Значит, backend не сможет писать в `/data`.

Решение — **init-контейнер** `backend-init`, который запускается **до** backend, делает `chown -R 1000:1000 /data` и завершается. В `docker-compose.prod.yml` уже включён:

```yaml
services:
  backend-init:
    image: alpine:3.20
    command: chown -R 1000:1000 /data
    volumes:
      - aps_data:/data
    restart: "no"

  backend:
    depends_on:
      backend-init:
        condition: service_completed_successfully
```

Проверить, что права корректны:

```bash
docker inspect aps_backend --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{"\n"}}{{end}}'
sudo ls -la /var/lib/docker/volumes/<project>_aps_data/_data
# Владелец должен быть: 1000 1000 (aps aps)
```

Проверить, что init-контейнер отработал:

```bash
docker compose -f docker-compose.prod.yml ps backend-init
# Ожидаемо: Exited (0)

docker compose -f docker-compose.prod.yml logs backend-init
# Может быть пусто (chown не выводит ничего)
```

### Сценарии деплоя

#### A. Production (RS256) — **рекомендуется**

Используется **асимметричная подпись**: вендор подписывает **приватным** ключом, клиент проверяет **публичным**. Клиент **не может** выпустить себе лицензию.

**1. Сгенерировать пару ключей (на машине вендора, один раз):**

```bash
python backend/scripts/generate_license.py init-master-key --algorithm RS256
```

Создаст:
- `~/.aps/license_master_key.private.pem` — **секрет вендора**, НИКОМУ не передавать;
- `~/.aps/license_master_key.public.pem` — публичный ключ, передавать клиенту.

**2. Получить `instance_id` клиента (с его сервера):**

```bash
curl https://aps.client.com/api/v1/license/instance
```

**3. Сгенерировать лицензию под клиента:**

```bash
python backend/scripts/generate_license.py generate \
  --algorithm RS256 \
  --org "ООО Клиент" \
  --tier enterprise \
  --days 365 \
  --instance-id <instance_id> \
  --output client.license
```

Если привязка к серверу не нужна (работает на любом) — **убрать `--instance-id`**.

**4. Передать клиенту:**
- **LICENSE_KEY** (JWT из `client.license`);
- **LICENSE_PUBLIC_KEY** (содержимое `license_master_key.public.pem`).

**5. В `.env` клиента:**

```dotenv
LICENSE_VERIFY=true
LICENSE_KEY=eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
LICENSE_PUBLIC_KEY="-----BEGIN PUBLIC KEY-----\nMIIB...\n-----END PUBLIC KEY-----"
# LICENSE_MASTER_SECRET — НЕ задавать!
```

**6. Перезапустить backend:**

```bash
docker compose -f docker-compose.prod.yml up -d --force-recreate backend
```

**Проверка в логах:**

```
[license] Режим проверки: RS256 (публичный ключ вендора)
[license] Лицензия валидна: holder='ООО Клиент', tier=enterprise, algorithm=RS256, days_left=365, instance_bound=true
```

#### B. Тест/дев (HS256 unattached) — только для внутренних тестов

⚠️ **Не использовать в продакшене.** Клиент получает **тот же секрет**, что и подпись, и технически может выпустить себе лицензию.

Лицензия **без `instance_id`** — работает на любой машине.

**1. Сгенерировать мастер-секрет (один раз):**

```bash
python backend/scripts/generate_license.py init-master-key --algorithm HS256
```

Создаст `~/.aps/license_master_key.hex` — 64 hex-символа.

**2. Сгенерировать лицензию:**

```bash
python backend/scripts/generate_license.py generate \
  --algorithm HS256 \
  --org "Test Org" \
  --tier enterprise \
  --days 30 \
  --output test.license
```

**3. В `.env`:**

```dotenv
LICENSE_VERIFY=true
LICENSE_KEY=<JWT из test.license>
LICENSE_MASTER_SECRET=<64 hex из init-master-key>
```

**4. Перезапустить backend** через `--force-recreate`:

```bash
docker compose -f docker-compose.prod.yml up -d --force-recreate backend
```

**Почему `--force-recreate`, а не `restart`:** `restart` переиспользует существующий контейнер с его переменными окружения. `.env` перечитывается **только при создании** контейнера. После правки `.env` нужен `--force-recreate`.

#### C. Локальная разработка, лицензия не нужна

```dotenv
LICENSE_VERIFY=false
```

Backend стартует, все эндпоинты доступны. В логах предупреждение:

```
[license] LICENSE_VERIFY=false — проверка лицензии отключена. Не использовать в production!
```

**Только для локальной разработки.** В продакшене — использовать **A (RS256)**.

### Перенос JWT на сервер без venv

Если на сервере нет Python-окружения с зависимостями (типично для VM/облака), лицензию генерируют **на машине вендора**, а на сервер переносят **через base64** — чтобы избежать искажений при копипасте:

**На машине вендора:**

```powershell
$jwt = (Get-Content client.license -Raw).Trim()
[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($jwt))
```

**На сервере:**

```bash
cat > /tmp/li.b64 << 'EOF'
<вставь base64-строку одной строкой>
EOF
base64 -d /tmp/li.b64 > /tmp/license.jwt
rm /tmp/li.b64

# Проверить длину
# HS256: ~330-400 символов; RS256: ~700-900 символов
wc -c /tmp/license.jwt
```

Затем в `.env`:

```bash
# Добавить LICENSE_KEY из файла
echo "LICENSE_KEY=$(cat /tmp/license.jwt)" >> .env
```

Или вручную через `nano .env`.

### Диагностика лицензирования

| Симптом | Причина | Решение |
|---|---|---|
| UI: красный бейдж «Лицензия недействительна» | Backend не загрузил лицензию | `docker compose logs backend | grep license` — смотреть причину |
| В логах: `LICENSE_KEY не задан` | `.env` не прочитан | Проверить, что `.env` в корне, а не в `backend/`; `--force-recreate backend` |
| В логах: `Signature verification failed` | Неверный ключ проверки | `LICENSE_MASTER_SECRET` (HS256) или `LICENSE_PUBLIC_KEY` (RS256) не соответствует тому, чем подписан JWT |
| В логах: `LicenseInstanceMismatchError` | Лицензия привязана к другому серверу | Перевыпустить лицензию под текущий `instance_id` (`curl /api/v1/license/instance`) |
| В логах: `Permission denied: /data/license_instance` | Volume не chown'нут | Проверить, что `backend-init` запускается и завершается успешно |
| `instance_id` меняется при `restart` | Volume `aps_data` не смонтирован | Проверить `docker inspect aps_backend \| grep -A5 Mounts` |
| После правки `.env` ничего не поменялось | Использовали `restart`, а не `--force-recreate` | `up -d --force-recreate backend` |
| UI: `Objects are not valid as a React child` | Frontend не пересобран | `docker compose build frontend` + `up -d --force-recreate frontend nginx` |
| UI: нет бейджа лицензии | Frontend образ устарел | `docker compose build --no-cache frontend` + `up -d --force-recreate frontend nginx` |
| UI: бейдж «Лицензия недействительна», хотя `/api/v1/license/info` возвращает `valid: true` | Frontend кэширует старый `licenseInfo` | Hard reload (`Ctrl+Shift+R`) |
| `/license/info` возвращает `algorithm: "HS256"`, хотя реально RS256 | Старый код с константой `LICENSE_ALGORITHM` | Обновить до версии, где `algorithm = info.algorithm` (из заголовка JWT) |

### Проверка статуса лицензии

После запуска:

```bash
# Через API
curl http://your-server-ip/api/v1/license/info | python3 -m json.tool

# Ожидаемо при valid=true:
# {
#   "valid": true,
#   "verify_enabled": true,
#   "key_provided": true,
#   "holder": "ООО Клиент",
#   "tier": "enterprise",
#   "days_left": 365,
#   "is_expired": false,
#   "instance_bound": true,   ← или false для unattached
#   "error": null,
#   "algorithm": "RS256"      ← реальный алгоритм из JWT
# }
```

Через UI: **клик по бейджу лицензии в шапке** → открывается `/license` со всеми полями.

### Ссылки

- [docs/LICENSE.md](LICENSE.md) — полное описание системы лицензирования
- [scripts/generate_license.py](../backend/scripts/generate_license.py) — CLI для вендора
- [backend/app/core/license.py](../backend/app/core/license.py) — код проверки

---

## Чек-лист развёртывания

- [ ] VM создана, SSH работает.
- [ ] Security Group: 22, 80, 443 открыты.
- [ ] `ufw` настроен.
- [ ] Docker + docker-compose установлены.
- [ ] Проект склонирован / залит.
- [ ] `.env` создан из `.env.example`.
- [ ] **`SECRET_KEY` сгенерирован** (`openssl rand -hex 32`).
- [ ] **`POSTGRES_PASSWORD` задан** (мин. 16 символов).
- [ ] **`ALLOWED_ORIGINS` = домен/IP** ⚠️.
- [ ] **`VITE_API_URL` = домен/IP** ⚠️ — **не `your-server-ip`!**
- [ ] **Проверка: `grep -c "change_me" .env` → `0`** ⚠️.
- [ ] **Проверка: `grep -c "your-server-ip" .env` → `0`** ⚠️.
- [ ] **Лицензия: `LICENSE_VERIFY` задан** (true для прода, false для dev).
- [ ] **Если `LICENSE_VERIFY=true`: `LICENSE_KEY` задан** ⚠️.
- [ ] **Если RS256 (prod): `LICENSE_PUBLIC_KEY` задан** (и `LICENSE_MASTER_SECRET` убран).
- [ ] **Если HS256 (dev-only): `LICENSE_MASTER_SECRET` задан** (64 hex).
- [ ] `.env` **НЕ** в git.
- [ ] `docker compose -f docker-compose.prod.yml build` — ок.
- [ ] `docker compose -f docker-compose.prod.yml up -d` — 4 контейнера Up + `backend-init` Exited (0).
- [ ] `backend-init` отработал (`ps backend-init` → Exited (0)).
- [ ] В логах backend: `instance_id сохранён в /data/license_instance` (без `Permission denied`).
- [ ] В логах backend: `Режим проверки: HS256/RS256 ...` (если `LICENSE_VERIFY=true`).
- [ ] В логах backend: `Лицензия валидна: holder=..., days_left=...` (если `LICENSE_VERIFY=true`).
- [ ] `deploy_init.sh` (или `.ps1`) выполнен успешно.
- [ ] `init_schema_v4.9.sql` применён.
- [ ] `init_schema_v4.9_seed.sql` применён.
- [ ] `seed_demo_data.sql` применён.
- [ ] Админ создан (или обновлён).
- [ ] `/health` отвечает `version: "4.9.1"`.
- [ ] **Проверка: `grep -r "your-server-ip" /usr/share/nginx/html/assets/` → пусто** ⚠️.
- [ ] Браузер открывает `http://your-server-ip/`.
- [ ] **UI: бейдж лицензии в шапке** (зелёный при valid, красный при `LICENSE_VERIFY=false`).
- [ ] **UI: страница `/license` открывается и показывает все поля**.
- [ ] **`/license/info` возвращает `algorithm: "RS256"` или `"HS256"`** (соответствует реальному).
- [ ] Логин работает.
- [ ] Справка открывается (31 статья).
- [ ] Оборудование грузится (10 записей).
- [ ] **Пароль админа сменён.**
- [ ] (Опционально) HTTPS настроен.
- [ ] (Опционально) Cron для бэкапов.
- [ ] (Опционально) Проверено восстановление из бэкапа.

---

## Что дальше

- [OPERATIONS.md](OPERATIONS.md) — операции с БД (backup, restore, миграции).
- [LICENSE.md](LICENSE.md) — система лицензирования (вендор + клиент + разработчик).
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — детальные проблемы.
- [CONFIGURATION.md](CONFIGURATION.md) — все переменные окружения.

---

*Последнее обновление: 2026-10-10*