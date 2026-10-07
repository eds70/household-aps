#!/usr/bin/env bash
#
# scripts/deploy_init.sh
#
# Первичная инициализация БД APS Production Scheduler в Docker.
#
# Что делает:
#   1. Проверяет окружение (docker, docker compose, контейнер postgres).
#   2. Применяет init_schema_v4.9.sql          (полная схема).
#   3. Применяет init_schema_v4.9_seed.sql     (31 статья + 8 подсказок).
#   4. Применяет seed_demo_data.sql            (демо-данные).
#   5. Создаёт администратора.
#   6. Печатает сводку.
#
# Идемпотентно: можно запускать повторно (все SQL используют
# IF NOT EXISTS / ON CONFLICT DO NOTHING).
#
# Использование (из корня проекта):
#   chmod +x scripts/deploy_init.sh
#   ./scripts/deploy_init.sh
#
# ⚠️  Требует запущенного docker-compose.prod.yml:
#       docker compose -f docker-compose.prod.yml up -d
#
# ⚠️  Кириллица: файлы применяются через `docker cp` + `psql -f`,
#     а не через pipe. Иначе кодировка портится.

set -euo pipefail

# ==========================================
# КОНСТАНТЫ
# ==========================================
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

COMPOSE_FILE="docker-compose.prod.yml"
PG_CONTAINER="aps_postgres"
BACKEND_CONTAINER="aps_backend"

# Цвета для вывода (если поддерживается терминалом)
if [ -t 1 ]; then
    C_RESET='\033[0m'
    C_GREEN='\033[0;32m'
    C_YELLOW='\033[0;33m'
    C_RED='\033[0;31m'
    C_BLUE='\033[0;34m'
    C_BOLD='\033[1m'
else
    C_RESET=''
    C_GREEN=''
    C_YELLOW=''
    C_RED=''
    C_BLUE=''
    C_BOLD=''
fi

# ==========================================
# ХЕЛПЕРЫ
# ==========================================
log_info()  { echo -e "${C_BLUE}ℹ${C_RESET}  $*"; }
log_ok()    { echo -e "${C_GREEN}✔${C_RESET}  $*"; }
log_warn()  { echo -e "${C_YELLOW}⚠${C_RESET}  $*"; }
log_error() { echo -e "${C_RED}✖${C_RESET}  $*" >&2; }
log_step()  { echo -e "\n${C_BOLD}${C_BLUE}▶ $*${C_RESET}"; }

die() {
    log_error "$1"
    exit 1
}

# ==========================================
# 1. ПРОВЕРКА ОКРУЖЕНИЯ
# ==========================================
log_step "Проверка окружения"

# docker
if ! command -v docker >/dev/null 2>&1; then
    die "docker не установлен. Установите: https://docs.docker.com/engine/install/"
fi
log_ok "docker найден: $(docker --version | cut -d' ' -f3 | tr -d ',')"

# docker compose
if ! docker compose version >/dev/null 2>&1; then
    die "docker compose plugin не установлен. См.: https://docs.docker.com/compose/install/"
fi
log_ok "docker compose найден: $(docker compose version --short)"

# .env
if [ ! -f .env ]; then
    die ".env не найден. Скопируйте: cp .env.example .env  и заполните."
fi
log_ok ".env найден"

# compose-файл
if [ ! -f "$COMPOSE_FILE" ]; then
    die "$COMPOSE_FILE не найден. Скрипт запущен не из корня проекта?"
fi
log_ok "$COMPOSE_FILE найден"

# ==========================================
# 2. ПРОВЕРКА КОНТЕЙНЕРОВ
# ==========================================
log_step "Проверка контейнеров"

if ! docker ps --filter "name=^/${PG_CONTAINER}$" --format '{{.Names}}' | grep -q "$PG_CONTAINER"; then
    die "Контейнер '$PG_CONTAINER' не запущен. Запустите: docker compose -f $COMPOSE_FILE up -d"
fi
log_ok "Контейнер '$PG_CONTAINER' запущен"

if ! docker ps --filter "name=^/${BACKEND_CONTAINER}$" --format '{{.Names}}' | grep -q "$BACKEND_CONTAINER"; then
    log_warn "Контейнер '$BACKEND_CONTAINER' не запущен — админ не будет создан."
    log_warn "Запустите: docker compose -f $COMPOSE_FILE up -d backend"
    BACKEND_AVAILABLE=0
else
    log_ok "Контейнер '$BACKEND_CONTAINER' запущен"
    BACKEND_AVAILABLE=1
fi

# Проверка readiness БД
log_info "Ожидание готовности PostgreSQL (pg_isready)..."
for i in {1..30}; do
    if docker exec "$PG_CONTAINER" pg_isready -U aps -d household >/dev/null 2>&1; then
        log_ok "PostgreSQL готов"
        break
    fi
    if [ "$i" -eq 30 ]; then
        die "PostgreSQL не готов за 30 секунд"
    fi
    sleep 1
done

# ==========================================
# 3. ПРИМЕНЕНИЕ ФАЙЛОВ SQL
# ==========================================
apply_sql() {
    local local_path="$1"
    local description="$2"
    local filename
    filename="$(basename "$local_path")"

    if [ ! -f "$local_path" ]; then
        die "Не найден файл: $local_path"
    fi

    log_info "Применение: $filename ($description)"
    docker cp "$local_path" "${PG_CONTAINER}:/tmp/${filename}"
    docker exec -i "$PG_CONTAINER" psql -U aps -d household \
        -v ON_ERROR_STOP=1 \
        -f "/tmp/${filename}" >/dev/null
    log_ok "$filename применён"
}

# 3.1. Схема (v4.9.0)
log_step "Применение схемы БД"
apply_sql "backend/init_schema_v4.9.sql" "полная схема v4.9.0"

# 3.2. Seed-статьи справки
log_step "Применение seed-статей справки"
apply_sql "backend/init_schema_v4.9_seed.sql" "31 статья + 8 подсказок"

# 3.3. Демо-данные
log_step "Применение демо-данных"
if [ -f "backend/seed_demo_data.sql" ]; then
    apply_sql "backend/seed_demo_data.sql" "демо-оборудование, партии, заказы"
else
    log_warn "backend/seed_demo_data.sql не найден — пропускаю"
fi

# ==========================================
# 4. СОЗДАНИЕ АДМИНИСТРАТОРА
# ==========================================
if [ "$BACKEND_AVAILABLE" -eq 1 ]; then
    log_step "Создание администратора"

    # Проверяем, есть ли уже админ
    ADMIN_EXISTS=$(docker exec -i "$PG_CONTAINER" psql -U aps -d household -tAc \
        "SELECT COUNT(*) FROM app_user WHERE role = 'ADMIN';")

    if [ "$ADMIN_EXISTS" = "0" ]; then
        log_info "Админ не найден — создаю (admin@household.ru / admin123)"
        docker exec -i "$BACKEND_CONTAINER" python -m scripts.create_admin_user
        log_ok "Администратор создан"
    else
        log_warn "Администратор уже существует ($ADMIN_EXISTS). Пропускаю."
        log_warn "Если забыли пароль — сменить вручную через SQL или создать нового."
    fi
fi

# ==========================================
# 5. СВОДНАЯ ПРОВЕРКА
# ==========================================
log_step "Сводная проверка"

psql_q() {
    docker exec -i "$PG_CONTAINER" psql -U aps -d household -tAc "$1"
}

# Проверка ключевых таблиц
TABLE_COUNT=$(psql_q "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';")
log_info "Таблиц в public: $TABLE_COUNT"

# Проверка plan_settings, help_article, help_hint, audit_saved_view
for table in plan_settings help_article help_hint audit_saved_view; do
    if [ "$(psql_q "SELECT to_regclass('public.$table') IS NOT NULL;")" = "t" ]; then
        log_ok "Таблица '$table' есть"
    else
        log_error "Таблица '$table' ОТСУТСТВУЕТ"
    fi
done

# Счётчики
ARTICLES=$(psql_q "SELECT COUNT(*) FROM help_article WHERE is_published = TRUE;")
HINTS=$(psql_q "SELECT COUNT(*) FROM help_hint WHERE is_published = TRUE;")
FAQ=$(psql_q "SELECT COUNT(*) FROM help_article WHERE category = 'faq';")
SETTINGS=$(psql_q "SELECT COUNT(*) FROM app_settings WHERE organization_id = '00000000-0000-0000-0000-000000000001';")
EQUIPMENT=$(psql_q "SELECT COUNT(*) FROM equipment;")
BATCHES=$(psql_q "SELECT COUNT(*) FROM batch;")

log_info "help_article (опубликовано):  $ARTICLES   (ожидаемо: 31)"
log_info "help_hint (опубликовано):     $HINTS   (ожидаемо: 8)"
log_info "FAQ-статей:                   $FAQ   (ожидаемо: 15)"
log_info "app_settings:                 $SETTINGS   (ожидаемо: 45+)"
log_info "Оборудования:                 $EQUIPMENT"
log_info "Партий:                       $BATCHES"

# Версия API (если backend доступен)
if [ "$BACKEND_AVAILABLE" -eq 1 ]; then
    API_VERSION=$(curl -s http://localhost/health 2>/dev/null | grep -o '"version":"[^"]*"' | cut -d'"' -f4 || echo "?")
    log_info "API version:                  $API_VERSION   (ожидаемо: 4.9.0)"
fi

# ==========================================
# 6. ИТОГ
# ==========================================
echo ""
echo -e "${C_GREEN}${C_BOLD}═══════════════════════════════════════════════════════════${C_RESET}"
echo -e "${C_GREEN}${C_BOLD}  ✅  Инициализация завершена успешно${C_RESET}"
echo -e "${C_GREEN}${C_BOLD}═══════════════════════════════════════════════════════════${C_RESET}"
echo ""
echo "  🌐  Frontend:  http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo 'localhost')/"
echo "  🔧  Swagger:   http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo 'localhost')/docs"
echo "  ❤️   Health:    http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo 'localhost')/health"
echo ""
echo "  🔑  Логин:     admin@household.ru"
echo "  🔒  Пароль:    admin123"
echo "  ${C_YELLOW}⚠  Смените пароль после первого входа!${C_RESET}"
echo ""
log_info "Проверить логи: docker compose -f $COMPOSE_FILE logs -f backend"