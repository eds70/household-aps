# backend/tests/test_plan_settings_data_loader.py
"""
Тесты логики чтения настроек в DataLoader (Итерация 13.14).

Проверяют:
  1. Если version_id передан → читаем из plan_settings.
  2. Если version_id = None → читаем из app_settings.
  3. Если для версии нет plan_settings → fallback на app_settings.
  4. ProductionScheduler прокидывает version_id в DataLoader.

Тесты структурные (без БД) — используют mock-сессии.
"""
import inspect
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from app.scheduler.data_loader import DataLoader

TEST_ORG_ID = UUID("00000000-0000-0000-0000-000000000001")


# ==========================================
# 1. КОНСТРУКТОР
# ==========================================

def test_data_loader_accepts_version_id():
    """DataLoader.__init__ принимает version_id."""
    sig = inspect.signature(DataLoader.__init__)
    assert "version_id" in sig.parameters, (
        "DataLoader должен принимать version_id"
    )


def test_data_loader_version_id_default_none():
    """По умолчанию version_id = None."""
    sig = inspect.signature(DataLoader.__init__)
    param = sig.parameters["version_id"]
    assert param.default is None, (
        "version_id по умолчанию должен быть None (глобальные настройки)"
    )


def test_data_loader_stores_version_id():
    """version_id сохраняется в self.version_id."""
    vid = uuid4()
    loader = DataLoader(org_id=TEST_ORG_ID, version_id=vid)
    assert loader.version_id == vid


def test_data_loader_no_version_id():
    """Без version_id → self.version_id = None."""
    loader = DataLoader(org_id=TEST_ORG_ID)
    assert loader.version_id is None


# ==========================================
# 2. ЛОГИКА _load_app_settings
# ==========================================

def test_load_app_settings_signature():
    """_load_app_settings принимает session."""
    sig = inspect.signature(DataLoader._load_app_settings)
    assert "session" in sig.parameters


def test_load_app_settings_uses_plan_settings_when_version_id():
    """Исходник _load_app_settings содержит ветку с plan_settings."""
    src = inspect.getsource(DataLoader._load_app_settings)
    assert "plan_settings" in src, (
        "_load_app_settings должен читать из plan_settings при version_id"
    )
    assert "self.version_id" in src, (
        "Должна быть проверка self.version_id"
    )


def test_load_app_settings_has_fallback():
    """Есть fallback на app_settings, если plan_settings пустые."""
    src = inspect.getsource(DataLoader._load_app_settings)
    assert "app_settings" in src, (
        "Должен быть fallback на app_settings"
    )
    assert "if settings_dict" in src or "if not settings_dict" in src, (
        "Должна быть проверка пустого результата для fallback"
    )


@pytest.mark.asyncio
async def test_load_app_settings_queries_plan_settings_with_version():
    """
    При version_id SQL-запрос идёт в plan_settings
    с фильтром по schedule_version_id.
    """
    vid = uuid4()
    loader = DataLoader(org_id=TEST_ORG_ID, version_id=vid)

    session = AsyncMock()

    mock_result = MagicMock()
    mock_result.fetchall.return_value = [
        MagicMock(setting_key="horizon_hours", setting_value=720),
        MagicMock(setting_key="shift_mode", setting_value="3x8"),
    ]
    session.execute.return_value = mock_result

    result = await loader._load_app_settings(session)

    assert session.execute.called
    call_args = session.execute.call_args
    sql_text = str(call_args[0][0])
    assert "plan_settings" in sql_text, (
        f"SQL должен содержать plan_settings, получено: {sql_text}"
    )
    assert "schedule_version_id" in sql_text
    params = call_args[0][1]
    assert params["version_id"] == vid

    assert result["horizon_hours"] == 720
    assert result["shift_mode"] == "3x8"


@pytest.mark.asyncio
async def test_load_app_settings_falls_back_to_app_settings():
    """
    Если plan_settings пуст — читаем из app_settings.
    """
    vid = uuid4()
    loader = DataLoader(org_id=TEST_ORG_ID, version_id=vid)

    session = AsyncMock()

    empty_result = MagicMock()
    empty_result.fetchall.return_value = []

    global_result = MagicMock()
    global_result.fetchall.return_value = [
        MagicMock(setting_key="horizon_hours", setting_value=600),
    ]

    session.execute.side_effect = [empty_result, global_result]

    result = await loader._load_app_settings(session)

    assert session.execute.call_count == 2

    first_sql = str(session.execute.call_args_list[0][0][0])
    assert "plan_settings" in first_sql

    second_sql = str(session.execute.call_args_list[1][0][0])
    assert "app_settings" in second_sql

    assert result["horizon_hours"] == 600


@pytest.mark.asyncio
async def test_load_app_settings_without_version_uses_app_settings():
    """
    Без version_id сразу читаем app_settings (один запрос).
    """
    loader = DataLoader(org_id=TEST_ORG_ID, version_id=None)

    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [
        MagicMock(setting_key="horizon_hours", setting_value=720),
    ]
    session.execute.return_value = mock_result

    result = await loader._load_app_settings(session)

    assert session.execute.call_count == 1

    sql_text = str(session.execute.call_args[0][0])
    assert "app_settings" in sql_text
    assert "plan_settings" not in sql_text, (
        "Без version_id не должно быть обращения к plan_settings"
    )

    assert result["horizon_hours"] == 720


# ==========================================
# 3. PRODUCTION SCHEDULER
# ==========================================

def test_production_scheduler_accepts_version_id():
    """ProductionScheduler.__init__ принимает version_id."""
    from app.scheduler.core import ProductionScheduler
    sig = inspect.signature(ProductionScheduler.__init__)
    assert "version_id" in sig.parameters


def test_production_scheduler_passes_version_id_to_loader():
    """ProductionScheduler передаёт version_id в DataLoader."""
    from app.scheduler.core import ProductionScheduler
    src = inspect.getsource(ProductionScheduler.__init__)
    assert "version_id" in src
    assert "DataLoader" in src
    assert "version_id=version_id" in src, (
        "version_id должен передаваться в DataLoader"
    )


def test_production_scheduler_version_id_optional():
    """version_id — необязательный параметр."""
    from app.scheduler.core import ProductionScheduler
    sig = inspect.signature(ProductionScheduler.__init__)
    param = sig.parameters["version_id"]
    assert param.default is None


# ==========================================
# 4. SANITY
# ==========================================

def test_load_all_calls_load_app_settings():
    """_load_all_with_session вызывает _load_app_settings."""
    src = inspect.getsource(DataLoader._load_all_with_session)
    assert "_load_app_settings" in src
    assert "org_settings" in src


if __name__ == "__main__":
    pytest.main([__file__, "-v"])