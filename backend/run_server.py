import uvicorn

if __name__ == "__main__":
    print("🚀 Запуск APS Production Scheduler API...")
    print("📖 Swagger UI: http://localhost:8000/docs")
    print("❤️  Health: http://localhost:8000/health")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
