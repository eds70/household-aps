-- ==========================================
-- МИГРАЦИЯ 16: What-if сценарии (Итерация 12)
-- ==========================================
-- Добавляет таблицу whatif_scenario для сценарного планирования.
--
-- Что-if сценарий:
--   1. Пользователь выбирает базовый план.
--   2. Задаёт изменения (JSONB):
--      - orders: [...]
--      - shift_mode: "..."
--      - resource_capacity: {...}
--      - calendar_events: [...]
--   3. Запускает расчёт → создаётся новая schedule_version.
--   4. Сравнивает с базовым планом.
--
-- Изменения НЕ применяются к основной БД — сценарий только читает.
-- Результат сохраняется как отдельная версия плана.
--
-- Идемпотентна: можно применять повторно.
-- ==========================================

CREATE TABLE IF NOT EXISTS whatif_scenario (
                                               id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    comment TEXT,
    base_version_id UUID NOT NULL REFERENCES schedule_version(id) ON DELETE CASCADE,
    result_version_id UUID REFERENCES schedule_version(id) ON DELETE SET NULL,
    changes JSONB NOT NULL DEFAULT '{}',
    status VARCHAR(30) NOT NULL DEFAULT 'DRAFT',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES app_user(id) ON DELETE SET NULL
    );

COMMENT ON TABLE whatif_scenario IS
    'What-if сценарии. Сравнение альтернативных планов. Итерация 12.';
COMMENT ON COLUMN whatif_scenario.status IS
    'DRAFT | RUNNING | DONE | FAILED';
COMMENT ON COLUMN whatif_scenario.changes IS
    'JSON с изменениями. Формат: {orders: [...], shift_mode: "...", '
    'resource_capacity: {...}, calendar_events: [...]}';
COMMENT ON COLUMN whatif_scenario.base_version_id IS
    'Базовый план, от которого считается сценарий.';
COMMENT ON COLUMN whatif_scenario.result_version_id IS
    'Результат расчёта — новая версия плана. Заполняется после run.';

CREATE INDEX IF NOT EXISTS idx_whatif_scenario_org
    ON whatif_scenario(organization_id);
CREATE INDEX IF NOT EXISTS idx_whatif_scenario_base
    ON whatif_scenario(base_version_id);
CREATE INDEX IF NOT EXISTS idx_whatif_scenario_status
    ON whatif_scenario(organization_id, status);
CREATE INDEX IF NOT EXISTS idx_whatif_scenario_created
    ON whatif_scenario(organization_id, created_at DESC);

-- ==========================================
-- ФИНАЛЬНАЯ ПРОВЕРКА
-- ==========================================
SELECT 'whatif_scenario' AS table_name, COUNT(*) AS rows
FROM whatif_scenario
WHERE organization_id = '00000000-0000-0000-0000-000000000001';

-- Ожидаемо: whatif_scenario | 0