# backend/tests/test_plan_settings_models.py
"""
Тесты Pydantic-моделей мастера настроек плана (Итерация 13.14).

Все тесты быстрые, БЕЗ БД.
Проверяют контракты API-моделей и их валидацию.

Итерация 13.14.1: settings имеет default_factory=dict — модель
позволяет обновлять только метаданные без settings.
"""

import pytest
from pydantic import ValidationError

from app.api.v1.plan_settings import PlanSettingsUpdateRequest


# ==========================================
# PlanSettingsUpdateRequest
# ==========================================

def test_update_request_minimal():
    """Минимальный запрос — только settings."""
    req = PlanSettingsUpdateRequest(settings={"horizon_hours": 720})
    assert req.settings["horizon_hours"] == 720


def test_update_request_empty_settings():
    """Пустой словарь settings — валиден (просто ничего не обновится)."""
    req = PlanSettingsUpdateRequest(settings={})
    assert req.settings == {}


def test_update_request_no_args_is_valid():
    """
    PlanSettingsUpdateRequest() без аргументов валиден.

    Итерация 13.14.1: settings имеет default_factory=dict — это
    by design, чтобы можно было обновлять только метаданные
    (name/comment/version_type), не передавая настройки.

    Раньше (до 13.14.1) этот тест ожидал ValidationError, но
    модель изменилась. Тест обновлён под реальное поведение.
    """
    req = PlanSettingsUpdateRequest()
    assert req.settings == {}
    assert req.name is None
    assert req.comment is None
    assert req.version_type is None


def test_update_request_only_metadata():
    """Обновление только метаданных, без settings."""
    req = PlanSettingsUpdateRequest(name="Новое имя плана")
    assert req.settings == {}
    assert req.name == "Новое имя плана"
    assert req.comment is None
    assert req.version_type is None


def test_update_request_only_comment():
    """Обновление только комментария."""
    req = PlanSettingsUpdateRequest(comment="Обновлённый комментарий")
    assert req.comment == "Обновлённый комментарий"
    assert req.name is None


def test_update_request_multiple_settings():
    """Несколько настроек разных типов."""
    req = PlanSettingsUpdateRequest(settings={
        "horizon_hours": 720,
        "weight_makespan": 1.0,
        "enable_cooling_degradation": True,
        "shift_mode": "3x8",
    })
    assert len(req.settings) == 4
    assert req.settings["shift_mode"] == "3x8"


def test_update_request_accepts_nested_json():
    """Вложенные структуры (например, shift_intervals)."""
    req = PlanSettingsUpdateRequest(settings={
        "shift_intervals": [
            {"start": "08:00", "end": "20:00"},
            {"start": "20:00", "end": "08:00"},
        ],
    })
    assert isinstance(req.settings["shift_intervals"], list)
    assert len(req.settings["shift_intervals"]) == 2


def test_update_request_accepts_null_value():
    """Null-значение допустимо (означает "сбросить")."""
    req = PlanSettingsUpdateRequest(settings={"cz_api_key": None})
    assert req.settings["cz_api_key"] is None


def test_update_request_name_short_rejected():
    """Слишком короткое имя — ошибка валидации (min_length=1)."""
    with pytest.raises(ValidationError):
        PlanSettingsUpdateRequest(name="")


def test_update_request_version_type_any_string():
    """version_type принимает строку (валидация — на уровне API)."""
    req = PlanSettingsUpdateRequest(version_type="MONTHLY")
    assert req.version_type == "MONTHLY"


# ==========================================
# Общие sanity-checks
# ==========================================

def test_update_request_serialization():
    """model_dump возвращает корректную структуру."""
    req = PlanSettingsUpdateRequest(settings={"horizon_hours": 720})
    dumped = req.model_dump()
    assert "settings" in dumped
    assert dumped["settings"] == {"horizon_hours": 720}
    assert "name" in dumped
    assert "comment" in dumped
    assert "version_type" in dumped


def test_update_request_from_json_dict():
    """model_validate принимает словарь (как из HTTP-запроса)."""
    req = PlanSettingsUpdateRequest.model_validate({
        "settings": {"timeout_seconds": 900},
    })
    assert req.settings["timeout_seconds"] == 900


def test_update_request_from_json_with_metadata():
    """model_validate с метаданными."""
    req = PlanSettingsUpdateRequest.model_validate({
        "settings": {"horizon_hours": 1440},
        "name": "Обновлённый план",
        "comment": "Комментарий",
        "version_type": "SHIFT",
    })
    assert req.settings["horizon_hours"] == 1440
    assert req.name == "Обновлённый план"
    assert req.comment == "Комментарий"
    assert req.version_type == "SHIFT"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])