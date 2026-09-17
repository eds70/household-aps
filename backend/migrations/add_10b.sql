-- ==========================================
-- МИГРАЦИЯ 10b: cooling_mode в scheduled_task
-- ==========================================
-- Сохраняет режим охлаждения (fast / slow) на уровне задачи.
-- Fast = обычная скорость.
-- Slow = замедление ×1.3 (при 2 параллельных охлаждениях).
--
-- Идемпотентна: можно применять повторно.
-- ==========================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'scheduled_task' AND column_name = 'cooling_mode'
    ) THEN
ALTER TABLE scheduled_task
    ADD COLUMN cooling_mode VARCHAR(10);
COMMENT ON COLUMN scheduled_task.cooling_mode IS
            'Режим охлаждения: fast (обычный), slow (замедление ×1.3), NULL (не cooling). Итерация 7.';

CREATE INDEX idx_scheduled_task_cooling_mode
    ON scheduled_task(organization_id, schedule_version_id, cooling_mode)
    WHERE cooling_mode IS NOT NULL;

RAISE NOTICE 'Колонка scheduled_task.cooling_mode добавлена';
ELSE
        RAISE NOTICE 'Колонка scheduled_task.cooling_mode уже существует';
END IF;
END $$;

-- Финальная проверка
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'scheduled_task' AND column_name = 'cooling_mode';