# scripts/deploy_init.ps1
#
# Первичная инициализация БД APS Production Scheduler в Docker.
# Аналог deploy_init.sh для Windows / PowerShell.
#
# Использование (из корня проекта):
#   .\scripts\deploy_init.ps1
#
# ⚠️  Требует запущенного docker-compose.prod.yml:
#       docker compose -f docker-compose.prod.yml up -d
#
# ⚠️  Кириллица: файлы применяются через `docker cp` + `psql -f`,
#     а не через Get-Content | docker exec. Иначе кодировка портится.

$ErrorActionPreference = "Stop"

# ==========================================
# КОНСТАНТЫ
# ==========================================
$ProjectRoot = Resolve-Path "$PSScriptRoot\.."
Set-Location $ProjectRoot

$ComposeFile = "docker-compose.prod.yml"
$PgContainer = "aps_postgres"
$BackendContainer = "aps_backend"

# ==========================================
# ХЕЛПЕРЫ
# ==========================================
function Write-Info  ($msg) { Write-Host "i  $msg" -ForegroundColor Cyan }
function Write-Ok    ($msg) { Write-Host "+  $msg" -ForegroundColor Green }
function Write-Warn  ($msg) { Write-Host "!  $msg" -ForegroundColor Yellow }
function Write-Err   ($msg) { Write-Host "x  $msg" -ForegroundColor Red }
function Write-Step  ($msg) { Write-Host "`n>  $msg" -ForegroundColor Blue }

function Die ($msg) {
    Write-Err $msg
    exit 1
}

# ==========================================
# 1. ПРОВЕРКА ОКРУЖЕНИЯ
# ==========================================
Write-Step "Проверка окружения"

# docker
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Die "docker не установлен. Установите Docker Desktop: https://www.docker.com/products/docker-desktop"
}

$dockerVersion = (docker --version) -replace '.*version ', '' -replace ',.*', ''
Write-Ok "docker найден: $dockerVersion"

# docker compose
try {
    $composeVersion = docker compose version --short 2>$null
    Write-Ok "docker compose найден: $composeVersion"
} catch {
    Die "docker compose plugin не установлен."
}

# .env
if (-not (Test-Path ".env")) {
    Die ".env не найден. Скопируйте: Copy-Item .env.example .env  и заполните."
}
Write-Ok ".env найден"

# compose-файл
if (-not (Test-Path $ComposeFile)) {
    Die "$ComposeFile не найден. Скрипт запущен не из корня проекта?"
}
Write-Ok "$ComposeFile найден"

# ==========================================
# 2. ПРОВЕРКА КОНТЕЙНЕРОВ
# ==========================================
Write-Step "Проверка контейнеров"

$pgRunning = docker ps --filter "name=^/$PgContainer$" --format "{{.Names}}"
if ($pgRunning -ne $PgContainer) {
    Die "Контейнер '$PgContainer' не запущен. Запустите: docker compose -f $ComposeFile up -d"
}
Write-Ok "Контейнер '$PgContainer' запущен"

$backendRunning = docker ps --filter "name=^/$BackendContainer$" --format "{{.Names}}"
$BackendAvailable = $false
if ($backendRunning -eq $BackendContainer) {
    Write-Ok "Контейнер '$BackendContainer' запущен"
    $BackendAvailable = $true
} else {
    Write-Warn "Контейнер '$BackendContainer' не запущен — админ не будет создан."
    Write-Warn "Запустите: docker compose -f $ComposeFile up -d backend"
}

# Ожидание готовности PostgreSQL
Write-Info "Ожидание готовности PostgreSQL (pg_isready)..."
$ready = $false
for ($i = 1; $i -le 30; $i++) {
    docker exec $PgContainer pg_isready -U aps -d household *> $null
    if ($LASTEXITCODE -eq 0) {
        Write-Ok "PostgreSQL готов"
        $ready = $true
        break
    }
    Start-Sleep -Seconds 1
}
if (-not $ready) {
    Die "PostgreSQL не готов за 30 секунд"
}

# ==========================================
# 3. ПРИМЕНЕНИЕ ФАЙЛОВ SQL
# ==========================================
function Apply-Sql {
    param(
        [string]$LocalPath,
        [string]$Description
    )

    $filename = Split-Path $LocalPath -Leaf

    if (-not (Test-Path $LocalPath)) {
        Die "Не найден файл: $LocalPath"
    }

    Write-Info "Применение: $filename ($Description)"

    docker cp $LocalPath "${PgContainer}:/tmp/${filename}" | Out-Null

    docker exec -i $PgContainer psql -U aps -d household `
        -v ON_ERROR_STOP=1 `
        -f "/tmp/${filename}" *> $null

    if ($LASTEXITCODE -ne 0) {
        Die "Ошибка применения $filename"
    }

    Write-Ok "$filename применён"
}

# 3.1. Схема (v4.9.0)
Write-Step "Применение схемы БД"
Apply-Sql "backend\init_schema_v4.9.sql" "полная схема v4.9.0"

# 3.2. Seed-статьи справки
Write-Step "Применение seed-статей справки"
Apply-Sql "backend\init_schema_v4.9_seed.sql" "31 статья + 8 подсказок"

# 3.3. Демо-данные
Write-Step "Применение демо-данных"
if (Test-Path "backend\seed_demo_data.sql") {
    Apply-Sql "backend\seed_demo_data.sql" "демо-оборудование, партии, заказы"
} else {
    Write-Warn "backend\seed_demo_data.sql не найден — пропускаю"
}

# ==========================================
# 4. СОЗДАНИЕ АДМИНИСТРАТОРА
# ==========================================
if ($BackendAvailable) {
    Write-Step "Создание администратора"

    $adminCount = (docker exec -i $PgContainer psql -U aps -d household -tAc `
        "SELECT COUNT(*) FROM app_user WHERE role = 'ADMIN';").Trim()

    if ($adminCount -eq "0") {
        Write-Info "Админ не найден — создаю (admin@household.ru / admin123)"
        docker exec -i $BackendContainer python -m scripts.create_admin_user
        if ($LASTEXITCODE -ne 0) {
            Write-Warn "Ошибка создания администратора (см. логи backend)"
        } else {
            Write-Ok "Администратор создан"
        }
    } else {
        Write-Warn "Администратор уже существует ($adminCount). Пропускаю."
    }
}

# ==========================================
# 5. СВОДНАЯ ПРОВЕРКА
# ==========================================
Write-Step "Сводная проверка"

function Psql-Q {
    param([string]$Query)
    $result = docker exec -i $PgContainer psql -U aps -d household -tAc $Query
    return $result.Trim()
}

# Проверка ключевых таблиц
foreach ($table in @("plan_settings", "help_article", "help_hint", "audit_saved_view")) {
    $exists = Psql-Q "SELECT to_regclass('public.$table') IS NOT NULL;"
    if ($exists -eq "t") {
        Write-Ok "Таблица '$table' есть"
    } else {
        Write-Err "Таблица '$table' ОТСУТСТВУЕТ"
    }
}

# Счётчики
$articles = Psql-Q "SELECT COUNT(*) FROM help_article WHERE is_published = TRUE;"
$hints    = Psql-Q "SELECT COUNT(*) FROM help_hint WHERE is_published = TRUE;"
$faq      = Psql-Q "SELECT COUNT(*) FROM help_article WHERE category = 'faq';"
$settings = Psql-Q "SELECT COUNT(*) FROM app_settings WHERE organization_id = '00000000-0000-0000-0000-000000000001';"
$equip    = Psql-Q "SELECT COUNT(*) FROM equipment;"
$batches  = Psql-Q "SELECT COUNT(*) FROM batch;"

Write-Info "help_article (опубликовано):  $articles   (ожидаемо: 31)"
Write-Info "help_hint (опубликовано):     $hints   (ожидаемо: 8)"
Write-Info "FAQ-статей:                   $faq   (ожидаемо: 15)"
Write-Info "app_settings:                 $settings   (ожидаемо: 45+)"
Write-Info "Оборудования:                 $equip"
Write-Info "Партий:                       $batches"

# Версия API (если backend доступен)
if ($BackendAvailable) {
    try {
        $health = Invoke-RestMethod -Uri "http://localhost/health" -TimeoutSec 5
        Write-Info "API version:                  $($health.version)   (ожидаемо: 4.9.0)"
    } catch {
        Write-Warn "Не удалось получить /health"
    }
}

# ==========================================
# 6. ИТОГ
# ==========================================
Write-Host ""
Write-Host "=========================================================" -ForegroundColor Green
Write-Host "  OK  Инициализация завершена успешно" -ForegroundColor Green
Write-Host "=========================================================" -ForegroundColor Green
Write-Host ""

# Определение IP хоста (для облака/локальной VM)
$hostIp = "localhost"
try {
    $hostIp = (Get-NetIPAddress -AddressFamily IPv4 |
            Where-Object { $_.IPAddress -notmatch '^127\.' -and $_.PrefixOrigin -ne 'WellKnown' } |
            Select-Object -First 1 -ExpandProperty IPAddress)
} catch {
    # fallback на localhost
}

Write-Host "  Frontend:  http://${hostIp}/"
Write-Host "  Swagger:   http://${hostIp}/docs"
Write-Host "  Health:    http://${hostIp}/health"
Write-Host ""
Write-Host "  Логин:     admin@household.ru"
Write-Host "  Пароль:    admin123"
Write-Host "  ! Смените пароль после первого входа!" -ForegroundColor Yellow
Write-Host ""
Write-Info "Проверить логи: docker compose -f $ComposeFile logs -f backend"