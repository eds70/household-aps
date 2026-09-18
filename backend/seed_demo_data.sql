-- ==========================================
-- ДЕМОНСТРАЦИОННЫЕ ДАННЫЕ
-- Кейс из Раздела 4 ТЗ
-- Сентябрь 2026
-- Версия: 1.4.0 (согласовано с init_schema.sql v1.4.0)
-- ==========================================
-- Что создаётся:
--   - 1 организация, 1 админ
--   - 11 материалов с остатками
--   - 3 ПФ (крем-мыло VIA_TANK, средство DIRECT, антисептик DIRECT)
--   - 4 ГП
--   - 4 реактора + 1 бойлер + 1 танк + 3 линии (все с code)
--   - 7 связей equipment_link
--   - 11 записей equipment_capability (6 реакторных + 5 линейных)
--   - 4 ресурсных пула
--   - 3 рецептуры
--   - 3 техкарты (11/8/8 операций)
--   - Матрица замывки 3×3
--   - 5 событий календаря (4 выходных + 1 ремонт Р3)
--   - 30 смен на сентябрь 2026 (08:00-20:00, сб-вс нерабочие)
--   - 4 производственных заказа
--   - 28 партий (пересчитано точно по ТЗ)
-- ==========================================

DO $$
DECLARE
v_org_id UUID := '00000000-0000-0000-0000-000000000001';
    v_admin_id UUID;

    -- Материалы
    v_mat_water UUID; v_mat_salt UUID; v_mat_fragrance UUID; v_mat_glycerin UUID;
    v_mat_betaine UUID; v_mat_alcohol UUID; v_mat_chloride UUID;
    v_mat_btl1 UUID; v_mat_btl5 UUID; v_mat_btl10 UUID; v_mat_cap UUID;

    -- Продукты (ПФ)
    v_pf_cream UUID; v_pf_dish UUID; v_pf_antiseptic UUID;

    -- Продукты (ГП)
    v_gp_cream_1 UUID; v_gp_cream_5 UUID; v_gp_dish_1 UUID; v_gp_antiseptic_10 UUID;

    -- Оборудование
    v_reactor1 UUID; v_reactor2 UUID; v_reactor3 UUID; v_reactor4 UUID;
    v_tank1 UUID;
    v_line1 UUID; v_line2 UUID; v_line3 UUID;
    v_boiler UUID;

    -- Рецептуры
    v_recipe_cream UUID; v_recipe_dish UUID; v_recipe_antiseptic UUID;

    -- Заказы
    v_order_cream_1 UUID; v_order_cream_5 UUID; v_order_dish_1 UUID; v_order_antiseptic_10 UUID;

    -- Смены
    v_date DATE;
    v_end_date DATE;
    v_starts_at TIMESTAMPTZ;
    v_ends_at TIMESTAMPTZ;
    v_dow INT;
    v_shift_name VARCHAR(50);
    v_shift_is_working BOOLEAN;
BEGIN

-- ==========================================
-- 1. ОРГАНИЗАЦИЯ И АДМИН
-- ==========================================
INSERT INTO organization (id, name, slug, settings)
VALUES (v_org_id, 'Бытовая Химия ООО', 'household-demo',
        '{"work_start": "08:00", "work_end": "20:00"}')
    ON CONFLICT (id) DO NOTHING;

v_admin_id := gen_random_uuid();
INSERT INTO app_user (id, organization_id, email, full_name, role)
VALUES (v_admin_id, v_org_id, 'admin@household.ru', 'Иванов Иван Иванович', 'ADMIN')
    ON CONFLICT DO NOTHING;

-- ==========================================
-- 2. МАТЕРИАЛЫ
-- ==========================================
v_mat_water := gen_random_uuid(); v_mat_salt := gen_random_uuid();
v_mat_fragrance := gen_random_uuid(); v_mat_glycerin := gen_random_uuid();
v_mat_betaine := gen_random_uuid(); v_mat_alcohol := gen_random_uuid();
v_mat_chloride := gen_random_uuid();
v_mat_btl1 := gen_random_uuid(); v_mat_btl5 := gen_random_uuid();
v_mat_btl10 := gen_random_uuid(); v_mat_cap := gen_random_uuid();

INSERT INTO material (id, organization_id, code, name, unit, category) VALUES
                                                                           (v_mat_water,     v_org_id, 'WATER',     'Вода',                 'kg', 'RAW'),
                                                                           (v_mat_salt,      v_org_id, 'SALT',      'Соль экстра',          'kg', 'RAW'),
                                                                           (v_mat_fragrance, v_org_id, 'FRAGRANCE', 'Отдушка цветочная',    'kg', 'RAW'),
                                                                           (v_mat_glycerin,  v_org_id, 'GLYCERIN',  'Глицерин',             'kg', 'RAW'),
                                                                           (v_mat_betaine,   v_org_id, 'BETAINE',   'Бетаин',               'kg', 'RAW'),
                                                                           (v_mat_alcohol,   v_org_id, 'ALCOHOL',   'Спирт',                'kg', 'RAW'),
                                                                           (v_mat_chloride,  v_org_id, 'CHLORIDE',  'Хлорид',               'kg', 'RAW'),
                                                                           (v_mat_btl1,      v_org_id, 'BTL1',      'Бутылки 1 литр',       'pc', 'PACKAGING'),
                                                                           (v_mat_btl5,      v_org_id, 'BTL5',      'Бутылки 5 литров',     'pc', 'PACKAGING'),
                                                                           (v_mat_btl10,     v_org_id, 'BTL10',     'Бутылки 10 литров',    'pc', 'PACKAGING'),
                                                                           (v_mat_cap,       v_org_id, 'CAP',       'Крышки универсальные', 'pc', 'PACKAGING')
    ON CONFLICT DO NOTHING;

INSERT INTO material_stock (organization_id, material_id, qty) VALUES
                                                                   (v_org_id, v_mat_water, 100000),
                                                                   (v_org_id, v_mat_salt, 3000),
                                                                   (v_org_id, v_mat_fragrance, 1500),
                                                                   (v_org_id, v_mat_glycerin, 4000),
                                                                   (v_org_id, v_mat_betaine, 1000),
                                                                   (v_org_id, v_mat_alcohol, 30000),
                                                                   (v_org_id, v_mat_chloride, 5000),
                                                                   (v_org_id, v_mat_btl1, 30000),
                                                                   (v_org_id, v_mat_btl5, 10000),
                                                                   (v_org_id, v_mat_btl10, 10000),
                                                                   (v_org_id, v_mat_cap, 40000)
    ON CONFLICT DO NOTHING;

-- ==========================================
-- 3. ПРОДУКЦИЯ: ПФ (с route_type)
-- ==========================================
v_pf_cream := gen_random_uuid();
v_pf_dish := gen_random_uuid();
v_pf_antiseptic := gen_random_uuid();

INSERT INTO product (id, organization_id, code, name, type, viscosity_coeff, requires_heating, route_type) VALUES
                                                                                                               (v_pf_cream,      v_org_id, 'PF_CREAM',      'Крем-мыло',                'PF', 1.3, TRUE,  'VIA_TANK'),
                                                                                                               (v_pf_dish,       v_org_id, 'PF_DISH',       'Средство для мытья посуды','PF', 1.0, FALSE, 'DIRECT'),
                                                                                                               (v_pf_antiseptic, v_org_id, 'PF_ANTISEPTIC', 'Антисептик',               'PF', 0.8, FALSE, 'DIRECT')
    ON CONFLICT DO NOTHING;

-- ==========================================
-- 4. ПРОДУКЦИЯ: ГП
-- ==========================================
v_gp_cream_1 := gen_random_uuid();
v_gp_cream_5 := gen_random_uuid();
v_gp_dish_1 := gen_random_uuid();
v_gp_antiseptic_10 := gen_random_uuid();

INSERT INTO product (id, organization_id, code, name, type, viscosity_coeff, bottle_volume_l, fill_speed_per_min, parent_pf_id) VALUES
                                                                                                                                    (v_gp_cream_1,      v_org_id, 'GP_CREAM_1L',      'Крем-мыло 1л',                 'GP', 1.3,  1.0, 10, v_pf_cream),
                                                                                                                                    (v_gp_cream_5,      v_org_id, 'GP_CREAM_5L',      'Крем-мыло 5л',                 'GP', 1.3,  5.0,  1, v_pf_cream),
                                                                                                                                    (v_gp_dish_1,       v_org_id, 'GP_DISH_1L',       'Средство для мытья посуды 1л', 'GP', 1.0,  1.0,  5, v_pf_dish),
                                                                                                                                    (v_gp_antiseptic_10,v_org_id, 'GP_ANTISEPTIC_10L','Антисептик 10л',               'GP', 0.8, 10.0,  1, v_pf_antiseptic)
    ON CONFLICT DO NOTHING;

-- ==========================================
-- 5. ОБОРУДОВАНИЕ (все с code)
-- ==========================================
v_reactor1 := gen_random_uuid(); v_reactor2 := gen_random_uuid();
v_reactor3 := gen_random_uuid(); v_reactor4 := gen_random_uuid();

INSERT INTO equipment (id, organization_id, code, name, type, volume_kg, speed_coeff, mixer_type) VALUES
                                                                                                      (v_reactor1, v_org_id, 'REACTOR_1', 'Реактор 1', 'REACTOR',  5000, 1.0, 'standard'),
                                                                                                      (v_reactor2, v_org_id, 'REACTOR_2', 'Реактор 2', 'REACTOR', 10000, 1.2, 'high_speed'),
                                                                                                      (v_reactor3, v_org_id, 'REACTOR_3', 'Реактор 3', 'REACTOR',  8000, 1.1, 'standard'),
                                                                                                      (v_reactor4, v_org_id, 'REACTOR_4', 'Реактор 4', 'REACTOR',  5000, 0.9, 'low_speed')
    ON CONFLICT DO NOTHING;

v_boiler := gen_random_uuid();
INSERT INTO equipment (id, organization_id, code, name, type, volume_kg)
VALUES (v_boiler, v_org_id, 'BOILER', 'Бойлер', 'BOILER', 2000)
    ON CONFLICT DO NOTHING;

v_tank1 := gen_random_uuid();
INSERT INTO equipment (id, organization_id, code, name, type, volume_kg, speed_coeff)
VALUES (v_tank1, v_org_id, 'TANK_1', 'Накопительная емкость 1', 'TANK', 5000, 1.0)
    ON CONFLICT DO NOTHING;

v_line1 := gen_random_uuid(); v_line2 := gen_random_uuid(); v_line3 := gen_random_uuid();

INSERT INTO equipment (id, organization_id, code, name, type, speed_coeff) VALUES
                                                                               (v_line1, v_org_id, 'LINE_1', 'Линия 1 (1л)',              'FILLING_LINE',   10),
                                                                               (v_line2, v_org_id, 'LINE_2', 'Линия 2 (5/10л)',           'FILLING_LINE',    5),
                                                                               (v_line3, v_org_id, 'LINE_3', 'Линия 3 (ручной слив 10л)', 'MANUAL_STATION',  0.2)
    ON CONFLICT DO NOTHING;

-- ==========================================
-- 6. СВЯЗИ ОБОРУДОВАНИЯ (7 связей)
-- ==========================================
INSERT INTO equipment_link (organization_id, from_equipment_id, to_equipment_id, is_direct) VALUES
                                                                                                (v_org_id, v_reactor1, v_tank1,  TRUE),
                                                                                                (v_org_id, v_tank1,    v_line1,  TRUE),
                                                                                                (v_org_id, v_reactor1, v_line1,  TRUE),
                                                                                                (v_org_id, v_reactor2, v_line1,  TRUE),
                                                                                                (v_org_id, v_reactor2, v_line2,  TRUE),
                                                                                                (v_org_id, v_reactor3, v_line2,  TRUE),
                                                                                                (v_org_id, v_reactor4, v_line3,  TRUE);

-- ==========================================
-- 7. МАТРИЦА СОВМЕСТИМОСТИ (11 записей)
-- ==========================================
INSERT INTO equipment_capability (organization_id, equipment_id, product_id, max_fill_percent) VALUES
                                                                                                   -- 6 реакторных
                                                                                                   (v_org_id, v_reactor1, v_pf_cream,      0.70),
                                                                                                   (v_org_id, v_reactor2, v_pf_cream,      0.70),
                                                                                                   (v_org_id, v_reactor2, v_pf_dish,       0.70),
                                                                                                   (v_org_id, v_reactor3, v_pf_dish,       0.70),
                                                                                                   (v_org_id, v_reactor3, v_pf_antiseptic, 0.70),
                                                                                                   (v_org_id, v_reactor4, v_pf_antiseptic, 0.70),
                                                                                                   -- 5 линейных
                                                                                                   (v_org_id, v_line1, v_gp_cream_1,       1.0),
                                                                                                   (v_org_id, v_line1, v_gp_dish_1,        1.0),
                                                                                                   (v_org_id, v_line2, v_gp_cream_5,       1.0),
                                                                                                   (v_org_id, v_line2, v_gp_antiseptic_10, 1.0),
                                                                                                   (v_org_id, v_line3, v_gp_antiseptic_10, 1.0)
    ON CONFLICT DO NOTHING;

-- ==========================================
-- 8. РЕСУРСНЫЕ ПУЛЫ (Итерация 6 + 7)
-- ==========================================
-- 6 пулов операторов по ТЗ:
--   REACTOR_OPERATOR — 3 аппаратчика на 4 реактора
--   LINE_OPERATOR    — 2 оператора на 3 линии розлива
--   MANUAL_OPERATOR  — 1 оператор ручной станции (LINE_3)
--   LAB              — 1 лаборант
--   COOLING_ZONE     — 2 реактора могут остывать одновременно (Итерация 7)
--   BOILER           — 1 бойлер
--
-- ВАЖНО: тип OPERATOR устарел (удален в add_09.sql). Используем
-- актуальные типы, иначе планировщик не применит OperatorPoolConstraint
-- и LabConstraint.
--
-- ON CONFLICT DO UPDATE обеспечивает идемпотентность: повторное
-- применение не создаст дублей и обновит существующие записи.

INSERT INTO resource_pool (organization_id, name, type, capacity, comment) VALUES
                                                                               (v_org_id, 'Аппаратчики реакторов',    'REACTOR_OPERATOR', 3, 'По ТЗ — 3 человека на 4 реактора. Итерация 6.'),
                                                                               (v_org_id, 'Операторы линий розлива',  'LINE_OPERATOR',    2, 'Работают на линиях розлива. Итерация 6.'),
                                                                               (v_org_id, 'Операторы ручной станции', 'MANUAL_OPERATOR',  1, 'Обслуживают ручную станцию (LINE_3). Итерация 6.'),
                                                                               (v_org_id, 'Лаборатория',              'LAB',              1, 'Один лаборант. Итерация 6.'),
                                                                               (v_org_id, 'Зона охлаждения',          'COOLING_ZONE',     2, 'Максимум 2 реактора остывают одновременно. Итерация 7.'),
                                                                               (v_org_id, 'Бойлер',                   'BOILER',           1, 'Один бойлер на весь цех.')
    ON CONFLICT (organization_id, type) DO UPDATE
                                               SET name = EXCLUDED.name,
                                               capacity = EXCLUDED.capacity,
                                               comment = EXCLUDED.comment,
                                               updated_at = NOW();

-- ==========================================
-- 9. РЕЦЕПТУРЫ
-- ==========================================
v_recipe_cream := gen_random_uuid();
INSERT INTO recipe (id, organization_id, product_id, base_volume_kg)
VALUES (v_recipe_cream, v_org_id, v_pf_cream, 100);

INSERT INTO recipe_item (recipe_id, material_id, qty_per_base) VALUES
                                                                   (v_recipe_cream, v_mat_water, 85),
                                                                   (v_recipe_cream, v_mat_salt, 5),
                                                                   (v_recipe_cream, v_mat_fragrance, 2),
                                                                   (v_recipe_cream, v_mat_glycerin, 8);

v_recipe_dish := gen_random_uuid();
INSERT INTO recipe (id, organization_id, product_id, base_volume_kg)
VALUES (v_recipe_dish, v_org_id, v_pf_dish, 100);

INSERT INTO recipe_item (recipe_id, material_id, qty_per_base) VALUES
                                                                   (v_recipe_dish, v_mat_water, 70),
                                                                   (v_recipe_dish, v_mat_salt, 15),
                                                                   (v_recipe_dish, v_mat_fragrance, 5),
                                                                   (v_recipe_dish, v_mat_betaine, 6),
                                                                   (v_recipe_dish, v_mat_alcohol, 4);

v_recipe_antiseptic := gen_random_uuid();
INSERT INTO recipe (id, organization_id, product_id, base_volume_kg)
VALUES (v_recipe_antiseptic, v_org_id, v_pf_antiseptic, 100);

INSERT INTO recipe_item (recipe_id, material_id, qty_per_base) VALUES
                                                                   (v_recipe_antiseptic, v_mat_water, 60),
                                                                   (v_recipe_antiseptic, v_mat_alcohol, 35),
                                                                   (v_recipe_antiseptic, v_mat_chloride, 5);

-- ==========================================
-- 10. ТЕХНОЛОГИЧЕСКИЕ КАРТЫ
-- ==========================================

-- КРЕМ-МЫЛО (11 этапов)
INSERT INTO operation_template (organization_id, product_id, stage_order, name, base_duration_mins,
                                needs_boiler, needs_cooling_zone, needs_operator, needs_lab, duration_formula, parallel_group_id, operator_pool) VALUES
                                                                                                                                                     (v_org_id, v_pf_cream, 1,  'Загрузка сырья (вода)',            60,  FALSE, FALSE, TRUE,  FALSE, 'water_loading', NULL,     'REACTOR_OPERATOR'),
                                                                                                                                                     (v_org_id, v_pf_cream, 2,  'Нагрев воды',                      120, TRUE,  FALSE, FALSE, FALSE, 'heating',       NULL,     NULL),
                                                                                                                                                     (v_org_id, v_pf_cream, 3,  'Перемешивание',                    90,  FALSE, FALSE, TRUE,  FALSE, 'mixing',        'GROUP1', 'REACTOR_OPERATOR'),
                                                                                                                                                     (v_org_id, v_pf_cream, 4,  'Охлаждение 80→60°C',               120, FALSE, TRUE,  FALSE, FALSE, 'cooling',       'GROUP1', NULL),
                                                                                                                                                     (v_org_id, v_pf_cream, 5,  'Лабораторный анализ',              30,  FALSE, FALSE, FALSE, TRUE,  NULL,            NULL,     NULL),
                                                                                                                                                     (v_org_id, v_pf_cream, 6,  'Загрузка доп. сырья',              30,  FALSE, FALSE, TRUE,  FALSE, 'water_loading', NULL,     'REACTOR_OPERATOR'),
                                                                                                                                                     (v_org_id, v_pf_cream, 7,  'Перемешивание (2 этап)',           60,  FALSE, FALSE, TRUE,  FALSE, 'mixing',        'GROUP2', 'REACTOR_OPERATOR'),
                                                                                                                                                     (v_org_id, v_pf_cream, 8,  'Охлаждение 60→40°C',               120, FALSE, TRUE,  FALSE, FALSE, 'cooling',       'GROUP2', NULL),
                                                                                                                                                     (v_org_id, v_pf_cream, 9,  'Лабораторный анализ (финал)',      30,  FALSE, FALSE, FALSE, TRUE,  NULL,            NULL,     NULL),
                                                                                                                                                     (v_org_id, v_pf_cream, 10, 'Перекачка в накопительную емкость',60,  FALSE, FALSE, TRUE,  FALSE, 'pumping',       NULL,     'REACTOR_OPERATOR'),
                                                                                                                                                     (v_org_id, v_pf_cream, 11, 'Промывка реактора',                90,  FALSE, FALSE, TRUE,  FALSE, 'washing',       NULL,     'REACTOR_OPERATOR');

-- СРЕДСТВО ДЛЯ МЫТЬЯ ПОСУДЫ (8 этапов)
INSERT INTO operation_template (organization_id, product_id, stage_order, name, base_duration_mins,
                                needs_boiler, needs_cooling_zone, needs_operator, needs_lab, duration_formula, parallel_group_id, operator_pool) VALUES
                                                                                                                                                     (v_org_id, v_pf_dish, 1, 'Загрузка сырья (вода)', 60,  FALSE, FALSE, TRUE,  FALSE, 'water_loading', NULL,     'REACTOR_OPERATOR'),
                                                                                                                                                     (v_org_id, v_pf_dish, 2, 'Перемешивание',         120, FALSE, FALSE, TRUE,  FALSE, 'mixing',        'GROUP1', 'REACTOR_OPERATOR'),
                                                                                                                                                     (v_org_id, v_pf_dish, 3, 'Охлаждение 90→50°C',    90,  FALSE, TRUE,  FALSE, FALSE, 'cooling',       'GROUP1', NULL),
                                                                                                                                                     (v_org_id, v_pf_dish, 4, 'Лабораторный анализ',   30,  FALSE, FALSE, FALSE, TRUE,  NULL,            NULL,     NULL),
                                                                                                                                                     (v_org_id, v_pf_dish, 5, 'Перемешивание (2 этап)',60,  FALSE, FALSE, TRUE,  FALSE, 'mixing',        'GROUP2', 'REACTOR_OPERATOR'),
                                                                                                                                                     (v_org_id, v_pf_dish, 6, 'Охлаждение 50→30°C',    90,  FALSE, TRUE,  FALSE, FALSE, 'cooling',       'GROUP2', NULL),
                                                                                                                                                     (v_org_id, v_pf_dish, 7, 'Лабораторный анализ (финал)', 30, FALSE, FALSE, FALSE, TRUE, NULL,         NULL,     NULL),
                                                                                                                                                     (v_org_id, v_pf_dish, 8, 'Промывка реактора',     90,  FALSE, FALSE, TRUE,  FALSE, 'washing',       NULL,     'REACTOR_OPERATOR');

-- АНТИСЕПТИК (8 этапов)
INSERT INTO operation_template (organization_id, product_id, stage_order, name, base_duration_mins,
                                needs_boiler, needs_cooling_zone, needs_operator, needs_lab, duration_formula, parallel_group_id, operator_pool) VALUES
                                                                                                                                                     (v_org_id, v_pf_antiseptic, 1, 'Загрузка сырья (вода)',            60, FALSE, FALSE, TRUE,  FALSE, 'water_loading', NULL, 'REACTOR_OPERATOR'),
                                                                                                                                                     (v_org_id, v_pf_antiseptic, 2, 'Перемешивание',                    60, FALSE, FALSE, TRUE,  FALSE, 'mixing',        NULL, 'REACTOR_OPERATOR'),
                                                                                                                                                     (v_org_id, v_pf_antiseptic, 3, 'Лабораторный анализ',              30, FALSE, FALSE, FALSE, TRUE,  NULL,            NULL, NULL),
                                                                                                                                                     (v_org_id, v_pf_antiseptic, 4, 'Загрузка доп. сырья',              30, FALSE, FALSE, TRUE,  FALSE, 'water_loading', NULL, 'REACTOR_OPERATOR'),
                                                                                                                                                     (v_org_id, v_pf_antiseptic, 5, 'Перемешивание (2 этап)',           30, FALSE, FALSE, TRUE,  FALSE, 'mixing',        NULL, 'REACTOR_OPERATOR'),
                                                                                                                                                     (v_org_id, v_pf_antiseptic, 6, 'Лабораторный анализ (финал)',      30, FALSE, FALSE, FALSE, TRUE,  NULL,            NULL, NULL),
                                                                                                                                                     (v_org_id, v_pf_antiseptic, 7, 'Перекачка в накопительную емкость',45, FALSE, FALSE, TRUE,  FALSE, 'pumping',       NULL, 'REACTOR_OPERATOR'),
                                                                                                                                                     (v_org_id, v_pf_antiseptic, 8, 'Промывка реактора',                30, FALSE, FALSE, TRUE,  FALSE, 'washing',       NULL, 'REACTOR_OPERATOR');

-- ==========================================
-- 11. МАТРИЦА ЗАМЫВКИ
-- ==========================================
INSERT INTO setup_matrix (organization_id, from_product_id, to_product_id, setup_mins) VALUES
                                                                                           (v_org_id, v_pf_cream,      v_pf_cream,      30),
                                                                                           (v_org_id, v_pf_cream,      v_pf_dish,       90),
                                                                                           (v_org_id, v_pf_cream,      v_pf_antiseptic, 90),
                                                                                           (v_org_id, v_pf_dish,       v_pf_dish,       30),
                                                                                           (v_org_id, v_pf_dish,       v_pf_cream,      90),
                                                                                           (v_org_id, v_pf_dish,       v_pf_antiseptic, 90),
                                                                                           (v_org_id, v_pf_antiseptic, v_pf_antiseptic, 30),
                                                                                           (v_org_id, v_pf_antiseptic, v_pf_cream,      90),
                                                                                           (v_org_id, v_pf_antiseptic, v_pf_dish,       90)
    ON CONFLICT DO NOTHING;

-- ==========================================
-- 12. КАЛЕНДАРЬ ПРОСТОЕВ (сентябрь 2026)
-- ==========================================
INSERT INTO calendar_event (organization_id, event_type, starts_at, ends_at, comment) VALUES
                                                                                          (v_org_id, 'WEEKEND', '2026-09-05 00:00:00+03', '2026-09-07 00:00:00+03', 'Выходные'),
                                                                                          (v_org_id, 'WEEKEND', '2026-09-12 00:00:00+03', '2026-09-14 00:00:00+03', 'Выходные'),
                                                                                          (v_org_id, 'WEEKEND', '2026-09-19 00:00:00+03', '2026-09-21 00:00:00+03', 'Выходные'),
                                                                                          (v_org_id, 'WEEKEND', '2026-09-26 00:00:00+03', '2026-09-28 00:00:00+03', 'Выходные');

INSERT INTO calendar_event (organization_id, equipment_id, event_type, starts_at, ends_at, comment) VALUES
    (v_org_id, v_reactor3, 'REPAIR', '2026-09-10 00:00:00+03', '2026-09-21 00:00:00+03', 'Плановый ремонт Р3');

-- ==========================================
-- 13. СМЕНЫ НА СЕНТЯБРЬ 2026 (Итерация 3)
-- ==========================================
-- Одна смена в день: 08:00-20:00.
-- Суббота и воскресенье — нерабочие (is_working = FALSE).
-- Всего 30 смен: 22 рабочих + 8 выходных.

v_date := '2026-09-01';
v_end_date := '2026-09-30';

WHILE v_date <= v_end_date LOOP
    v_dow := EXTRACT(DOW FROM v_date);  -- 0=вс, 6=сб

    v_starts_at := (v_date::text || ' 08:00:00+03')::TIMESTAMPTZ;
    v_ends_at   := (v_date::text || ' 20:00:00+03')::TIMESTAMPTZ;

    v_shift_is_working := (v_dow <> 0 AND v_dow <> 6);
    v_shift_name := 'Смена ' || TO_CHAR(v_date, 'DD.MM.YYYY');

INSERT INTO shift (organization_id, name, starts_at, ends_at, is_working, comment)
VALUES (
           v_org_id,
           v_shift_name,
           v_starts_at,
           v_ends_at,
           v_shift_is_working,
           CASE WHEN v_shift_is_working THEN 'Рабочая смена' ELSE 'Выходной' END
       );

v_date := v_date + 1;
END LOOP;

-- ==========================================
-- 14. ПРОИЗВОДСТВЕННЫЕ ЗАКАЗЫ
-- ==========================================
INSERT INTO production_order (id, organization_id, product_id, target_qty, due_date, priority) VALUES
                                                                                                   (gen_random_uuid(), v_org_id, v_gp_cream_1,       20000, '2026-09-30 23:59:59+03', 5),
                                                                                                   (gen_random_uuid(), v_org_id, v_gp_cream_5,        5000, '2026-09-30 23:59:59+03', 5),
                                                                                                   (gen_random_uuid(), v_org_id, v_gp_dish_1,        15000, '2026-09-30 23:59:59+03', 5),
                                                                                                   (gen_random_uuid(), v_org_id, v_gp_antiseptic_10,  8000, '2026-09-30 23:59:59+03', 5);

-- Находим ID заказов
SELECT id INTO v_order_cream_1       FROM production_order WHERE product_id = v_gp_cream_1;
SELECT id INTO v_order_cream_5       FROM production_order WHERE product_id = v_gp_cream_5;
SELECT id INTO v_order_dish_1        FROM production_order WHERE product_id = v_gp_dish_1;
SELECT id INTO v_order_antiseptic_10 FROM production_order WHERE product_id = v_gp_antiseptic_10;

-- ==========================================
-- 15. ПАРТИИ (28 штук по ТЗ)
-- ==========================================
-- Крем-мыло 1л (Р1): 5×3500 + 1×2500 = 20 000 кг → 6 партий
INSERT INTO batch (organization_id, order_id, product_id, volume_kg, assigned_equipment_id) VALUES
                                                                                                (v_org_id, v_order_cream_1, v_pf_cream, 3500, v_reactor1),
                                                                                                (v_org_id, v_order_cream_1, v_pf_cream, 3500, v_reactor1),
                                                                                                (v_org_id, v_order_cream_1, v_pf_cream, 3500, v_reactor1),
                                                                                                (v_org_id, v_order_cream_1, v_pf_cream, 3500, v_reactor1),
                                                                                                (v_org_id, v_order_cream_1, v_pf_cream, 3500, v_reactor1),
                                                                                                (v_org_id, v_order_cream_1, v_pf_cream, 2500, v_reactor1);

-- Крем-мыло 5л (Р2): 3×7000 + 1×4000 = 25 000 кг → 4 партии
INSERT INTO batch (organization_id, order_id, product_id, volume_kg, assigned_equipment_id) VALUES
                                                                                                (v_org_id, v_order_cream_5, v_pf_cream, 7000, v_reactor2),
                                                                                                (v_org_id, v_order_cream_5, v_pf_cream, 7000, v_reactor2),
                                                                                                (v_org_id, v_order_cream_5, v_pf_cream, 7000, v_reactor2),
                                                                                                (v_org_id, v_order_cream_5, v_pf_cream, 4000, v_reactor2);

-- Средство 1л (Р2+Р3): 2×7000 + 1×1000 = 15 000 кг → 3 партии
INSERT INTO batch (organization_id, order_id, product_id, volume_kg, assigned_equipment_id) VALUES
                                                                                                (v_org_id, v_order_dish_1, v_pf_dish, 7000, v_reactor2),
                                                                                                (v_org_id, v_order_dish_1, v_pf_dish, 7000, v_reactor2),
                                                                                                (v_org_id, v_order_dish_1, v_pf_dish, 1000, v_reactor3);

-- Антисептик 10л (Р3): 14×5600 = 78 400 кг
INSERT INTO batch (organization_id, order_id, product_id, volume_kg, assigned_equipment_id)
SELECT v_org_id, v_order_antiseptic_10, v_pf_antiseptic, 5600, v_reactor3
FROM generate_series(1, 14);

-- Антисептик 10л (Р4): 1×1600 = 1600 кг
INSERT INTO batch (organization_id, order_id, product_id, volume_kg, assigned_equipment_id) VALUES
    (v_org_id, v_order_antiseptic_10, v_pf_antiseptic, 1600, v_reactor4);

END $$;

-- ==========================================
-- ФИНАЛЬНАЯ ПРОВЕРКА
-- ==========================================
SELECT 'organization' AS table_name, COUNT(*) AS rows FROM organization
UNION ALL SELECT 'app_user',           COUNT(*) FROM app_user
          UNION ALL SELECT 'material',           COUNT(*) FROM material
          UNION ALL SELECT 'material_stock',     COUNT(*) FROM material_stock
          UNION ALL SELECT 'product (PF)',       COUNT(*) FROM product WHERE type = 'PF'
          UNION ALL SELECT 'product (GP)',       COUNT(*) FROM product WHERE type = 'GP'
          UNION ALL SELECT 'equipment (code)',   COUNT(*) FROM equipment WHERE code IS NOT NULL
          UNION ALL SELECT 'equipment_link',     COUNT(*) FROM equipment_link
          UNION ALL SELECT 'equipment_capability', COUNT(*) FROM equipment_capability
          UNION ALL SELECT 'resource_pool',      COUNT(*) FROM resource_pool
          UNION ALL SELECT 'recipe',             COUNT(*) FROM recipe
          UNION ALL SELECT 'recipe_item',        COUNT(*) FROM recipe_item
          UNION ALL SELECT 'operation_template', COUNT(*) FROM operation_template
          UNION ALL SELECT 'setup_matrix',       COUNT(*) FROM setup_matrix
          UNION ALL SELECT 'calendar_event',     COUNT(*) FROM calendar_event
          UNION ALL SELECT 'shift (сентябрь)',   COUNT(*) FROM shift WHERE starts_at >= '2026-09-01' AND starts_at < '2026-10-01'
          UNION ALL SELECT 'shift (рабочих)',    COUNT(*) FROM shift WHERE is_working = TRUE
          UNION ALL SELECT 'production_order',   COUNT(*) FROM production_order
          UNION ALL SELECT 'batch',              COUNT(*) FROM batch
          UNION ALL SELECT 'organization_settings', COUNT(*) FROM organization_settings;

-- ==========================================
-- ОЖИДАЕМЫЙ РЕЗУЛЬТАТ:
--   organization:           1
--   app_user:               1
--   material:               11
--   material_stock:         11
--   product (PF):           3
--   product (GP):           4
--   equipment (code):       9
--   equipment_link:         7
--   equipment_capability:   11
--   resource_pool:          4
--   recipe:                 3
--   recipe_item:            12
--   operation_template:     27
--   setup_matrix:           9
--   calendar_event:         5
--   shift (сентябрь):       30
--   shift (рабочих):        22
--   production_order:       4
--   batch:                  28
--   organization_settings:  17
-- ==========================================