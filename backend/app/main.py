# backend/app/main.py
import logging
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1.advisor import router as advisor_router
from app.api.v1.audit import router as audit_router
from app.api.v1.auth import router as auth_router
from app.api.v1.calendar import router as calendar_router
from app.api.v1.cz import router as cz_router
from app.api.v1.equipment import router as equipment_router
from app.api.v1.gantt import router as gantt_router
from app.api.v1.help import router as help_router
from app.api.v1.help_docs import router as help_docs_router
from app.api.v1.lab import router as lab_router
from app.api.v1.license import router as license_router
from app.api.v1.materials import router as materials_router
from app.api.v1.operations import router as operations_router
from app.api.v1.orders import router as orders_router
from app.api.v1.personnel import router as personnel_router
from app.api.v1.plan_settings import router as plan_settings_router
from app.api.v1.products import router as products_router
from app.api.v1.recipes import router as recipes_router
from app.api.v1.reschedule import router as reschedule_router
from app.api.v1.schedule import router as schedule_router
from app.api.v1.settings import router as settings_router
from app.api.v1.shift import router as shift_router
from app.api.v1.whatif import router as whatif_router
from app.core.config import settings
from app.core.license import (
    PUBLIC_PATH_PREFIXES,
    LicenseError,
    LicenseInfo,
    get_or_create_instance_id,
    verify_license,
)
from app.scheduler.logging_config import setup_scheduler_logging

APP_VERSION = "4.9.1"

logger = setup_scheduler_logging(level=logging.INFO)

tags_metadata = [
    {"name": "Авторизация"},
    {"name": "Планирование"},
    {"name": "Диаграмма Ганта"},
    {"name": "Оборудование"},
    {"name": "Продукты"},
    {"name": "Технологические карты"},
    {"name": "Календарь простоев"},
    {"name": "Материалы"},
    {"name": "Рецептуры"},
    {"name": "Производственные заказы"},
    {"name": "Advisor"},
    {"name": "Сменное планирование"},
    {"name": "Перепланирование"},
    {"name": "Лаборатория"},
    {"name": "Персонал"},
    {"name": "Честный Знак"},
    {"name": "Настройки"},
    {"name": "Настройки плана"},
    {"name": "What-if сценарии"},
    {"name": "Аудит"},
    {"name": "Справка"},
    {"name": "Лицензия"},
    {"name": "Система"},
]

app = FastAPI(
    title="APS Production Scheduler",
    description=(
        "REST API для построения оптимальных планов производства "
        "с использованием OR-Tools CP-SAT."
    ),
    version=APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=tags_metadata,
    debug=True,
)


# ==========================================
# MIDDLEWARE: LicenseMiddleware
# ==========================================
#
# ВАЖНО (порядок middleware в Starlette):
#   Последний добавленный через add_middleware выполняется ПЕРВЫМ.
#   Поэтому здесь порядок такой:
#     1) LicenseMiddleware  — добавлен раньше → выполняется позже
#     2) CORSMiddleware     — добавлен позже  → выполняется раньше
#
#   Это нужно, чтобы 403 от LicenseMiddleware уходил с CORS-заголовками,
#   иначе браузер показывает «CORS policy blocked» вместо честного 403.

class LicenseMiddleware(BaseHTTPMiddleware):
    """
    Проверяет валидность лицензии для всех запросов, кроме публичных.

    Логика:
      - OPTIONS-запросы (CORS preflight) — всегда пропускаются.
      - Если LICENSE_VERIFY=false → middleware ничего не делает.
      - Если LICENSE_VERIFY=true:
        - Публичные пути (PUBLIC_PATH_PREFIXES) — пропускаются.
        - Всё остальное — проверяется app.state.license_info.
          Если None → 403 «Лицензия недействительна».
    """

    async def dispatch(self, request: Request, call_next):
        # 1. CORS preflight — всегда пропускаем.
        #    Preflight не содержит credentials и не должен требовать лицензии.
        #    Его обработает CORSMiddleware (зарегистрирован «выше»).
        if request.method == "OPTIONS":
            return await call_next(request)

        # 2. Если верификация отключена — пропускаем всё
        if not settings.LICENSE_VERIFY:
            return await call_next(request)

        # 3. Публичные пути — пропускаем
        path = request.url.path
        for prefix in PUBLIC_PATH_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        # 4. Проверка лицензии
        license_info: Optional[LicenseInfo] = getattr(
            request.app.state, "license_info", None
        )
        license_error: Optional[str] = getattr(
            request.app.state, "license_error", None
        )

        if license_info is None or license_info.is_expired:
            detail: dict = {
                "code": "LICENSE_INVALID",
                "message": license_error or "Лицензия недействительна",
            }
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": detail},
            )

        return await call_next(request)


# Порядок регистрации: LicenseMiddleware первым в коде → выполняется последним.
# CORSMiddleware добавляется СЛЕДУЮЩИМ, значит выполняется ПЕРВЫМ и успевает
# обернуть ответ LicenseMiddleware в CORS-заголовки.
app.add_middleware(LicenseMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================
# STARTUP: загрузка и проверка лицензии
# ==========================================

@app.on_event("startup")
async def load_license_on_startup() -> None:
    """
    Проверяет лицензию при старте backend.

    Сохраняет результат в app.state:
      - license_info: LicenseInfo | None (валидная лицензия)
      - license_error: str | None (текст ошибки для UI)
      - instance_id: str (текущий instance_id сервера)

    Поведение:
      - LICENSE_VERIFY=false → пропуск, всё работает.
      - LICENSE_VERIFY=true, LICENSE_KEY задан → проверка.
      - LICENSE_VERIFY=true, LICENSE_KEY не задан → ошибка, но приложение
        стартует (мягкая блокировка).

    Никогда не бросает исключение — приложение должно стартовать,
    даже если лицензия невалидна. UI покажет ошибку через /license/info.

    Выбор алгоритма проверки подписи:
      1. Если задан LICENSE_PUBLIC_KEY — используется RS256/ES256
         (асимметричный, публичный ключ вендора).
      2. Иначе, если задан LICENSE_MASTER_SECRET — используется HS256
         (симметричный, только для локальной разработки).
      3. Если ни один не задан — лицензию проверить невозможно,
         приложение работает в мягкой блокировке.

    Приоритет: LICENSE_PUBLIC_KEY важнее LICENSE_MASTER_SECRET.
    Если в .env заданы оба — используется публичный ключ (RS256),
    а мастер-секрет игнорируется. Это защищает от конфигурации,
    когда разработчик добавил публичный ключ, но забыл убрать
    старый мастер-секрет (или наоборот — продакшен с dev-секретом).
    """
    # Инициализируем дефолтные значения
    app.state.license_info = None
    app.state.license_error = None

    # Всегда вычисляем instance_id (нужен для /license/instance)
    try:
        app.state.instance_id = get_or_create_instance_id()
        logger.info(
            f"[license] instance_id: {app.state.instance_id[:16]}..."
        )
    except Exception as e:
        logger.error(f"[license] Не удалось вычислить instance_id: {e}")
        app.state.instance_id = None

    # Если верификация отключена — всё
    if not settings.LICENSE_VERIFY:
        logger.warning(
            "[license] LICENSE_VERIFY=false — проверка лицензии отключена. "
            "Не использовать в production!"
        )
        return

    # Если ключ не задан — мягкая блокировка
    if not settings.LICENSE_KEY:
        logger.warning(
            "[license] LICENSE_KEY не задан, а LICENSE_VERIFY=true. "
            "Приложение работает в режиме мягкой блокировки: "
            "защищённые эндпоинты вернут 403. "
            "Получите лицензию и добавьте её в .env."
        )
        app.state.license_error = (
            "LICENSE_KEY не задан. Обратитесь к вендору для получения лицензии."
        )
        return

    # ==========================================
    # Выбор ключа и алгоритма для проверки подписи
    # ==========================================
    if settings.LICENSE_PUBLIC_KEY:
        # Продакшен: асимметричная подпись, публичный ключ вендора.
        # Алгоритм задаётся здесь явно. Если в JWT подписан другим
        # алгоритмом (например, ES256 вместо RS256) — verify_license
        # бросит LicenseInvalidError, что правильно: клиент должен
        # получить от вендора лицензию под тот алгоритм, который
        # объявлен в LICENSE_PUBLIC_KEY.
        verify_key = settings.LICENSE_PUBLIC_KEY
        verify_algorithm = "RS256"
        verify_mode = "RS256 (публичный ключ вендора)"
    elif settings.LICENSE_MASTER_SECRET:
        # Dev: симметричная подпись, тот же секрет, что и при подписи.
        verify_key = settings.LICENSE_MASTER_SECRET
        verify_algorithm = "HS256"
        verify_mode = "HS256 (мастер-секрет — только для dev!)"
    else:
        logger.error(
            "[license] LICENSE_KEY задан, но не указан ни "
            "LICENSE_PUBLIC_KEY (RS256/ES256), ни LICENSE_MASTER_SECRET (HS256). "
            "Проверить подпись лицензии невозможно."
        )
        app.state.license_error = (
            "Не задан ключ для проверки подписи лицензии. "
            "Обратитесь к вендору."
        )
        return

    logger.info(f"[license] Режим проверки: {verify_mode}")

    # Проверка лицензии
    try:
        info = verify_license(
            key=settings.LICENSE_KEY,
            secret=verify_key,
            expected_instance_id=app.state.instance_id,
            algorithm=verify_algorithm,
        )
        app.state.license_info = info
        app.state.license_error = None

        logger.info(
            f"[license] Лицензия валидна: "
            f"holder={info.holder!r}, "
            f"tier={info.tier}, "
            f"algorithm={info.algorithm or verify_algorithm}, "
            f"expires={info.expires_at.isoformat()}, "
            f"days_left={info.days_left}, "
            f"instance_bound={info.is_instance_bound}"
        )

        if info.days_left <= 14:
            logger.warning(
                f"[license] Лицензия истекает через {info.days_left} дн.! "
                f"Продлите её, чтобы избежать блокировки."
            )

    except LicenseError as e:
        app.state.license_info = None
        app.state.license_error = str(e)
        logger.error(f"[license] Проверка лицензии не прошла: {e}")
    except Exception as e:
        app.state.license_info = None
        app.state.license_error = f"Внутренняя ошибка проверки лицензии: {e}"
        logger.error(
            f"[license] Непредвиденная ошибка при проверке лицензии: {e}",
            exc_info=True,
        )


# ==========================================
# РОУТЕРЫ
# ==========================================

app.include_router(auth_router)
app.include_router(schedule_router)
app.include_router(gantt_router)
app.include_router(equipment_router)
app.include_router(products_router)
app.include_router(operations_router)
app.include_router(calendar_router)
app.include_router(materials_router)
app.include_router(recipes_router)
app.include_router(orders_router)
app.include_router(advisor_router)
app.include_router(shift_router)
app.include_router(reschedule_router)
app.include_router(lab_router)
app.include_router(personnel_router)
app.include_router(cz_router)
app.include_router(settings_router)
app.include_router(plan_settings_router)
app.include_router(whatif_router)
app.include_router(audit_router)
app.include_router(help_router)
app.include_router(help_docs_router)
app.include_router(license_router)


# ==========================================
# СИСТЕМНЫЕ ЭНДПОИНТЫ
# ==========================================

@app.get("/health", tags=["Система"])
async def health_check():
    """
    Health-check. Публичный (не требует лицензии).
    """
    return {
        "status": "healthy",
        "version": APP_VERSION,
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/", tags=["Система"])
async def root():
    """
    Корневой эндпоинт. Публичный.
    """
    return {
        "message": "APS Production Scheduler API",
        "version": APP_VERSION,
        "docs": "/docs",
        "auth": "/api/v1/auth/login",
    }