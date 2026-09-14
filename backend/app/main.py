# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from app.api.v1.schedule import router as schedule_router
from app.api.v1.gantt import router as gantt_router
from app.api.v1.equipment import router as equipment_router
from app.api.v1.products import router as products_router
from app.api.v1.operations import router as operations_router
from app.api.v1.calendar import router as calendar_router
from app.api.v1.materials import router as materials_router
from app.api.v1.recipes import router as recipes_router
from app.api.v1.orders import router as orders_router

app = FastAPI(
    title="APS Production Scheduler",
    description="REST API для построения оптимальных планов производства с использованием OR-Tools CP-SAT.",
    version="1.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(schedule_router)
app.include_router(gantt_router)
app.include_router(equipment_router)
app.include_router(products_router)
app.include_router(operations_router)
app.include_router(calendar_router)
app.include_router(materials_router)
app.include_router(recipes_router)
app.include_router(orders_router)


@app.get("/health", tags=["Система"])
async def health_check():
    return {
        "status": "healthy",
        "version": "1.1.0",
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/", tags=["Система"])
async def root():
    return {"message": "APS Production Scheduler API", "docs": "/docs"}