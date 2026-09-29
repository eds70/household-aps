-- ==========================================
-- МИГРАЦИЯ 22: Индексы для каскадного сдвига (Итерация 13.17)
-- ==========================================
-- Добавляет индексы для быстрого поиска задач
-- при каскадном сдвиге на Ганте.
--
-- Идемпотентна.
-- ==========================================

CREATE INDEX IF NOT EXISTS idx_scheduled_task_equipment_time
    ON scheduled_task(organization_id, schedule_version_id, equipment_id, planned_start);

-- Индекс для поиска по depends_on_task_ids (GIN)
-- Уже создан в add_20.sql как idx_scheduled_task_depends_on,
-- но добавим ещё один для version_id + depends_on
CREATE INDEX IF NOT EXISTS idx_scheduled_task_version_deps
    ON scheduled_task USING GIN (depends_on_task_ids)
    WHERE depends_on_task_ids IS NOT NULL
    AND depends_on_task_ids != '[]'::jsonb;

SELECT 'idx_scheduled_task_equipment_time' AS index_name,
       EXISTS (
           SELECT 1 FROM pg_indexes
           WHERE indexname = 'idx_scheduled_task_equipment_time'
       ) AS created
UNION ALL
SELECT 'idx_scheduled_task_version_deps',
       EXISTS (
           SELECT 1 FROM pg_indexes
           WHERE indexname = 'idx_scheduled_task_version_deps'
       );