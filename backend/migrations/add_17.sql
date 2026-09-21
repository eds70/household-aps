-- ==========================================
-- МИГРАЦИЯ 17: UNIQUE на material_stock
-- ==========================================
-- Проблема: при создании материала через API создаётся запись в material_stock,
-- но UNIQUE-констрейнта на (organization_id, material_id) нет.
-- Повторные вставки / миграции могут создать дубликаты.
--
-- Решение: добавить UNIQUE (organization_id, material_id).
--
-- Идемпотентна: можно применять повторно.
-- ==========================================

DO $$
BEGIN
    -- 1. Удалить возможные дубликаты (оставить запись с самым свежим updated_at)
DELETE FROM material_stock ms1
    USING material_stock ms2
WHERE ms1.id <> ms2.id
  AND ms1.organization_id = ms2.organization_id
  AND ms1.material_id = ms2.material_id
  AND (
    ms1.updated_at < ms2.updated_at
   OR (ms1.updated_at = ms2.updated_at AND ms1.id > ms2.id)
    );

-- 2. Добавить UNIQUE constraint
IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'material_stock_org_mat_unique'
    ) THEN
ALTER TABLE material_stock
    ADD CONSTRAINT material_stock_org_mat_unique
        UNIQUE (organization_id, material_id);

RAISE NOTICE 'Добавлен UNIQUE (organization_id, material_id) на material_stock';
ELSE
        RAISE NOTICE 'UNIQUE уже существует — пропускаем';
END IF;
END $$;

-- ==========================================
-- ФИНАЛЬНАЯ ПРОВЕРКА
-- ==========================================
SELECT 'material_stock' AS table_name, COUNT(*) AS rows FROM material_stock
UNION ALL
SELECT 'уникальных пар (org, material)', COUNT(DISTINCT (organization_id, material_id))
FROM material_stock;

SELECT conname, pg_get_constraintdef(oid) AS definition
FROM pg_constraint
WHERE conname = 'material_stock_org_mat_unique';