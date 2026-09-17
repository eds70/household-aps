-- ==========================================
-- МИГРАЦИЯ 09d: operator_pool в scheduled_task
-- ==========================================
-- Сохраняет пул операторов на уровне задачи,
-- чтобы считать загрузку по фактическому плану.
-- Идемпотентна.
-- ==========================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'scheduled_task' AND column_name = 'operator_pool'
    ) THEN
ALTER TABLE scheduled_task
    ADD COLUMN operator_pool VARCHAR(50);
COMMENT ON COLUMN scheduled_task.operator_pool IS
            'Пул операторов (REACTOR_OPERATOR, LINE_OPERATOR, MANUAL_OPERATOR, LAB). Итерация 6.';

CREATE INDEX idx_scheduled_task_operator_pool
    ON scheduled_task(organization_id, schedule_version_id, operator_pool)
    WHERE operator_pool IS NOT NULL;

RAISE NOTICE 'Колонка scheduled_task.operator_pool добавлена';
ELSE
        RAISE NOTICE 'Колонка scheduled_task.operator_pool уже существует';
END IF;
END $$;

-- Финальная проверка
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'scheduled_task' AND column_name = 'operator_pool';