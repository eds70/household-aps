-- ==========================================
-- МИГРАЦИЯ 09: ЛЮДИ КАК РЕСУРС (Итерация 6)
-- ==========================================
-- Добавляет:
--   1. Новые типы пулов операторов в resource_pool
--   2. Заполняет пулы значениями по ТЗ
--   3. Включает feature-флаги
--   4. Обновляет operator_pool в operation_template
--
-- Идемпотентна: можно применять повторно.
-- ==========================================

-- ==========================================
-- 1. UNIQUE CONSTRAINT на (organization_id, type)
-- ==========================================
-- Без этого ON CONFLICT (organization_id, type) не работает.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'resource_pool_org_type_unique'
    ) THEN
        -- Удаляем дубликаты (если есть)
DELETE FROM resource_pool r1
    USING resource_pool r2
WHERE r1.id > r2.id
  AND r1.organization_id = r2.organization_id
  AND r1.type = r2.type;

-- Добавляем UNIQUE
ALTER TABLE resource_pool
    ADD CONSTRAINT resource_pool_org_type_unique
        UNIQUE (organization_id, type);

RAISE NOTICE 'Добавлен UNIQUE (organization_id, type) на resource_pool';
ELSE
        RAISE NOTICE 'UNIQUE (organization_id, type) уже существует';
END IF;
END $$;

-- ==========================================
-- 2. УДАЛЯЕМ СТАРЫЙ ОБЩИЙ ПУЛ OPERATOR
-- ==========================================
DELETE FROM resource_pool
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
  AND type = 'OPERATOR';

-- ==========================================
-- 3. СОЗДАНИЕ/ОБНОВЛЕНИЕ ПУЛОВ ОПЕРАТОРОВ
-- ==========================================
INSERT INTO resource_pool (organization_id, name, type, capacity, comment)
VALUES
    ('00000000-0000-0000-0000-000000000001',
     'Аппаратчики реакторов',
     'REACTOR_OPERATOR',
     3,
     'По ТЗ — 3 человека на 4 реактора. Итерация 6.'),

    ('00000000-0000-0000-0000-000000000001',
     'Операторы линий розлива',
     'LINE_OPERATOR',
     2,
     'Работают на линиях розлива. Итерация 6.'),

    ('00000000-0000-0000-0000-000000000001',
     'Операторы ручной станции',
     'MANUAL_OPERATOR',
     1,
     'Обслуживают ручную станцию (LINE_3). Итерация 6.')
    ON CONFLICT (organization_id, type) DO UPDATE
                                               SET name = EXCLUDED.name,
                                               capacity = EXCLUDED.capacity,
                                               comment = EXCLUDED.comment;

-- ==========================================
-- 4. FEATURE-ФЛАГИ
-- ==========================================
INSERT INTO organization_settings (organization_id, setting_key, setting_value, description) VALUES
                                                                                                 ('00000000-0000-0000-0000-000000000001',
                                                                                                  'enable_operator_pools',
                                                                                                  'true',
                                                                                                  'Пулы операторов. Итерация 6.'),

                                                                                                 ('00000000-0000-0000-0000-000000000001',
                                                                                                  'enable_manual_station',
                                                                                                  'true',
                                                                                                  'Ручная станция. Итерация 6.')
    ON CONFLICT (organization_id, setting_key) DO UPDATE
                                                      SET setting_value = EXCLUDED.setting_value,
                                                      description = EXCLUDED.description;

-- ==========================================
-- 5. ОБНОВЛЕНИЕ operator_pool В OPERATION_TEMPLATE
-- ==========================================
-- Проставляем LINE_OPERATOR для операций, которые сейчас NULL
-- и явно относятся к линии (например, future fill-операции).
-- Сейчас у нас: 16 REACTOR_OPERATOR, 11 NULL (лабораторные).
-- Операции слива — динамические (fill_...), создаются в routing.py.

DO $$
DECLARE
v_updated INT;
BEGIN
    -- Реакторные операции — у кого NULL, но needs_operator=true
UPDATE operation_template
SET operator_pool = 'REACTOR_OPERATOR'
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
  AND needs_operator = TRUE
  AND operator_pool IS NULL;

GET DIAGNOSTICS v_updated = ROW_COUNT;
RAISE NOTICE 'Обновлено реакторных операций: %', v_updated;

    -- Операции линий (LINE_FILL) — по имени
UPDATE operation_template
SET operator_pool = 'LINE_OPERATOR'
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
  AND operator_pool IS NULL
  AND (
    name ILIKE '%слив%'
          OR name ILIKE '%розлив%'
          OR name ILIKE '%фасов%'
    );

GET DIAGNOSTICS v_updated = ROW_COUNT;
RAISE NOTICE 'Обновлено операций линий: %', v_updated;
END $$;

-- ==========================================
-- 6. ФИНАЛЬНАЯ ПРОВЕРКА
-- ==========================================
SELECT 'resource_pool' AS table_name, type, capacity
FROM resource_pool
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
ORDER BY type;

SELECT setting_key, setting_value
FROM organization_settings
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
  AND setting_key IN ('enable_operator_pools', 'enable_manual_station');

SELECT
    COALESCE(operator_pool, '(NULL)') AS pool,
    COUNT(*) AS ops
FROM operation_template
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
GROUP BY operator_pool
ORDER BY pool;