@echo off
setlocal
chcp 65001 >nul

title APS Production Scheduler (Docker stop)

echo Stopping APS Docker containers...
docker compose -f "%~dp0docker\docker-compose.yml" down

echo.
echo Done. Data volume (pgdata) is preserved.
echo To delete all data: docker compose -f "%~dp0docker\docker-compose.yml" down -v
pause