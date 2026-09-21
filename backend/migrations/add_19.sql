-- ==========================================
-- МИГРАЦИЯ 19: TANK_2 для крем-мыла 5л (Итерация 13.4, fix C2)
-- ==========================================
-- Проблема: PF_CREAM помечен route_type='VIA_TANK', но только Р1
-- подключён к TANK_1. Р2 (где варится крем-мыло 5л) — без танка,
-- Advisor выдаёт ROUTE_MISMATCH.
--
-- Решение: создать TANK_2 (10 000 кг) и связать с Р2 и LINE_2.
--
-- Идемпотентна: можно применять повторно.
-- ==========================================

DO $$
DECLARE
v_org_id UUID := '00000000-0000-0000-0000-000000000001';
    v_r2_id UUID;
    v_tank2_id UUID;
    v_line2_id UUID;
    v_existing_tank2 UUID;
BEGIN
    -- 1. Находим Р2 и LINE_2
SELECT id INTO v_r2_id
FROM equipment
WHERE organization_id = v_org_id AND code = 'REACTOR_2';

SELECT id INTO v_line2_id
FROM equipment
WHERE organization_id = v_org_id AND code = 'LINE_2';

IF v_r2_id IS NULL THEN
        RAISE EXCEPTION 'REACTOR_2 не найден для org %', v_org_id;
END IF;
    IF v_line2_id IS NULL THEN
        RAISE EXCEPTION 'LINE_2 не найден для org %', v_org_id;
END IF;

    -- 2. Проверяем, есть ли уже TANK_2
SELECT id INTO v_existing_tank2
FROM equipment
WHERE organization_id = v_org_id AND code = 'TANK_2';

IF v_existing_tank2 IS NULL THEN
        -- Создаём TANK_2 (объём = под Р2, 10 000 кг)
        v_tank2_id := gen_random_uuid();
INSERT INTO equipment (
    id, organization_id, code, name, type, volume_kg, speed_coeff
) VALUES (
             v_tank2_id, v_org_id, 'TANK_2',
             'Накопительная емкость 2', 'TANK', 10000, 1.0
         );
RAISE NOTICE 'Создан TANK_2 с id=%', v_tank2_id;
ELSE
        v_tank2_id := v_existing_tank2;
        RAISE NOTICE 'TANK_2 уже существует, id=%', v_tank2_id;
END IF;

    -- 3. Связываем Р2 → TANK_2 (если ещё нет)
INSERT INTO equipment_link (organization_id, from_equipment_id, to_equipment_id, is_direct)
VALUES (v_org_id, v_r2_id, v_tank2_id, TRUE)
    ON CONFLICT (from_equipment_id, to_equipment_id) DO NOTHING;

-- 4. Связываем TANK_2 → LINE_2 (если ещё нет)
INSERT INTO equipment_link (organization_id, from_equipment_id, to_equipment_id, is_direct)
VALUES (v_org_id, v_tank2_id, v_line2_id, TRUE)
    ON CONFLICT (from_equipment_id, to_equipment_id) DO NOTHING;

RAISE NOTICE 'Связи Р2→TANK_2→LINE_2 созданы/проверены';
END $$;

-- ==========================================
-- ФИНАЛЬНАЯ ПРОВЕРКА
-- ==========================================
SELECT 'TANK_2' AS check_name, id, name, volume_kg
FROM equipment
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
  AND code = 'TANK_2';

SELECT
    e1.code AS from_eq, e2.code AS to_eq, el.is_direct
FROM equipment_link el
         JOIN equipment e1 ON e1.id = el.from_equipment_id
         JOIN equipment e2 ON e2.id = el.to_equipment_id
WHERE e1.organization_id = '00000000-0000-0000-0000-000000000001'
  AND (e1.code = 'REACTOR_2' OR e1.code = 'TANK_2')
ORDER BY e1.code, e2.code;

-- Ожидаемо:
--   TANK_2  | <uuid> | Накопительная емкость 2 | 10000
--
--   REACTOR_2 → TANK_2  (TRUE)
--   REACTOR_2 → LINE_1  (TRUE)
--   REACTOR_2 → LINE_2  (TRUE)
--   TANK_2    → LINE_2  (TRUE)