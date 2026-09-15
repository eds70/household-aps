# backend/scripts/create_admin_user.py
"""
Скрипт для создания администратора с хешированным паролем.
Запуск: python -m scripts.create_admin_user
"""
import asyncio
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.auth.security import get_password_hash, create_access_token
from app.core.config import settings

ORG_ID = UUID("00000000-0000-0000-0000-000000000001")


async def create_admin_user():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        email = "admin@household.ru"
        password = "admin123"  # ⚠️ Смените в production!
        password_hash = get_password_hash(password)

        # Проверяем, существует ли пользователь
        result = await session.execute(
            text("SELECT id FROM app_user WHERE email = :email"),
            {"email": email}
        )
        existing = result.fetchone()

        if existing:
            # Обновляем пароль
            await session.execute(
                text("""
                    UPDATE app_user
                    SET password_hash = :password_hash, is_active = TRUE
                    WHERE email = :email
                """),
                {"password_hash": password_hash, "email": email}
            )
            user_id = existing.id
            print(f"✅ Пароль пользователя {email} обновлен")
        else:
            # Создаем нового пользователя
            result = await session.execute(
                text("""
                    INSERT INTO app_user
                    (organization_id, email, full_name, role, password_hash, is_active)
                    VALUES
                    (:org_id, :email, 'Администратор системы', 'ADMIN', :password_hash, TRUE)
                    RETURNING id
                """),
                {
                    "org_id": ORG_ID,
                    "email": email,
                    "password_hash": password_hash,
                }
            )
            user_id = result.scalar()
            print(f"✅ Пользователь {email} создан с ID: {user_id}")

        await session.commit()

        # Генерируем тестовый токен
        token = create_access_token(
            data={
                "sub": str(user_id),
                "org_id": str(ORG_ID),
                "role": "ADMIN",
                "email": email,
            }
        )
        print(f"\n🔑 Тестовый JWT токен:\n{token}")
        print(f"\n📝 Как использовать в Swagger UI:")
        print(f"   1. Откройте http://localhost:8000/docs")
        print(f"   2. Нажмите кнопку 'Authorize' сверху")
        print(f"   3. Введите: Bearer {token}")
        print(f"   4. Нажмите 'Authorize' и 'Close'")


if __name__ == "__main__":
    print("🚀 Создание/обновление пользователя admin@household.ru...")
    asyncio.run(create_admin_user())