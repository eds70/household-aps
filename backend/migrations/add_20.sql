-- ==========================================
-- МИГРАЦИЯ 20: Связи между задачами (Итерация 13.6)
-- ==========================================
-- Добавляет колонку scheduled_task.depends_on_task_ids —
-- список UUID задач-предшественников внутри той же версии плана.
--
-- Используется frontend'ом для рисования ортогональных «проводов»
-- между задачами, особенно когда процесс меняет оборудование
-- (реактор → танк → линия).
--
-- Идемпотентна: можно применять повторно.
-- ==========================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'scheduled_task'
          AND column_name = 'depends_on_task_ids'
    ) THEN
ALTER TABLE scheduled_task
    ADD COLUMN depends_on_task_ids JSONB DEFAULT '[]'::jsonb;

COMMENT ON COLUMN scheduled_task.depends_on_task_ids IS
            'Список UUID задач-предшественников внутри той же версии плана. '
            'Используется для рисования связей на Ганте. Итерация 13.6.';

        RAISE NOTICE 'Колонка scheduled_task.depends_on_task_ids добавлена';
ELSE
        RAISE NOTICE 'Колонка scheduled_task.depends_on_task_ids уже существует';
END IF;
END $$;

-- Индекс для быстрого поиска задач по зависимостям
CREATE INDEX IF NOT EXISTS idx_scheduled_task_depends_on
    ON scheduled_task USING GIN (depends_on_task_ids)
    WHERE depends_on_task_ids IS NOT NULL
    AND depends_on_task_ids != '[]'::jsonb;

-- Финальная проверка
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'scheduled_task'
  AND column_name = 'depends_on_task_ids';