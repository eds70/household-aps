# backend/app/auth/dependencies.py
"""
FastAPI dependencies для работы с авторизацией.

Содержит:
- get_current_user: извлечение данных пользователя из JWT токена
- get_current_org_id: получение ID организации из токена
- get_current_user_id: получение ID пользователя из токена
- require_admin: проверка роли администратора
- get_db_session: централизованное получение сессии БД

Все зависимости используют request.state для передачи данных между слоями.
"""

from fastapi import Request, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from uuid import UUID
from typing import Optional
from app.auth.security import decode_token
from app.core.config import settings

# ==========================================
# Схема безопасности Bearer Token
# ==========================================
# Автоматически извлекает токен из заголовка Authorization: Bearer <token>
security = HTTPBearer()


# ==========================================
# Dependency: Получение текущего пользователя
# ==========================================
async def get_current_user(
        request: Request,
        credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    Извлекает и валидирует JWT токен из заголовка Authorization.

    Сохраняет данные пользователя в request.state для использования
    в других dependencies и эндпоинтах.

    Args:
        request: HTTP запрос
        credentials: Bearer токен (автоматически извлекается FastAPI)

    Returns:
        Словарь с данными пользователя:
        {
            "user_id": str,
            "org_id": str,
            "role": str,
            "email": str
        }

    Raises:
        HTTPException 401: Если токен отсутствует, невалиден или истёк
    """
    token = credentials.credentials

    try:
        # Декодируем и валидируем токен
        payload = decode_token(token)

        # Извлекаем данные из payload
        user_id = payload.get("sub")
        org_id = payload.get("org_id")
        role = payload.get("role")
        email = payload.get("email")

        # Проверяем наличие обязательных полей
        if not user_id or not org_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Невалидный токен: отсутствуют обязательные данные (user_id или org_id)",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Сохраняем в request.state для использования в других dependencies
        request.state.current_user_id = user_id
        request.state.current_org_id = org_id
        request.state.current_role = role
        request.state.current_email = email

        return {
            "user_id": user_id,
            "org_id": org_id,
            "role": role,
            "email": email,
        }

    except HTTPException:
        # Пробрасываем HTTPException как есть
        raise
    except Exception as e:
        # Любые другие ошибки (например, истёкший токен)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Ошибка авторизации: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ==========================================
# Dependency: Получение ID организации
# ==========================================
async def get_current_org_id(
        request: Request,
        current_user: dict = Depends(get_current_user)
) -> UUID:
    """
    Dependency для получения ID текущей организации из JWT токена.

    Используется во всех эндпоинтах вместо захардкоженного ORG_ID.
    Автоматически вызывает get_current_user для валидации токена.

    Args:
        request: HTTP запрос
        current_user: Данные пользователя из токена (автоматически)

    Returns:
        UUID организации

    Raises:
        HTTPException 401: Если org_id не найден в токене
    """
    org_id = request.state.current_org_id

    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Organization ID не найден в токене",
        )

    return UUID(org_id)


# ==========================================
# Dependency: Получение ID пользователя
# ==========================================
async def get_current_user_id(
        request: Request,
        current_user: dict = Depends(get_current_user)
) -> UUID:
    """
    Dependency для получения ID текущего пользователя из JWT токена.

    Args:
        request: HTTP запрос
        current_user: Данные пользователя из токена (автоматически)

    Returns:
        UUID пользователя

    Raises:
        HTTPException 401: Если user_id не найден в токене
    """
    user_id = request.state.current_user_id

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User ID не найден в токене",
        )

    return UUID(user_id)


# ==========================================
# Dependency: Проверка роли администратора
# ==========================================
async def require_admin(
        current_user: dict = Depends(get_current_user)
) -> dict:
    """
    Dependency для проверки роли администратора.

    Используется в эндпоинтах, доступных только администраторам:
    - Управление пользователями
    - Изменение настроек организации
    - Просмотр логов

    Args:
        current_user: Данные пользователя из токена (автоматически)

    Returns:
        Словарь с данными пользователя (если роль ADMIN)

    Raises:
        HTTPException 403: Если роль не ADMIN
    """
    if current_user.get("role") != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ запрещен. Требуется роль ADMIN",
        )

    return current_user


# ==========================================
# Dependency: Проверка конкретной роли
# ==========================================
async def require_role(
        role: str,
        current_user: dict = Depends(get_current_user)
) -> dict:
    """
    Dependency для проверки конкретной роли пользователя.

    Используется как:
        @router.get("/admin-only")
        async def admin_endpoint(user=Depends(lambda: require_role("ADMIN"))):
            ...

    Args:
        role: Требуемая роль (ADMIN, PLANNER, MASTER, LAB, VIEWER)
        current_user: Данные пользователя из токена (автоматически)

    Returns:
        Словарь с данными пользователя (если роль совпадает)

    Raises:
        HTTPException 403: Если роль не совпадает
    """
    allowed_roles = {"ADMIN", "PLANNER", "MASTER", "LAB", "VIEWER"}

    if role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Недопустимая роль в проверке: {role}",
        )

    if current_user.get("role") != role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Доступ запрещен. Требуется роль {role}",
        )

    return current_user


# ==========================================
# Dependency: Получение сессии БД
# ==========================================
# Создаём engine и sessionmaker один раз при импорте модуля
_engine = create_async_engine(settings.DATABASE_URL, echo=False)
_async_session = sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


async def get_db_session() -> AsyncSession:
    """
    Dependency для получения асинхронной сессии БД.

    Использует контекстный менеджер для автоматического закрытия сессии
    после выполнения запроса.

    Yields:
        AsyncSession: Асинхронная сессия SQLAlchemy

    Example:
        @router.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db_session)):
            result = await db.execute(text("SELECT * FROM items"))
            return result.fetchall()
    """
    async with _async_session() as session:
        try:
            yield session
        finally:
            await session.close()


# ==========================================
# Dependency: Опциональный пользователь
# ==========================================
async def get_optional_user(
        request: Request,
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
) -> Optional[dict]:
    """
    Dependency для получения пользователя, если токен предоставлен.

    В отличие от get_current_user, не выбрасывает ошибку при отсутствии токена.
    Используется в эндпоинтах, которые работают как для авторизованных,
    так и для неавторизованных пользователей.

    Args:
        request: HTTP запрос
        credentials: Bearer токен (опционально)

    Returns:
        Словарь с данными пользователя или None
    """
    if not credentials:
        return None

    try:
        payload = decode_token(credentials.credentials)

        user_id = payload.get("sub")
        org_id = payload.get("org_id")
        role = payload.get("role")
        email = payload.get("email")

        if user_id and org_id:
            request.state.current_user_id = user_id
            request.state.current_org_id = org_id
            request.state.current_role = role
            request.state.current_email = email

            return {
                "user_id": user_id,
                "org_id": org_id,
                "role": role,
                "email": email,
            }
    except Exception:
        # Токен невалиден, но это не ошибка - просто возвращаем None
        pass

    return None