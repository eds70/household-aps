# backend/app/api/v1/help_docs.py
"""
Отдача файлов docs/*.md через API (Итерация 15.1).

Эндпоинт:
  GET /api/v1/help/docs/{filename} — вернуть содержимое docs/{filename}

Ограничения:
  - Разрешены только файлы .md.
  - Разрешены только файлы из docs/ (без ../).
  - Ограничение размера — 1 МБ.
"""
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import get_current_org_id

router = APIRouter(prefix="/api/v1/help/docs", tags=["Справка"])
logger = logging.getLogger("app.api.help_docs")

# ==========================================
# КОНСТАНТЫ
# ==========================================

# backend/app/api/v1/help_docs.py → backend/
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent.parent
_DOCS_DIR = _BACKEND_DIR.parent / "docs"

MAX_FILE_SIZE = 1024 * 1024  # 1 МБ


# ==========================================
# GET /docs/{filename}
# ==========================================

@router.get("/{filename}")
async def get_doc_file(
        filename: str,
        _org_id=Depends(get_current_org_id),
):
    """
    Возвращает содержимое файла docs/{filename}.

    Безопасность:
      - Имя файла должно заканчиваться на .md.
      - Имя файла не должно содержать /, \\, .. .
      - Файл должен существовать в docs/.
    """
    # 1. Валидация имени
    if not filename.endswith(".md"):
        raise HTTPException(
            status_code=400,
            detail="Разрешены только файлы .md",
        )

    if any(ch in filename for ch in ("/", "\\", "..")):
        raise HTTPException(
            status_code=400,
            detail="Недопустимое имя файла",
        )

    # 2. Проверка существования
    file_path = _DOCS_DIR / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"Файл docs/{filename} не найден",
        )

    # 3. Размер
    if file_path.stat().st_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"Файл docs/{filename} слишком большой (>1 МБ)",
        )

    # 4. Чтение
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.error(f"Ошибка чтения docs/{filename}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось прочитать файл: {e}",
        )

    return {
        "filename": filename,
        "content_md": content,
        "size": file_path.stat().st_size,
    }