-- ==========================================
-- МИГРАЦИЯ 09c: updated_at в resource_pool
-- ==========================================
-- Добавляет колонку updated_at для аудита изменений capacity.
-- Идемпотентна — можно применять повторно.
-- ==========================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'resource_pool' AND column_name = 'updated_at'
    ) THEN
ALTER TABLE resource_pool
    ADD COLUMN updated_at TIMESTAMPTZ DEFAULT NOW();
COMMENT ON COLUMN resource_pool.updated_at IS
            'Дата последнего изменения (Итерация 6)';
        RAISE NOTICE 'Колонка resource_pool.updated_at добавлена';
ELSE
        RAISE NOTICE 'Колонка resource_pool.updated_at уже существует';
END IF;
END $$;

-- ==========================================
-- Заполним существующие строки текущей датой (если NULL)
-- ==========================================
UPDATE resource_pool
SET updated_at = NOW()
WHERE updated_at IS NULL;

-- ==========================================
-- ФИНАЛЬНАЯ ПРОВЕРКА
-- ==========================================
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'resource_pool'
ORDER BY ordinal_position;