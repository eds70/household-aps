# backend/run_tests.ps1
# ==========================================
# Запуск pytest с корректной кириллицей на Windows.
#
# Использование:
#   .\run_tests.ps1                     # все тесты
#   .\run_tests.ps1 tests/test_help.py  # конкретный файл
#   .\run_tests.ps1 -k "help" -v        # с фильтром
#   .\run_tests.ps1 -Coverage           # с покрытием
# ==========================================

param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PytestArgs,

    [switch]$Coverage
)

# --- 1. Кодовая страница консоли → UTF-8 ---
chcp 65001 | Out-Null

# --- 2. Переменные окружения Python ---
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8       = "1"        # PEP 540 UTF-8 mode (Python 3.7+)
$env:PYTHONLEGACYWINDOWSSTDIO = "0"

# --- 3. (опционально) отключить буферизацию ---
$env:PYTHONUNBUFFERED = "1"

# --- 4. Активировать venv, если он есть ---
$venvActivate = Join-Path $PSScriptRoot ".venv\Scripts\Activate.ps1"
if (Test-Path $venvActivate) {
    Write-Host "🐍 Активация venv: $venvActivate" -ForegroundColor Cyan
    & $venvActivate
}

# --- 5. Собрать аргументы pytest ---
$pytestArgsList = @()
if ($Coverage) {
    $pytestArgsList += "--cov=app", "--cov-report=term-missing"
}

if ($PytestArgs) {
    $pytestArgsList += $PytestArgs
} else {
    $pytestArgsList += "tests/", "-v"
}

# --- 6. Запустить pytest ---
Write-Host "🧪 pytest $($pytestArgsList -join ' ')" -ForegroundColor Cyan
& python -m pytest @pytestArgsList

# --- 7. Прокинуть exit code ---
exit $LASTEXITCODE