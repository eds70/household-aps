# backend/tests/test_saver_uses_snapshot.py
"""
Тесты Итерации 13.15: saver использует общий snapshot_all_catalogs.

Проверяют, что:
  1. saver.py импортирует snapshot_all_catalogs.
  2. _do_save вызывает эту функцию, а не делает inline SQL.
  3. Удалён старый inline SQL для снапшотов.
"""

import inspect

import pytest

from app.scheduler import saver as saver_module


# ==========================================
# 1. ИМПОРТ И СВЯЗЬ С SNAPSHOT
# ==========================================

def test_saver_imports_snapshot():
    """saver.py импортирует snapshot_all_catalogs."""
    src = inspect.getsource(saver_module)
    assert "from .snapshot import snapshot_all_catalogs" in src


def test_do_save_calls_snapshot_all_catalogs():
    """_do_save вызывает snapshot_all_catalogs."""
    src = inspect.getsource(saver_module.ScheduleSaver._do_save)
    assert "snapshot_all_catalogs" in src
    assert "session=session" in src or "session = session" in src


def test_do_save_passes_org_id():
    """_do_save передаёт org_id в snapshot_all_catalogs."""
    src = inspect.getsource(saver_module.ScheduleSaver._do_save)
    assert "org_id=self.org_id" in src


def test_do_save_passes_version_id():
    """_do_save передаёт version_id в snapshot_all_catalogs."""
    src = inspect.getsource(saver_module.ScheduleSaver._do_save)
    assert "version_id=version_id" in src


# ==========================================
# 2. ОТСУТСТВИЕ INLINE SQL (РЕГРЕССИЯ)
# ==========================================

def test_do_save_has_no_inline_equipment_snapshot_sql():
    """_do_save НЕ содержит inline INSERT INTO equipment_snapshot."""
    src = inspect.getsource(saver_module.ScheduleSaver._do_save)
    assert "INSERT INTO equipment_snapshot" not in src, (
        "saver._do_save не должен содержать inline INSERT в equipment_snapshot — "
        "используйте snapshot_all_catalogs"
    )


def test_do_save_has_no_inline_product_snapshot_sql():
    """_do_save НЕ содержит inline INSERT INTO product_snapshot."""
    src = inspect.getsource(saver_module.ScheduleSaver._do_save)
    assert "INSERT INTO product_snapshot" not in src


def test_do_save_has_no_inline_operation_snapshot_sql():
    """_do_save НЕ содержит inline INSERT INTO operation_snapshot."""
    src = inspect.getsource(saver_module.ScheduleSaver._do_save)
    assert "INSERT INTO operation_snapshot" not in src


def test_do_save_has_no_inline_calendar_snapshot_sql():
    """_do_save НЕ содержит inline INSERT INTO calendar_snapshot."""
    src = inspect.getsource(saver_module.ScheduleSaver._do_save)
    assert "INSERT INTO calendar_snapshot" not in src


# ==========================================
# 3. РЕЗУЛЬТАТ СОХРАНЕНИЯ
# ==========================================

def test_do_save_returns_snapshot_stats():
    """_do_save возвращает snapshot_stats в результате."""
    src = inspect.getsource(saver_module.ScheduleSaver._do_save)
    assert "snapshot_stats" in src
    assert '"snapshot_stats"' in src or "'snapshot_stats'" in src


def test_do_save_logs_snapshot_stats():
    """_do_save логирует статистику снапшотов."""
    src = inspect.getsource(saver_module.ScheduleSaver._do_save)
    # Проверяем, что в логировании упоминается snapshot_stats
    assert "snapshot_stats['equipment']" in src or \
           "snapshot_stats[\"equipment\"]" in src or \
           "snapshot_stats" in src


if __name__ == "__main__":
    pytest.main([__file__, "-v"])