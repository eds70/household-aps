# ==========================================
# APS Production Scheduler — Quick Start
# ==========================================
# Поднимает весь проект с нуля одной командой:
#   1. PostgreSQL в Docker (контейнер aps_postgres)
#   2. Схема БД + демо-данные
#   3. Python venv + зависимости
#   4. Админ-пользователь
#   5. npm-зависимости фронтенда
#
# Использование:
#   .\quickstart.ps1              # полный запуск
#   .\quickstart.ps1 -SkipDb      # пропустить PostgreSQL (уже запущен)
#   .\quickstart.ps1 -SkipSeed    # пропустить схему и демо-данные
#   .\quickstart.ps1 -Help        # справка
# ==========================================

param(
    [switch]$SkipDb,
    [switch]$SkipSeed,
    [switch]$SkipFrontend,
    [switch]$Help
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# ---------- Цвета ----------
function Write-Step($msg)    { Write-Host "▶ $msg" -ForegroundColor Cyan }
function Write-Ok($msg)      { Write-Host "✅ $msg" -ForegroundColor Green }
function Write-Warn($msg)    { Write-Host "⚠️  $msg" -ForegroundColor Yellow }
function Write-Fail($msg)    { Write-Host "❌ $msg" -ForegroundColor Red }

# ---------- Справка ----------
if ($Help) {
    Write-Host ""
    Write-Host "APS Production Scheduler — Quick Start" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Использование:"
    Write-Host "  .\quickstart.ps1              Полный запуск"
    Write-Host "  .\quickstart.ps1 -SkipDb      Пропустить PostgreSQL (уже запущен)"
    Write-Host "  .\quickstart.ps1 -SkipSeed    Пропустить схему и демо-данные"
    Write-Host "  .\quickstart.ps1 -SkipFrontend Пропустить установку npm-зависимостей"
    Write-Host "  .\quickstart.ps1 -Help        Показать эту справку"
    Write-Host ""
    Write-Host "После запуска:"
    Write-Host "  Backend:  cd backend; python run_server.py  →  http://localhost:8000/docs"
    Write-Host "  Frontend: cd frontend; npm run dev           →  http://localhost:5173"
    Write-Host "  Логин:    admin@household.ru / admin123"
    Write-Host ""
    exit 0
}

# ---------- Баннер ----------
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  🏭 APS Production Scheduler" -ForegroundColor Cyan
Write-Host "  Quick Start Script" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# ---------- Проверка окружения ----------
Write-Step "Проверка окружения..."

$missing = @()
foreach ($cmd in @("docker", "python", "npm")) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        $missing += $cmd
    }
}

if ($missing.Count -gt 0) {
    Write-Fail "Не найдены: $($missing -join ', ')"
    Write-Host ""
    Write-Host "Установите:" -ForegroundColor Yellow
    Write-Host "  Docker:  https://docs.docker.com/get-docker/"
    Write-Host "  Python:  https://www.python.org/downloads/ (3.12+)"
    Write-Host "  Node.js: https://nodejs.org/ (18+)"
    exit 1
}
Write-Ok "Docker, Python, Node.js — найдены"

# ---------- Проверка, что мы в корне проекта ----------
if (-not (Test-Path "backend\init_schema.sql")) {
    Write-Fail "Не найден backend\init_schema.sql. Запускай скрипт из корня проекта (household-aps\)."
    exit 1
}
if (-not (Test-Path "frontend\package.json")) {
    Write-Fail "Не найден frontend\package.json. Запускай скрипт из корня проекта."
    exit 1
}
Write-Ok "Корень проекта определён: $(Get-Location)"

# ==========================================
# ШАГ 1. PostgreSQL в Docker
# ==========================================
if (-not $SkipDb) {
    Write-Step "Шаг 1/5: PostgreSQL в Docker..."

    $containerExists = docker ps -a --filter "name=^aps_postgres$" --format "{{.Names}}"

    if ($containerExists -eq "aps_postgres") {
        $containerRunning = docker ps --filter "name=^aps_postgres$" --format "{{.Names}}"
        if ($containerRunning -eq "aps_postgres") {
            Write-Ok "Контейнер aps_postgres уже запущен"
        } else {
            Write-Host "   Контейнер aps_postgres существует, но остановлен. Запускаю..."
            docker start aps_postgres | Out-Null
            Start-Sleep -Seconds 3
            Write-Ok "Контейнер aps_postgres запущен"
        }
    } else {
        Write-Host "   Создаю контейнер aps_postgres..."
        docker run --name aps_postgres `
            -e POSTGRES_USER=aps `
            -e POSTGRES_PASSWORD=aps_secret `
            -e POSTGRES_DB=household `
            -p 5433:5432 `
            -d postgres:16 | Out-Null

        Write-Host "   Ждём инициализации PostgreSQL (10 сек)..."
        Start-Sleep -Seconds 10
        Write-Ok "PostgreSQL запущен в контейнере aps_postgres"
    }
} else {
    Write-Warn "Шаг 1/5: PostgreSQL пропущен (-SkipDb)"
}

# ==========================================
# ШАГ 2. Схема БД + демо-данные
# ==========================================
if (-not $SkipSeed) {
    Write-Step "Шаг 2/5: Схема БД и демо-данные..."

    # Проверяем, есть ли уже таблицы
    $tableCount = docker exec aps_postgres psql -U aps -d household -t -c `
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>$null
    $tableCount = ($tableCount -as [string]).Trim()

    if ([int]$tableCount -gt 0) {
        Write-Warn "В БД уже есть $tableCount таблиц. Пропускаю init_schema.sql."
        Write-Host "   Если нужно пересоздать — удалите БД и запустите снова:"
        Write-Host "     docker exec aps_postgres psql -U aps -d household -c `"DROP SCHEMA public CASCADE; CREATE SCHEMA public;`""
    } else {
        Write-Host "   Применяю init_schema.sql..."
        Get-Content -Raw backend\init_schema.sql | docker exec -i aps_postgres psql -U aps -d household | Out-Null
        Write-Ok "Схема создана"
    }

    # Демо-данные — только если batch пустой
    $batchCount = docker exec aps_postgres psql -U aps -d household -t -c `
        "SELECT COUNT(*) FROM batch;" 2>$null
    $batchCount = ($batchCount -as [string]).Trim()

    if ([int]$batchCount -gt 0) {
        Write-Warn "В БД уже есть $batchCount партий. Пропускаю seed_demo_data.sql."
    } else {
        Write-Host "   Применяю seed_demo_data.sql..."
        Get-Content -Raw backend\seed_demo_data.sql | docker exec -i aps_postgres psql -U aps -d household | Out-Null
        Write-Ok "Демо-данные загружены"
    }
} else {
    Write-Warn "Шаг 2/5: Схема и демо-данные пропущены (-SkipSeed)"
}

# ==========================================
# ШАГ 3. Python venv + зависимости
# ==========================================
Write-Step "Шаг 3/5: Python venv и зависимости..."

Push-Location backend

if (-not (Test-Path ".venv")) {
    Write-Host "   Создаю .venv..."
    python -m venv .venv
    Write-Ok ".venv создан"
} else {
    Write-Ok ".venv уже существует"
}

# Активируем venv
$venvActivate = ".\.venv\Scripts\Activate.ps1"
if (Test-Path $venvActivate) {
    Write-Host "   Устанавливаю зависимости (requirements.txt + requirements-dev.txt)..."
    & $venvActivate
    pip install --quiet --upgrade pip
    pip install --quiet -r requirements.txt
    if (Test-Path "requirements-dev.txt") {
        pip install --quiet -r requirements-dev.txt
    }
    Write-Ok "Зависимости Python установлены"
} else {
    Write-Fail "Не удалось найти .venv\Scripts\Activate.ps1"
    Pop-Location
    exit 1
}

# ---------- Создаём администратора ----------
Write-Host "   Создаю/обновляю администратора..."
python -m scripts.create_admin_user | Out-Null
Write-Ok "Администратор admin@household.ru создан"

Pop-Location

# ==========================================
# ШАГ 4. npm-зависимости фронтенда
# ==========================================
if (-not $SkipFrontend) {
    Write-Step "Шаг 4/5: npm-зависимости..."

    Push-Location frontend

    if (Test-Path "node_modules") {
        Write-Ok "node_modules уже существует"
    } else {
        Write-Host "   npm install (может занять 1-2 минуты)..."
        npm install --silent
        Write-Ok "npm-зависимости установлены"
    }

    Pop-Location
} else {
    Write-Warn "Шаг 4/5: npm-зависимости пропущены (-SkipFrontend)"
}

# ==========================================
# ШАГ 5. Готово!
# ==========================================
Write-Step "Шаг 5/5: Готово!"

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "  ✅ Проект готов к запуску!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Запусти в двух терминалах:" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Терминал 1 (Backend):" -ForegroundColor Yellow
Write-Host "    cd backend"
Write-Host "    .\.venv\Scripts\Activate.ps1"
Write-Host "    python run_server.py"
Write-Host ""
Write-Host "  Терминал 2 (Frontend):" -ForegroundColor Yellow
Write-Host "    cd frontend"
Write-Host "    npm run dev"
Write-Host ""
Write-Host "Открой в браузере:" -ForegroundColor Cyan
Write-Host "  Frontend: http://localhost:5173"
Write-Host "  Swagger:  http://localhost:8000/docs"
Write-Host ""
Write-Host "Логин по умолчанию:" -ForegroundColor Cyan
Write-Host "  Email:  admin@household.ru"
Write-Host "  Пароль: admin123"
Write-Host ""

