# backend/app/main.py
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.advisor import router as advisor_router
from app.api.v1.audit import router as audit_router
from app.api.v1.auth import router as auth_router
from app.api.v1.calendar import router as calendar_router
from app.api.v1.cz import router as cz_router
from app.api.v1.equipment import router as equipment_router
from app.api.v1.gantt import router as gantt_router
from app.api.v1.lab import router as lab_router
from app.api.v1.materials import router as materials_router
from app.api.v1.operations import router as operations_router
from app.api.v1.orders import router as orders_router
from app.api.v1.personnel import router as personnel_router
from app.api.v1.plan_settings import router as plan_settings_router  # ← НОВОЕ
from app.api.v1.products import router as products_router
from app.api.v1.recipes import router as recipes_router
from app.api.v1.reschedule import router as reschedule_router
from app.api.v1.schedule import router as schedule_router
from app.api.v1.settings import router as settings_router
from app.api.v1.shift import router as shift_router
from app.api.v1.whatif import router as whatif_router
from app.core.config import settings

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
    {"name": "Настройки плана"},        # ← НОВОЕ
    {"name": "What-if сценарии"},
    {"name": "Аудит"},
    {"name": "Система"},
]

app = FastAPI(
    title="APS Production Scheduler",
    description=(
        "REST API для построения оптимальных планов производства "
        "с использованием OR-Tools CP-SAT."
    ),
    version="3.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=tags_metadata,
    debug=True,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
app.include_router(plan_settings_router)   # ← НОВОЕ
app.include_router(whatif_router)
app.include_router(audit_router)


@app.get("/health", tags=["Система"])
async def health_check():
    return {
        "status": "healthy",
        "version": "3.0.0",
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/", tags=["Система"])
async def root():
    return {
        "message": "APS Production Scheduler API",
        "docs": "/docs",
        "auth": "/api/v1/auth/login",
    }