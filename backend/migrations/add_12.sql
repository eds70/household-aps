-- ==========================================
-- МИГРАЦИЯ 12: operation_name (Итерация 9, fix)
-- ==========================================
-- Добавляет колонку scheduled_task.operation_name — фактическое
-- имя операции (в т.ч. для динамических fill_*, у которых нет
-- шаблона в operation_template).
--
-- Идемпотентна: можно применять повторно.
-- ==========================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'scheduled_task' AND column_name = 'operation_name'
    ) THEN
ALTER TABLE scheduled_task
    ADD COLUMN operation_name VARCHAR(200);

COMMENT ON COLUMN scheduled_task.operation_name IS
            'Фактическое имя операции (в т.ч. для динамических fill_*). Итерация 9 (fix).';

        RAISE NOTICE 'Колонка scheduled_task.operation_name добавлена';
ELSE
        RAISE NOTICE 'Колонка scheduled_task.operation_name уже существует';
END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_scheduled_task_operation_name
    ON scheduled_task(organization_id, operation_name)
    WHERE operation_name IS NOT NULL;

-- Финальная проверка
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'scheduled_task' AND column_name = 'operation_name';