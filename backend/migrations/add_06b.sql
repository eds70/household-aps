-- ==========================================
-- МИГРАЦИЯ 06b: СНАПШОТ-ТАБЛИЦЫ — ДОБАВЛЕНИЕ НОВЫХ КОЛОНОК
-- ==========================================
-- Итерация 3. Исправляет рассинхрон схемы снапшотов:
-- актуальный init_schema.sql (v1.3.0) содержит колонки code / route_type /
-- operator_pool в снапшотах, но существующие БД (v1.2.0) их не имеют.
--
-- Эта миграция идемпотентна, можно применять повторно.
-- ==========================================

-- ==========================================
-- 1. equipment_snapshot: +code
-- ==========================================
DO $$
BEGIN
IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
WHERE table_name = 'equipment_snapshot' AND column_name = 'code'
) THEN
ALTER TABLE equipment_snapshot ADD COLUMN code VARCHAR(50);
COMMENT ON COLUMN equipment_snapshot.code IS 'Код оборудования (снимок на момент планирования)';
RAISE NOTICE 'Добавлена колонка equipment_snapshot.code';
ELSE
RAISE NOTICE 'Колонка equipment_snapshot.code уже существует';
END IF;
END $$;

-- ==========================================
-- 2. product_snapshot: +route_type
-- ==========================================
DO $$
BEGIN
IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
WHERE table_name = 'product_snapshot' AND column_name = 'route_type'
) THEN
ALTER TABLE product_snapshot ADD COLUMN route_type VARCHAR(20) DEFAULT 'DIRECT';
COMMENT ON COLUMN product_snapshot.route_type IS 'Способ слива: DIRECT | VIA_TANK (снимок)';
RAISE NOTICE 'Добавлена колонка product_snapshot.route_type';
ELSE
RAISE NOTICE 'Колонка product_snapshot.route_type уже существует';
END IF;
END $$;

-- ==========================================
-- 3. operation_snapshot: +operator_pool
-- ==========================================
DO $$
BEGIN
IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
WHERE table_name = 'operation_snapshot' AND column_name = 'operator_pool'
) THEN
ALTER TABLE operation_snapshot ADD COLUMN operator_pool VARCHAR(50);
COMMENT ON COLUMN operation_snapshot.operator_pool IS 'Пул операторов (снимок)';
RAISE NOTICE 'Добавлена колонка operation_snapshot.operator_pool';
ELSE
RAISE NOTICE 'Колонка operation_snapshot.operator_pool уже существует';
END IF;
END $$;

-- ==========================================
-- 4. Задним числом заполнить старые снапшоты
-- ==========================================
-- Уже существующие записи в снапшотах (если есть) — заполняем code/route_type/operator_pool
-- из актуальных справочников по id.
UPDATE equipment_snapshot es
SET code = e.code
FROM equipment e
WHERE es.id = e.id
AND es.code IS NULL;

UPDATE product_snapshot ps
SET route_type = p.route_type
FROM product p
WHERE ps.id = p.id
AND (ps.route_type IS NULL OR ps.route_type = 'DIRECT');

UPDATE operation_snapshot os
SET operator_pool = ot.operator_pool
FROM operation_template ot
WHERE os.id = ot.id
AND os.operator_pool IS NULL;

-- ==========================================
-- ФИНАЛЬНАЯ ПРОВЕРКА
-- ==========================================
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_name IN ('equipment_snapshot', 'product_snapshot', 'operation_snapshot')
AND column_name IN ('code', 'route_type', 'operator_pool')
ORDER BY table_name, column_name;

-- Ожидаемый результат:
--   equipment_snapshot  | code          | character varying
--   operation_snapshot  | operator_pool | character varying
--   product_snapshot    | route_type    | character varying