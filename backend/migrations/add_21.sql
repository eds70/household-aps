-- ==========================================
-- МИГРАЦИЯ 21: Снапшот настроек для каждого плана
-- ==========================================
-- Каждый plan (schedule_version) хранит СВОЙ набор настроек,
-- с которыми он был построен. Это позволяет:
--   1. Воспроизводить план — зная plan_settings, можно пересчитать
--      ровно тот же результат.
--   2. Не ломать старые планы при изменении глобальных app_settings.
--   3. Сравнивать планы, построенные с разными настройками.
--
-- Логика:
--   - При создании плана мастер заполняет plan_settings.
--   - Планировщик (DataLoader) читает plan_settings, а не app_settings.
--   - app_settings используется как ДЕФОЛТ для мастера (когда план ещё не создан).
--
-- Идемпотентна: можно применять повторно.
-- ==========================================

CREATE TABLE IF NOT EXISTS plan_settings (
                                             id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
    schedule_version_id UUID NOT NULL REFERENCES schedule_version(id) ON DELETE CASCADE,
    setting_key VARCHAR(100) NOT NULL,
    setting_value JSONB NOT NULL,
    value_type VARCHAR(20) NOT NULL,
    category VARCHAR(50) NOT NULL,
    -- Снимок метаданных на момент создания плана.
    -- Нужен, чтобы UI показывал настройки даже если реестр (SETTINGS_REGISTRY) изменится.
    label VARCHAR(200),
    description TEXT,
    min_value NUMERIC,
    max_value NUMERIC,
    options JSONB,
    display_order INT DEFAULT 0,
    is_system BOOLEAN DEFAULT FALSE,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (schedule_version_id, setting_key)
    );

COMMENT ON TABLE plan_settings IS
    'Снапшот настроек для конкретного плана (schedule_version). '
    'Планировщик читает эти настройки, а не глобальные app_settings. Итерация 13.14.';

COMMENT ON COLUMN plan_settings.setting_value IS
    'Значение настройки, с которым был построен план. JSONB.';

COMMENT ON COLUMN plan_settings.category IS
    'Категория настройки для группировки в мастере: planning, shifts, cooling, '
    'calendar, materials, lab, resources, features, optimization, cz.';

CREATE INDEX IF NOT EXISTS idx_plan_settings_version
    ON plan_settings(schedule_version_id);

CREATE INDEX IF NOT EXISTS idx_plan_settings_org_category
    ON plan_settings(organization_id, category);

-- ==========================================
-- ТРИГГЕР: при создании schedule_version копируем текущие app_settings
-- ==========================================
-- Если план создаётся через API без явного мастера — просто копируем
-- глобальные настройки. Это дефолт «без мастера».
-- Если мастер передаёт свои настройки явно — он делает это ПОСЛЕ создания
-- version, перезаписывая значения через upsert.
-- ==========================================

CREATE OR REPLACE FUNCTION copy_app_settings_to_plan()
RETURNS TRIGGER AS $$
BEGIN
INSERT INTO plan_settings (
    organization_id, schedule_version_id, setting_key, setting_value,
    value_type, category, label, description,
    min_value, max_value, options, display_order, is_system
)
SELECT
    NEW.organization_id,
    NEW.id,
    s.setting_key,
    s.setting_value,
    s.value_type,
    s.category,
    s.label,
    s.description,
    s.min_value,
    s.max_value,
    s.options,
    s.display_order,
    COALESCE(s.is_system, FALSE)
FROM app_settings s
WHERE s.organization_id = NEW.organization_id
    ON CONFLICT (schedule_version_id, setting_key) DO NOTHING;

RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_copy_app_settings_to_plan ON schedule_version;
CREATE TRIGGER trg_copy_app_settings_to_plan
    AFTER INSERT ON schedule_version
    FOR EACH ROW EXECUTE FUNCTION copy_app_settings_to_plan();

-- ==========================================
-- ФИНАЛЬНАЯ ПРОВЕРКА
-- ==========================================
SELECT 'plan_settings' AS table_name, COUNT(*) AS rows FROM plan_settings;
SELECT 'triggers' AS check_name, COUNT(*) FROM pg_trigger
WHERE tgname = 'trg_copy_app_settings_to_plan';