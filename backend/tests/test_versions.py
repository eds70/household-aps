# backend/tests/test_versions.py
"""
Тесты hotfix Итерации 5: деактивация старых версий + фильтрация по version_id.

ВАЖНО: FastAPI оборачивает функции-роутеры декоратором @router.get(...).
Поэтому inspect.getsource(module.get_shift_tasks) НЕ работает —
символа `get_shift_tasks` в модуле нет (его заменил wrapper).

Правильный подход — читать исходник МОДУЛЯ (файла) целиком
через inspect.getsource(module) и искать подстроки в тексте.
"""

import inspect

import pytest


# ==========================================
# ТЕСТЫ: SAавER ДЕАКТИВИРУЕТ СТАРЫЕ ВЕРСИИ
# ==========================================

def test_saver_deactivates_old_versions():
    """
    Проверяет, что в saver.py есть UPDATE schedule_version
    SET is_active = FALSE перед созданием новой версии.

    saver.py не использует FastAPI-декораторы, поэтому inspect.getsource
    метода работает.
    """
    from app.scheduler import saver as saver_module

    source = inspect.getsource(saver_module.ScheduleSaver.save_schedule)
    assert "UPDATE schedule_version" in source, (
        "saver.py должен деактивировать старые версии"
    )
    assert "SET is_active = FALSE" in source, (
        "saver.py должен ставить is_active = FALSE для старых версий"
    )
    assert "deactivated_versions" in source, (
        "saver.py должен возвращать счётчик деактивированных версий"
    )


# ==========================================
# ТЕСТЫ: SHIFT.PY ФИЛЬТРУЕТ ПО VERSION_ID
# ==========================================

def test_shift_has_resolve_version_id_helper():
    """Хелпер _resolve_version_id должен существовать в shift.py."""
    from app.api.v1 import shift as shift_module

    # Для роутеров FastAPI проверяем через getattr — _resolve_version_id
    # не обёрнут декоратором, поэтому он доступен напрямую.
    assert hasattr(shift_module, "_resolve_version_id"), (
        "shift.py должен содержать _resolve_version_id"
    )
    assert callable(shift_module._resolve_version_id)


def test_shift_module_has_version_filter():
    """
    Исходник модуля shift.py должен содержать фильтр по schedule_version_id.

    Мы читаем весь файл (inspect.getsource(module)) и ищем подстроки —
    это работает независимо от декораторов FastAPI.
    """
    from app.api.v1 import shift as shift_module

    source = inspect.getsource(shift_module)
    assert "schedule_version_id = :version_id" in source, (
        "shift.py должен фильтровать задачи по schedule_version_id"
    )
    # У нас ДВА места с фильтром (основной запрос + carryover внутри метода)
    assert source.count("schedule_version_id = :version_id") >= 2, (
        "И основной, и carryover-запрос должны фильтровать по version_id"
    )
    assert "resolved_version_id" in source, (
        "shift.py должен использовать resolved_version_id"
    )


def test_shift_module_has_resolve_version_calls():
    """Исходник shift.py должен вызывать _resolve_version_id."""
    from app.api.v1 import shift as shift_module

    source = inspect.getsource(shift_module)
    # Должно быть минимум 2 вызова — в get_shift_tasks и get_carryover
    assert source.count("await _resolve_version_id") >= 2, (
        "shift.py должен вызывать _resolve_version_id в get_shift_tasks и get_carryover"
    )


# ==========================================
# ТЕСТЫ: GANTT.PY ФИЛЬТРУЕТ ПО VERSION_ID
# ==========================================

def test_gantt_has_resolve_version_id_helper():
    """Хелпер _resolve_version_id должен существовать в gantt.py."""
    from app.api.v1 import gantt as gantt_module

    assert hasattr(gantt_module, "_resolve_version_id"), (
        "gantt.py должен содержать _resolve_version_id"
    )
    assert callable(gantt_module._resolve_version_id)


def test_gantt_module_uses_resolved_version():
    """
    Исходник gantt.py должен использовать resolved_version_id.
    """
    from app.api.v1 import gantt as gantt_module

    source = inspect.getsource(gantt_module)
    assert "resolved_version_id" in source, (
        "gantt.py должен использовать resolved_version_id"
    )
    assert "await _resolve_version_id" in source, (
        "gantt.py должен вызывать _resolve_version_id"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])