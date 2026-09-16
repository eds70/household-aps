-- ==========================================
-- ИСТОРИЯ МИГРАЦИЙ: Итерации 0–2
-- ==========================================
-- Этот файл — склейка add_01..add_05.
-- Применяется на БД, созданную СТАРЫМ init_schema.sql (v1.2.0),
-- чтобы привести её к актуальной схеме v1.3.0.
--
-- НЕ ПРИМЕНЯТЬ на пустую БД — используйте init_schema.sql (v1.3.0).
-- Все операции идемпотентны (IF NOT EXISTS / ON CONFLICT DO NOTHING),
-- поэтому повторное применение безопасно.
--
-- Содержит:
--   add_01: organization_settings, password_hash, базовые настройки
--   add_02: feature-флаги (10 штук)
--   add_03: product.route_type, scheduled_task.linked_equipment_id + task_role,
--           operation_template.operator_pool
--   add_04: equipment.code, equipment_link, equipment_capability для линий,
--           28 партий вместо 30
--   add_05: enable_material_constraints = true
-- ==========================================


-- ==========================================
-- ADD_01: organization_settings + app_user
-- ==========================================
CREATE TABLE IF NOT EXISTS organization_settings (
                                                     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
    setting_key VARCHAR(100) NOT NULL,
    setting_value JSONB NOT NULL,
    description TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (organization_id, setting_key)
    );
COMMENT ON TABLE organization_settings IS 'Настройки организации. Хранит бизнес-параметры и feature-флаги.';

CREATE INDEX IF NOT EXISTS idx_org_settings_org_id ON organization_settings(organization_id);

ALTER TABLE app_user ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255);
ALTER TABLE app_user ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ;
ALTER TABLE app_user ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;

COMMENT ON COLUMN app_user.password_hash IS 'Хешированный пароль пользователя (bcrypt)';
COMMENT ON COLUMN app_user.last_login_at IS 'Дата и время последнего входа';

-- Базовые настройки
INSERT INTO organization_settings (organization_id, setting_key, setting_value, description) VALUES
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'max_operators',              '3',                        'Максимальное количество операторов'),
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'cooling_zone_capacity',      '2',                        'Максимум реакторов в зоне охлаждения'),
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'default_horizon_hours',      '2160',                     'Горизонт планирования по умолчанию (часы)'),
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'max_fill_percent',           '0.70',                     'Максимальная загрузка реактора'),
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'planning_start_date',        '"2026-09-01T08:00:00"',    'Дата начала планирования'),
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'work_start_time',            '"08:00"',                  'Начало рабочего дня'),
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'work_end_time',              '"20:00"',                  'Конец рабочего дня')
    ON CONFLICT (organization_id, setting_key) DO NOTHING;


-- ==========================================
-- ADD_02: Feature-флаги (10 штук)
-- ==========================================
-- Изначально все false, активируются в add_03 и add_05.
INSERT INTO organization_settings (organization_id, setting_key, setting_value, description) VALUES
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'enable_tank_routing',        'false', 'Цепочки реактор→танк→линия (Итерация 1)'),
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'enable_shift_planning',      'false', 'Посменное планирование (Итерация 3)'),
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'enable_rescheduling',        'false', 'Перепланирование (Итерация 4)'),
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'enable_material_constraints','false', 'Учёт остатков сырья (Итерация 2)'),
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'enable_advisor',             'true',  'Подсказки планировщика (Итерация 2)'),
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'enable_lab_blocking',        'false', 'Блокировка лабой (Итерация 5)'),
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'enable_cooling_degradation', 'false', 'Деградация охлаждения (Итерация 7)'),
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'enable_operator_pools',      'false', 'Пулы операторов (Итерация 6)'),
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'enable_manual_station',      'false', 'Ручная станция (Итерация 6)'),
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'enable_cz_integration',      'false', 'Интеграция с ЧЗ (Итерация 8)')
    ON CONFLICT (organization_id, setting_key) DO NOTHING;


-- ==========================================
-- ADD_03: Цепочки рабочих центров
-- ==========================================
-- 3.1. product.route_type
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'product' AND column_name = 'route_type'
    ) THEN
ALTER TABLE product ADD COLUMN route_type VARCHAR(20) DEFAULT 'DIRECT';
COMMENT ON COLUMN product.route_type IS
            'Способ слива ПФ: DIRECT (напрямую на линию) или VIA_TANK (через накопительную емкость)';
END IF;
END $$;

UPDATE product SET route_type = 'VIA_TANK' WHERE code = 'PF_CREAM';
UPDATE product SET route_type = 'DIRECT'   WHERE code IN ('PF_DISH', 'PF_ANTISEPTIC');

-- 3.2. scheduled_task.linked_equipment_id + task_role
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'scheduled_task' AND column_name = 'linked_equipment_id'
    ) THEN
ALTER TABLE scheduled_task ADD COLUMN linked_equipment_id UUID REFERENCES equipment(id);
COMMENT ON COLUMN scheduled_task.linked_equipment_id IS
            'Второй ресурс задачи (слив занимает реактор+линию, перекачка — реактор+танк)';
END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'scheduled_task' AND column_name = 'task_role'
    ) THEN
ALTER TABLE scheduled_task ADD COLUMN task_role VARCHAR(30);
COMMENT ON COLUMN scheduled_task.task_role IS
            'Роль задачи в цепочке: REACTOR_OP, TANK_TRANSFER, LINE_FILL, WASH, SETUP';
END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_scheduled_task_linked_eq
    ON scheduled_task(linked_equipment_id)
    WHERE linked_equipment_id IS NOT NULL;

-- 3.3. operation_template.operator_pool
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'operation_template' AND column_name = 'operator_pool'
    ) THEN
ALTER TABLE operation_template ADD COLUMN operator_pool VARCHAR(50);
COMMENT ON COLUMN operation_template.operator_pool IS
            'Пул операторов: REACTOR_OPERATOR (аппаратчики) или LINE_OPERATOR (операторы линий)';
END IF;
END $$;

UPDATE operation_template
SET operator_pool = 'REACTOR_OPERATOR'
WHERE needs_operator = TRUE AND operator_pool IS NULL;

-- 3.4. Включаем enable_tank_routing
INSERT INTO organization_settings (organization_id, setting_key, setting_value, description) VALUES
    ('00000000-0000-0000-0000-000000000001', 'enable_tank_routing',
     'true', 'Цепочки реактор→танк→линия (Итерация 1)')
    ON CONFLICT (organization_id, setting_key) DO UPDATE
                                                      SET setting_value = EXCLUDED.setting_value,
                                                      description = EXCLUDED.description;


-- ==========================================
-- ADD_04: equipment.code, equipment_link, equipment_capability, 28 партий
-- ==========================================

-- 4.1. equipment.code
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'equipment' AND column_name = 'code'
    ) THEN
ALTER TABLE equipment ADD COLUMN code VARCHAR(50);
COMMENT ON COLUMN equipment.code IS
            'Уникальный код оборудования (REACTOR_1, TANK_1, LINE_1, BOILER)';
        RAISE NOTICE 'Колонка equipment.code добавлена';
ELSE
        RAISE NOTICE 'Колонка equipment.code уже существует';
END IF;
END $$;

-- 4.2. Заполнение code по именам
DO $$
DECLARE
v_org_id UUID := '00000000-0000-0000-0000-000000000001';
BEGIN
UPDATE equipment SET code = 'BOILER'    WHERE organization_id = v_org_id AND name = 'Бойлер';
UPDATE equipment SET code = 'TANK_1'    WHERE organization_id = v_org_id AND name = 'Накопительная емкость 1';
UPDATE equipment SET code = 'LINE_1'    WHERE organization_id = v_org_id AND name = 'Линия 1 (1л)';
UPDATE equipment SET code = 'LINE_2'    WHERE organization_id = v_org_id AND name = 'Линия 2 (5/10л)';
UPDATE equipment SET code = 'LINE_3'    WHERE organization_id = v_org_id AND name = 'Линия 3 (ручной слив 10л)';
UPDATE equipment SET code = 'REACTOR_1' WHERE organization_id = v_org_id AND name = 'Реактор 1';
UPDATE equipment SET code = 'REACTOR_2' WHERE organization_id = v_org_id AND name = 'Реактор 2';
UPDATE equipment SET code = 'REACTOR_3' WHERE organization_id = v_org_id AND name = 'Реактор 3';
UPDATE equipment SET code = 'REACTOR_4' WHERE organization_id = v_org_id AND name = 'Реактор 4';
END $$;

-- 4.3. UNIQUE constraint на (organization_id, code)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'equipment_org_code_unique'
    ) THEN
DELETE FROM equipment e1
    USING equipment e2
WHERE e1.id > e2.id
  AND e1.organization_id = e2.organization_id
  AND e1.code = e2.code
  AND e1.code IS NOT NULL;

ALTER TABLE equipment
    ADD CONSTRAINT equipment_org_code_unique UNIQUE (organization_id, code);
RAISE NOTICE 'UNIQUE constraint equipment_org_code_unique добавлен';
ELSE
        RAISE NOTICE 'UNIQUE constraint уже существует';
END IF;
END $$;

-- 4.4. equipment_link (7 связей)
DO $$
DECLARE
v_org_id UUID := '00000000-0000-0000-0000-000000000001';
    v_r1 UUID; v_r2 UUID; v_r3 UUID; v_r4 UUID;
    v_t1 UUID; v_l1 UUID; v_l2 UUID; v_l3 UUID;
BEGIN
SELECT id INTO v_r1 FROM equipment WHERE organization_id = v_org_id AND code = 'REACTOR_1';
SELECT id INTO v_r2 FROM equipment WHERE organization_id = v_org_id AND code = 'REACTOR_2';
SELECT id INTO v_r3 FROM equipment WHERE organization_id = v_org_id AND code = 'REACTOR_3';
SELECT id INTO v_r4 FROM equipment WHERE organization_id = v_org_id AND code = 'REACTOR_4';
SELECT id INTO v_t1 FROM equipment WHERE organization_id = v_org_id AND code = 'TANK_1';
SELECT id INTO v_l1 FROM equipment WHERE organization_id = v_org_id AND code = 'LINE_1';
SELECT id INTO v_l2 FROM equipment WHERE organization_id = v_org_id AND code = 'LINE_2';
SELECT id INTO v_l3 FROM equipment WHERE organization_id = v_org_id AND code = 'LINE_3';

IF v_r1 IS NULL OR v_t1 IS NULL OR v_l1 IS NULL THEN
        RAISE WARNING 'Не найдено оборудование с ожидаемыми code';
        RETURN;
END IF;

DELETE FROM equipment_link WHERE organization_id = v_org_id;

INSERT INTO equipment_link (organization_id, from_equipment_id, to_equipment_id, is_direct) VALUES
                                                                                                (v_org_id, v_r1, v_t1, TRUE),
                                                                                                (v_org_id, v_t1, v_l1, TRUE),
                                                                                                (v_org_id, v_r1, v_l1, TRUE),
                                                                                                (v_org_id, v_r2, v_l1, TRUE),
                                                                                                (v_org_id, v_r2, v_l2, TRUE),
                                                                                                (v_org_id, v_r3, v_l2, TRUE),
                                                                                                (v_org_id, v_r4, v_l3, TRUE);

RAISE NOTICE 'Создано equipment_link: %',
        (SELECT COUNT(*) FROM equipment_link WHERE organization_id = v_org_id);
END $$;

-- 4.5. equipment_capability для линий
DO $$
DECLARE
v_org_id UUID := '00000000-0000-0000-0000-000000000001';
    v_l1 UUID; v_l2 UUID; v_l3 UUID;
    v_gc1 UUID; v_gc5 UUID; v_gd1 UUID; v_ga10 UUID;
BEGIN
SELECT id INTO v_l1 FROM equipment WHERE organization_id = v_org_id AND code = 'LINE_1';
SELECT id INTO v_l2 FROM equipment WHERE organization_id = v_org_id AND code = 'LINE_2';
SELECT id INTO v_l3 FROM equipment WHERE organization_id = v_org_id AND code = 'LINE_3';

SELECT id INTO v_gc1  FROM product WHERE organization_id = v_org_id AND code = 'GP_CREAM_1L';
SELECT id INTO v_gc5  FROM product WHERE organization_id = v_org_id AND code = 'GP_CREAM_5L';
SELECT id INTO v_gd1  FROM product WHERE organization_id = v_org_id AND code = 'GP_DISH_1L';
SELECT id INTO v_ga10 FROM product WHERE organization_id = v_org_id AND code = 'GP_ANTISEPTIC_10L';

IF v_l1 IS NULL OR v_gc1 IS NULL THEN
        RAISE WARNING 'Не найдены LINE_1 или GP_CREAM_1L';
        RETURN;
END IF;

INSERT INTO equipment_capability (organization_id, equipment_id, product_id, max_fill_percent) VALUES
                                                                                                   (v_org_id, v_l1, v_gc1,  1.0),
                                                                                                   (v_org_id, v_l1, v_gd1,  1.0),
                                                                                                   (v_org_id, v_l2, v_gc5,  1.0),
                                                                                                   (v_org_id, v_l2, v_ga10, 1.0),
                                                                                                   (v_org_id, v_l3, v_ga10, 1.0)
    ON CONFLICT DO NOTHING;

RAISE NOTICE 'equipment_capability всего: %',
        (SELECT COUNT(*) FROM equipment_capability WHERE organization_id = v_org_id);
END $$;

-- 4.6. Пересоздать 28 партий по ТЗ
DO $$
DECLARE
v_org_id UUID := '00000000-0000-0000-0000-000000000001';
    v_r1 UUID; v_r2 UUID; v_r3 UUID; v_r4 UUID;
    v_pf_cream UUID; v_pf_dish UUID; v_pf_antiseptic UUID;
    v_o_c1 UUID; v_o_c5 UUID; v_o_d1 UUID; v_o_a10 UUID;
BEGIN
SELECT id INTO v_r1 FROM equipment WHERE organization_id = v_org_id AND code = 'REACTOR_1';
SELECT id INTO v_r2 FROM equipment WHERE organization_id = v_org_id AND code = 'REACTOR_2';
SELECT id INTO v_r3 FROM equipment WHERE organization_id = v_org_id AND code = 'REACTOR_3';
SELECT id INTO v_r4 FROM equipment WHERE organization_id = v_org_id AND code = 'REACTOR_4';

SELECT id INTO v_pf_cream      FROM product WHERE organization_id = v_org_id AND code = 'PF_CREAM';
SELECT id INTO v_pf_dish       FROM product WHERE organization_id = v_org_id AND code = 'PF_DISH';
SELECT id INTO v_pf_antiseptic FROM product WHERE organization_id = v_org_id AND code = 'PF_ANTISEPTIC';

SELECT po.id INTO v_o_c1
FROM production_order po JOIN product p ON po.product_id = p.id
WHERE po.organization_id = v_org_id AND p.code = 'GP_CREAM_1L';

SELECT po.id INTO v_o_c5
FROM production_order po JOIN product p ON po.product_id = p.id
WHERE po.organization_id = v_org_id AND p.code = 'GP_CREAM_5L';

SELECT po.id INTO v_o_d1
FROM production_order po JOIN product p ON po.product_id = p.id
WHERE po.organization_id = v_org_id AND p.code = 'GP_DISH_1L';

SELECT po.id INTO v_o_a10
FROM production_order po JOIN product p ON po.product_id = p.id
WHERE po.organization_id = v_org_id AND p.code = 'GP_ANTISEPTIC_10L';

IF v_o_c1 IS NULL THEN
        RAISE WARNING 'Не найден заказ GP_CREAM_1L — пропускаю пересоздание партий';
        RETURN;
END IF;

DELETE FROM batch WHERE organization_id = v_org_id;

-- Крем-мыло 1л (Р1): 5×3500 + 1×2500 = 20 000 кг
INSERT INTO batch (organization_id, order_id, product_id, volume_kg, assigned_equipment_id) VALUES
                                                                                                (v_org_id, v_o_c1, v_pf_cream, 3500, v_r1),
                                                                                                (v_org_id, v_o_c1, v_pf_cream, 3500, v_r1),
                                                                                                (v_org_id, v_o_c1, v_pf_cream, 3500, v_r1),
                                                                                                (v_org_id, v_o_c1, v_pf_cream, 3500, v_r1),
                                                                                                (v_org_id, v_o_c1, v_pf_cream, 3500, v_r1),
                                                                                                (v_org_id, v_o_c1, v_pf_cream, 2500, v_r1);

-- Крем-мыло 5л (Р2): 3×7000 + 1×4000 = 25 000 кг
INSERT INTO batch (organization_id, order_id, product_id, volume_kg, assigned_equipment_id) VALUES
                                                                                                (v_org_id, v_o_c5, v_pf_cream, 7000, v_r2),
                                                                                                (v_org_id, v_o_c5, v_pf_cream, 7000, v_r2),
                                                                                                (v_org_id, v_o_c5, v_pf_cream, 7000, v_r2),
                                                                                                (v_org_id, v_o_c5, v_pf_cream, 4000, v_r2);

-- Средство 1л (Р2 + Р3): 2×7000 + 1×1000 = 15 000 кг
INSERT INTO batch (organization_id, order_id, product_id, volume_kg, assigned_equipment_id) VALUES
                                                                                                (v_org_id, v_o_d1, v_pf_dish, 7000, v_r2),
                                                                                                (v_org_id, v_o_d1, v_pf_dish, 7000, v_r2),
                                                                                                (v_org_id, v_o_d1, v_pf_dish, 1000, v_r3);

-- Антисептик 10л (Р3): 14×5600 = 78 400 кг
INSERT INTO batch (organization_id, order_id, product_id, volume_kg, assigned_equipment_id)
SELECT v_org_id, v_o_a10, v_pf_antiseptic, 5600, v_r3
FROM generate_series(1, 14);

-- Антисептик 10л (Р4): 1×1600 = 1600 кг
INSERT INTO batch (organization_id, order_id, product_id, volume_kg, assigned_equipment_id) VALUES
    (v_org_id, v_o_a10, v_pf_antiseptic, 1600, v_r4);

RAISE NOTICE 'Создано партий: %',
        (SELECT COUNT(*) FROM batch WHERE organization_id = v_org_id);
END $$;

-- 4.7. Обновить route_type и max_fill_percent
UPDATE product SET route_type = 'VIA_TANK'
WHERE organization_id = '00000000-0000-0000-0000-000000000001' AND code = 'PF_CREAM';

UPDATE product SET route_type = 'DIRECT'
WHERE organization_id = '00000000-0000-0000-0000-000000000001' AND code IN ('PF_DISH', 'PF_ANTISEPTIC');

UPDATE equipment_capability SET max_fill_percent = 0.70
WHERE organization_id = '00000000-0000-0000-0000-000000000001';


-- ==========================================
-- ADD_05: Включаем материальные ограничения
-- ==========================================
INSERT INTO organization_settings (organization_id, setting_key, setting_value, description) VALUES
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'enable_material_constraints',
                                                                                                  'true', 'Учёт остатков сырья в планировщике (Итерация 2)'),
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'enable_advisor',
                                                                                                  'true', 'Подсказки планировщика (Итерация 2)')
    ON CONFLICT (organization_id, setting_key) DO UPDATE
                                                      SET setting_value = EXCLUDED.setting_value,
                                                      description = EXCLUDED.description;


-- ==========================================
-- ИТОГОВАЯ ПРОВЕРКА
-- ==========================================
SELECT 'equipment (с code)'     AS table_name, COUNT(*) AS rows
FROM equipment WHERE organization_id = '00000000-0000-0000-0000-000000000001' AND code IS NOT NULL
UNION ALL SELECT 'equipment_link',       COUNT(*)
          FROM equipment_link WHERE organization_id = '00000000-0000-0000-0000-000000000001'
          UNION ALL SELECT 'equipment_capability', COUNT(*)
          FROM equipment_capability WHERE organization_id = '00000000-0000-0000-0000-000000000001'
          UNION ALL SELECT 'batch',                COUNT(*)
          FROM batch WHERE organization_id = '00000000-0000-0000-0000-000000000001'
          UNION ALL SELECT 'organization_settings',COUNT(*)
          FROM organization_settings WHERE organization_id = '00000000-0000-0000-0000-000000000001';

-- Ожидаемый результат:
--   equipment (с code):      9
--   equipment_link:          7
--   equipment_capability:   11
--   batch:                  28
--   organization_settings:  17