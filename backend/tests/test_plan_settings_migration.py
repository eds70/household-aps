# backend/tests/test_plan_settings_migration.py
"""
Тесты миграции add_21.sql (Итерация 13.14).

Проверяют содержимое SQL-файла без реальной БД:
  - Наличие CREATE TABLE plan_settings.
  - Наличие триггера copy_app_settings_to_plan.
  - Наличие индексов.
  - Идемпотентность (IF NOT EXISTS / ON CONFLICT).
"""
import os
import re

import pytest

MIGRATION_PATH = os.path.join(
    os.path.dirname(__file__), "..", "migrations", "add_21.sql"
)


# ==========================================
# 1. ФАЙЛ СУЩЕСТВУЕТ
# ==========================================

def test_migration_file_exists():
    """Файл add_21.sql существует."""
    assert os.path.exists(MIGRATION_PATH), (
        "migrations/add_21.sql должен существовать"
    )


def test_migration_file_not_empty():
    """Файл не пустой и содержит SQL."""
    with open(MIGRATION_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    assert len(content) > 500, "Файл слишком короткий"
    assert "CREATE TABLE" in content


# ==========================================
# 2. CREATE TABLE
# ==========================================

def test_migration_creates_plan_settings_table():
    """CREATE TABLE IF NOT EXISTS plan_settings."""
    with open(MIGRATION_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    assert "CREATE TABLE IF NOT EXISTS plan_settings" in content
    assert "schedule_version_id UUID NOT NULL" in content
    assert "REFERENCES schedule_version" in content


def test_migration_has_unique_constraint():
    """UNIQUE (schedule_version_id, setting_key)."""
    with open(MIGRATION_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    assert "UNIQUE (schedule_version_id, setting_key)" in content


def test_migration_has_metadata_columns():
    """Снапшот метаданных: value_type, category, label, description, etc."""
    with open(MIGRATION_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    for col in (
            "setting_key",
            "setting_value",
            "value_type",
            "category",
            "label",
            "description",
            "min_value",
            "max_value",
            "options",
            "display_order",
            "is_system",
    ):
        assert col in content, f"Колонка {col} отсутствует"


def test_migration_setting_value_is_jsonb():
    """setting_value — JSONB (не TEXT)."""
    with open(MIGRATION_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    match = re.search(
        r"setting_value\s+JSONB",
        content,
        re.IGNORECASE,
    )
    assert match is not None, "setting_value должен быть JSONB"


# ==========================================
# 3. ИНДЕКСЫ
# ==========================================

def test_migration_has_version_index():
    """Индекс по schedule_version_id."""
    with open(MIGRATION_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    assert "idx_plan_settings_version" in content
    assert "ON plan_settings(schedule_version_id)" in content


def test_migration_has_org_category_index():
    """Составной индекс по (organization_id, category)."""
    with open(MIGRATION_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    assert "idx_plan_settings_org_category" in content
    assert "(organization_id, category)" in content


# ==========================================
# 4. ТРИГГЕР
# ==========================================

def test_migration_creates_trigger_function():
    """Функция copy_app_settings_to_plan существует."""
    with open(MIGRATION_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    assert "CREATE OR REPLACE FUNCTION copy_app_settings_to_plan" in content
    assert "RETURNS TRIGGER" in content


def test_migration_function_inserts_from_app_settings():
    """Функция копирует из app_settings в plan_settings."""
    with open(MIGRATION_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    assert "INSERT INTO plan_settings" in content
    assert "FROM app_settings" in content
    assert "ON CONFLICT" in content, (
        "Триггер должен быть идемпотентным (ON CONFLICT DO NOTHING)"
    )


def test_migration_creates_trigger_on_schedule_version():
    """Триггер trg_copy_app_settings_to_plan на schedule_version."""
    with open(MIGRATION_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    assert "CREATE TRIGGER trg_copy_app_settings_to_plan" in content
    assert "AFTER INSERT ON schedule_version" in content
    assert "FOR EACH ROW EXECUTE FUNCTION copy_app_settings_to_plan()" in content


def test_migration_drops_old_trigger():
    """DROP TRIGGER IF EXISTS перед CREATE."""
    with open(MIGRATION_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    assert "DROP TRIGGER IF EXISTS trg_copy_app_settings_to_plan" in content


# ==========================================
# 5. ИДЕМПОТЕНТНОСТЬ
# ==========================================

def test_migration_is_idempotent():
    """Все критичные операции обёрнуты в IF NOT EXISTS / OR REPLACE."""
    with open(MIGRATION_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    assert "CREATE TABLE IF NOT EXISTS plan_settings" in content
    assert content.count("CREATE INDEX IF NOT EXISTS") >= 2
    assert "CREATE OR REPLACE FUNCTION" in content
    assert "DROP TRIGGER IF EXISTS" in content


def test_migration_uses_on_conflict_do_nothing():
    """Триггер использует ON CONFLICT DO NOTHING."""
    with open(MIGRATION_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    assert "ON CONFLICT (schedule_version_id, setting_key) DO NOTHING" in content


# ==========================================
# 6. КОММЕНТАРИИ
# ==========================================

def test_migration_has_comments():
    """Миграция содержит COMMENT ON для документации."""
    with open(MIGRATION_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    assert "COMMENT ON TABLE plan_settings" in content
    assert "COMMENT ON COLUMN plan_settings.setting_value" in content


def test_migration_references_iteration():
    """Миграция упоминает итерацию (для истории)."""
    with open(MIGRATION_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    assert "13.14" in content or "Итерация 13" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])