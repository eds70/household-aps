-- ==========================================
-- МИГРАЦИЯ 07: ПЕРЕПЛАНИРОВАНИЕ
-- ==========================================
-- Итерация 4. Добавляет:
--   1. Таблица reschedule_log — журнал перепланирований
--   2. Поле frozen_before в schedule_version — до какого момента задачи «заморожены»
--   3. Поле is_pinned в scheduled_task — уже есть, активируем использование
--   4. Feature-флаг enable_rescheduling = true
-- ==========================================

-- ==========================================
-- 1. SCHEDULE_VERSION: frozen_before
-- ==========================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'schedule_version' AND column_name = 'frozen_before'
    ) THEN
ALTER TABLE schedule_version ADD COLUMN frozen_before TIMESTAMPTZ;
COMMENT ON COLUMN schedule_version.frozen_before IS
            'Задачи, начавшиеся до этого момента, заморожены — не двигаются при перепланировании';
END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'schedule_version' AND column_name = 'parent_version_id'
    ) THEN
ALTER TABLE schedule_version ADD COLUMN parent_version_id UUID REFERENCES schedule_version(id) ON DELETE SET NULL;
COMMENT ON COLUMN schedule_version.parent_version_id IS
            'Родительская версия — от какой версии плана перепланировали';
END IF;
END $$;

-- ==========================================
-- 2. RESCHEDULE_LOG
-- ==========================================
CREATE TABLE IF NOT EXISTS reschedule_log (
                                              id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
    from_version_id UUID REFERENCES schedule_version(id) ON DELETE SET NULL,
    to_version_id UUID REFERENCES schedule_version(id) ON DELETE SET NULL,
    reason VARCHAR(30) NOT NULL,          -- DELAY | BREAKDOWN | QTY_CHANGE | MANUAL
    changes JSONB NOT NULL DEFAULT '{}',  -- {affected_batch_ids, new_calendar_events, ...}
    affected_task_count INT DEFAULT 0,
    moved_task_count INT DEFAULT 0,
    frozen_before TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES app_user(id),
    comment TEXT
    );
COMMENT ON TABLE reschedule_log IS 'Журнал перепланирований. Связывает старую и новую версии плана.';

CREATE INDEX IF NOT EXISTS idx_reschedule_log_org ON reschedule_log(organization_id);
CREATE INDEX IF NOT EXISTS idx_reschedule_log_from_version ON reschedule_log(from_version_id);
CREATE INDEX IF NOT EXISTS idx_reschedule_log_to_version ON reschedule_log(to_version_id);

-- ==========================================
-- 3. ВКЛЮЧАЕМ FEATURE-ФЛАГ
-- ==========================================
INSERT INTO organization_settings (organization_id, setting_key, setting_value, description) VALUES
    ('00000000-0000-0000-0000-000000000001', 'enable_rescheduling',
     'true', 'Перепланирование (Итерация 4)')
    ON CONFLICT (organization_id, setting_key) DO UPDATE
                                                      SET setting_value = EXCLUDED.setting_value,
                                                      description = EXCLUDED.description;

-- ==========================================
-- ФИНАЛЬНАЯ ПРОВЕРКА
-- ==========================================
SELECT 'reschedule_log' AS table_name, COUNT(*) AS rows FROM reschedule_log
UNION ALL
SELECT 'schedule_version.frozen_before', COUNT(*) FROM information_schema.columns
WHERE table_name = 'schedule_version' AND column_name = 'frozen_before'
UNION ALL
SELECT 'schedule_version.parent_version_id', COUNT(*) FROM information_schema.columns
WHERE table_name = 'schedule_version' AND column_name = 'parent_version_id'
UNION ALL
SELECT 'enable_rescheduling', COUNT(*) FROM organization_settings
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
  AND setting_key = 'enable_rescheduling'
  AND setting_value = 'true'::jsonb;

-- Ожидаемо:
--   reschedule_log:                       0
--   schedule_version.frozen_before:       1
--   schedule_version.parent_version_id:   1
--   enable_rescheduling:                  1