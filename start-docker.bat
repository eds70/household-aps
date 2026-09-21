@echo off
setlocal
chcp 65001 >nul

title APS Production Scheduler (Docker)

echo ============================================================
echo  APS Production Scheduler - Docker
echo ============================================================
echo.

REM Removing standalone containers so ports/names do not clash
for %%C in (aps_postgres aps_backend aps_frontend) do (
    docker rm -f %%C >nul 2>&1
)

echo Building and starting containers (first run may take a few minutes)...
docker compose -f "%~dp0docker\docker-compose.yml" up -d --build

if errorlevel 1 (
    echo.
    echo [!] Failed. Check that Docker Desktop is running.
    pause
    exit /b 1
)

echo.
echo  Application:    http://localhost:5173
echo  Swagger:        http://localhost:5173/docs
echo  PostgreSQL:     localhost:5433 (aps / aps_secret / household)
echo.
echo  Demo login:     admin@household.ru / admin123
echo.
echo  Stop:           stop-docker.bat
echo.
pause