# backend/app/api/v1/auth.py
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, get_db_session
from app.auth.models import (
    LoginRequest,
    TokenResponse,
    UserResponse,
    ChangePasswordRequest,
)
from app.auth.security import (
    verify_password_async,
    get_password_hash_async,
    create_access_token,
)

router = APIRouter(prefix="/api/v1/auth", tags=["Авторизация"])


@router.post("/login", response_model=TokenResponse)
async def login(
        request: LoginRequest,
        db: AsyncSession = Depends(get_db_session),
):
    """
    Авторизация пользователя по email и паролю.
    Возвращает JWT токен с данными пользователя и организации.
    """
    result = await db.execute(
        text("""
            SELECT id, organization_id, email, full_name, role, password_hash, is_active
            FROM app_user
            WHERE email = :email
        """),
        {"email": request.email},
    )
    user = result.fetchone()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Пользователь заблокирован",
        )

    if not user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # ✅ Async-версия bcrypt — не блокирует event loop
    is_valid = await verify_password_async(request.password, user.password_hash)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "org_id": str(user.organization_id),
            "role": user.role,
            "email": user.email,
        }
    )

    # Обновляем время последнего входа
    await db.execute(
        text("""
            UPDATE app_user
            SET last_login_at = NOW()
            WHERE id = :user_id
        """),
        {"user_id": user.id},
    )
    await db.commit()

    return TokenResponse(
        access_token=access_token,
        user_id=user.id,
        organization_id=user.organization_id,
        role=user.role,
        full_name=user.full_name,
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
        current_user: dict = Depends(get_current_user),
        db: AsyncSession = Depends(get_db_session),
):
    """
    Получение информации о текущем пользователе.
    """
    result = await db.execute(
        text("""
            SELECT id, email, full_name, role, organization_id, is_active, last_login_at
            FROM app_user
            WHERE id = :user_id
        """),
        {"user_id": current_user["user_id"]},
    )
    user = result.fetchone()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден",
        )

    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "organization_id": user.organization_id,
        "is_active": user.is_active,
        "last_login_at": user.last_login_at,
    }


@router.post("/change-password")
async def change_password(
        request: ChangePasswordRequest,
        current_user: dict = Depends(get_current_user),
        db: AsyncSession = Depends(get_db_session),
):
    """
    Смена пароля текущего пользователя.
    """
    result = await db.execute(
        text("SELECT password_hash FROM app_user WHERE id = :user_id"),
        {"user_id": current_user["user_id"]},
    )
    row = result.fetchone()

    if not row or not row.password_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный текущий пароль",
        )

    is_valid = await verify_password_async(request.old_password, row.password_hash)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный текущий пароль",
        )

    new_hash = await get_password_hash_async(request.new_password)
    await db.execute(
        text("""
            UPDATE app_user
            SET password_hash = :new_hash
            WHERE id = :user_id
        """),
        {"new_hash": new_hash, "user_id": current_user["user_id"]},
    )
    await db.commit()

    return {"message": "Пароль успешно изменен"}