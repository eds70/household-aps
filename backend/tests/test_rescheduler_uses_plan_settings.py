# backend/tests/test_rescheduler_uses_plan_settings.py
"""
Тесты Итерации 13.14: rescheduler читает настройки из plan_settings.

Проверяют:
  1. Что Rescheduler.reschedule() передаёт version_id в ProductionScheduler.
  2. Что это делается и в основном вызове, и в fallback.
  3. Что Rescheduler не использует глобальные app_settings
     (нет прямых SQL-запросов к app_settings в коде reschedule).

Все тесты структурные — читают исходник через inspect.getsource.
БД не требуется.
"""
import inspect

import pytest

from app.scheduler import rescheduler as rescheduler_module
from app.scheduler.rescheduler import Rescheduler


# ==========================================
# 1. ОСНОВНОЙ ВЫЗОВ PRODUCTION SCHEDULER
# ==========================================

def test_reschedule_passes_version_id_to_scheduler():
    """
    reschedule() должен передавать version_id=from_version_id
    в ProductionScheduler.
    """
    src = inspect.getsource(Rescheduler.reschedule)

    assert "ProductionScheduler(" in src, (
        "reschedule() должен создавать ProductionScheduler"
    )
    assert "version_id=from_version_id" in src, (
        "reschedule() должен передавать version_id=from_version_id "
        "в ProductionScheduler (Итерация 13.14)"
    )


def test_reschedule_passes_version_id_in_fallback():
    """
    В fallback-ветке (scheduler2) тоже должен передаваться version_id.
    Иначе fallback будет считать без plan_settings.
    """
    src = inspect.getsource(Rescheduler.reschedule)

    # Должно быть минимум 2 вхождения version_id=from_version_id
    count = src.count("version_id=from_version_id")
    assert count >= 2, (
        f"version_id=from_version_id должен передаваться в обоих вызовах "
        f"ProductionScheduler (основной + fallback). Найдено: {count}"
    )


def test_reschedule_has_fallback_scheduler():
    """
    Sanity-check: fallback-ветка действительно существует (scheduler2).
    """
    src = inspect.getsource(Rescheduler.reschedule)
    assert "scheduler2" in src, (
        "Должен быть второй вызов ProductionScheduler для fallback"
    )


# ==========================================
# 2. ЗАГРУЗКА from_version_id
# ==========================================

def test_reschedule_loads_from_version():
    """
    reschedule() должен принимать from_version_id и использовать его.
    """
    sig = inspect.signature(Rescheduler.reschedule)
    assert "from_version_id" in sig.parameters, (
        "reschedule() должен принимать from_version_id"
    )


def test_reschedule_references_from_version_id():
    """
    Исходник reschedule() должен ссылаться на from_version_id.
    """
    src = inspect.getsource(Rescheduler.reschedule)
    assert "from_version_id" in src, (
        "reschedule() должен использовать from_version_id"
    )


# ==========================================
# 3. ПРЯМЫЕ SQL-ЗАПРОСЫ К app_settings
# ==========================================

def test_reschedule_does_not_query_app_settings_directly():
    """
    reschedule() НЕ должен читать настройки напрямую из app_settings —
    это делает ProductionScheduler через DataLoader с version_id.
    """
    src = inspect.getsource(Rescheduler.reschedule)

    # Проверяем отсутствие прямого SELECT ... FROM app_settings
    assert "FROM app_settings" not in src, (
        "reschedule() не должен читать настройки из app_settings напрямую — "
        "это делает DataLoader с version_id=from_version_id"
    )


def test_rescheduler_module_does_not_import_settings_reader():
    """
    Модуль rescheduler не должен использовать settings_reader напрямую.
    Он делегирует чтение настроек ProductionScheduler.
    """
    src = inspect.getsource(rescheduler_module)

    # Не должен импортировать settings_reader
    assert "from .settings_reader" not in src
    assert "from app.scheduler.settings_reader" not in src


# ==========================================
# 4. DOCSTRING И КОММЕНТАРИИ
# ==========================================

def test_reschedule_docstring_mentions_plan_settings():
    """
    Docstring reschedule() должен упоминать plan_settings
    (чтобы будущие разработчики понимали контекст).
    """
    doc = Rescheduler.reschedule.__doc__ or ""
    assert "plan_settings" in doc or "13.14" in doc, (
        "Docstring reschedule() должен упоминать plan_settings "
        "или Итерацию 13.14"
    )


def test_module_docstring_mentions_iteration_13_14():
    """
    Модуль rescheduler.py должен упоминать Итерацию 13.14 в docstring.
    """
    doc = rescheduler_module.__doc__ or ""
    assert "13.14" in doc, (
        "Docstring модуля должен упоминать Итерацию 13.14"
    )


# ==========================================
# 5. SANITY: STRUCTURE
# ==========================================

def test_reschedule_signature_unchanged():
    """
    Сигнатура reschedule() не должна меняться — version_id
    берётся из from_version_id, а не передаётся отдельно.
    """
    sig = inspect.signature(Rescheduler.reschedule)
    params = set(sig.parameters.keys())

    # Обязательные параметры остались
    assert "from_version_id" in params
    assert "reason" in params
    assert "changes" in params

    # version_id НЕ должен появляться как отдельный параметр
    assert "version_id" not in params, (
        "version_id НЕ должен передаваться в reschedule() отдельно — "
        "он берётся из from_version_id"
    )


def test_rescheduler_has_original_methods():
    """
    Sanity: все оригинальные методы Rescheduler на месте.
    """
    for method in (
            "_load_version",
            "_load_tasks",
            "_apply_breakdown",
            "_apply_qty_change",
            "_apply_delay",
            "_build_pinned_tasks",
            "_find_affected_batch_ids",
            "reschedule",
            "compare_versions",
    ):
        assert hasattr(Rescheduler, method), f"Нет метода {method}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])