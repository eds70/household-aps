-- ==========================================
-- ДЕМОНСТРАЦИОННЫЕ ДАННЫЕ
-- Кейс из Раздела 4 ТЗ
-- Сентябрь 2026
-- ==========================================

-- Фиксированный ID организации для удобства
DO $$
DECLARE
    v_org_id UUID := '00000000-0000-0000-0000-000000000001';
    v_admin_id UUID;
    
    -- Материалы
    v_mat_water UUID;
    v_mat_salt UUID;
    v_mat_fragrance UUID;
    v_mat_glycerin UUID;
    v_mat_betaine UUID;
    v_mat_alcohol UUID;
    v_mat_chloride UUID;
    v_mat_btl1 UUID;
    v_mat_btl5 UUID;
    v_mat_btl10 UUID;
    v_mat_cap UUID;
    
    -- Продукты (ПФ)
    v_pf_cream UUID;
    v_pf_dish UUID;
    v_pf_antiseptic UUID;
    
    -- Продукты (ГП)
    v_gp_cream_1 UUID;
    v_gp_cream_5 UUID;
    v_gp_dish_1 UUID;
    v_gp_antiseptic_10 UUID;
    
    -- Оборудование
    v_reactor1 UUID;
    v_reactor2 UUID;
    v_reactor3 UUID;
    v_reactor4 UUID;
    v_tank1 UUID;
    v_line1 UUID;
    v_line2 UUID;
    v_line3 UUID;
    v_boiler UUID;
    
    -- Ресурсы
    v_res_operators UUID;
    v_res_cooling UUID;
    v_res_boiler UUID;
    
    -- Рецептуры
    v_recipe_cream UUID;
    v_recipe_dish UUID;
    v_recipe_antiseptic UUID;
BEGIN

-- ==========================================
-- 1. ОРГАНИЗАЦИЯ
-- ==========================================
INSERT INTO organization (id, name, slug, settings)
VALUES (v_org_id, 'Бытовая Химия ООО', 'household-demo', 
        '{"work_start": "08:00", "work_end": "20:00", "shifts_per_day": 2}')
ON CONFLICT (id) DO NOTHING;

-- Администратор
v_admin_id := gen_random_uuid();
INSERT INTO app_user (id, organization_id, email, full_name, role)
VALUES (v_admin_id, v_org_id, 'admin@household.ru', 'Иванов Иван Иванович', 'ADMIN')
ON CONFLICT DO NOTHING;

-- ==========================================
-- 2. МАТЕРИАЛЫ
-- ==========================================
v_mat_water := gen_random_uuid();
v_mat_salt := gen_random_uuid();
v_mat_fragrance := gen_random_uuid();
v_mat_glycerin := gen_random_uuid();
v_mat_betaine := gen_random_uuid();
v_mat_alcohol := gen_random_uuid();
v_mat_chloride := gen_random_uuid();
v_mat_btl1 := gen_random_uuid();
v_mat_btl5 := gen_random_uuid();
v_mat_btl10 := gen_random_uuid();
v_mat_cap := gen_random_uuid();

INSERT INTO material (id, organization_id, code, name, unit, category) VALUES
    (v_mat_water, v_org_id, 'WATER', 'Вода', 'kg', 'RAW'),
    (v_mat_salt, v_org_id, 'SALT', 'Соль экстра', 'kg', 'RAW'),
    (v_mat_fragrance, v_org_id, 'FRAGRANCE', 'Отдушка цветочная', 'kg', 'RAW'),
    (v_mat_glycerin, v_org_id, 'GLYCERIN', 'Глицерин', 'kg', 'RAW'),
    (v_mat_betaine, v_org_id, 'BETAINE', 'Бетаин', 'kg', 'RAW'),
    (v_mat_alcohol, v_org_id, 'ALCOHOL', 'Спирт', 'kg', 'RAW'),
    (v_mat_chloride, v_org_id, 'CHLORIDE', 'Хлорид', 'kg', 'RAW'),
    (v_mat_btl1, v_org_id, 'BTL1', 'Бутылки 1 литр', 'pc', 'PACKAGING'),
    (v_mat_btl5, v_org_id, 'BTL5', 'Бутылки 5 литров', 'pc', 'PACKAGING'),
    (v_mat_btl10, v_org_id, 'BTL10', 'Бутылки 10 литров', 'pc', 'PACKAGING'),
    (v_mat_cap, v_org_id, 'CAP', 'Крышки универсальные', 'pc', 'PACKAGING')
ON CONFLICT DO NOTHING;

-- Остатки на складе (из ТЗ)
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
-- 3. ПРОДУКЦИЯ: ПОЛУФАБРИКАТЫ (ПФ)
-- ==========================================
v_pf_cream := gen_random_uuid();
v_pf_dish := gen_random_uuid();
v_pf_antiseptic := gen_random_uuid();

INSERT INTO product (id, organization_id, code, name, type, viscosity_coeff, requires_heating) VALUES
    (v_pf_cream, v_org_id, 'PF_CREAM', 'Крем-мыло', 'PF', 1.3, TRUE),
    (v_pf_dish, v_org_id, 'PF_DISH', 'Средство для мытья посуды', 'PF', 1.0, FALSE),
    (v_pf_antiseptic, v_org_id, 'PF_ANTISEPTIC', 'Антисептик', 'PF', 0.8, FALSE)
ON CONFLICT DO NOTHING;

-- ==========================================
-- 4. ПРОДУКЦИЯ: ГОТОВАЯ ПРОДУКЦИЯ (ГП)
-- ==========================================
v_gp_cream_1 := gen_random_uuid();
v_gp_cream_5 := gen_random_uuid();
v_gp_dish_1 := gen_random_uuid();
v_gp_antiseptic_10 := gen_random_uuid();

INSERT INTO product (id, organization_id, code, name, type, viscosity_coeff, bottle_volume_l, fill_speed_per_min, parent_pf_id) VALUES
    (v_gp_cream_1, v_org_id, 'GP_CREAM_1L', 'Крем-мыло 1л', 'GP', 1.3, 1.0, 10, v_pf_cream),
    (v_gp_cream_5, v_org_id, 'GP_CREAM_5L', 'Крем-мыло 5л', 'GP', 1.3, 5.0, 1, v_pf_cream),
    (v_gp_dish_1, v_org_id, 'GP_DISH_1L', 'Средство для мытья посуды 1л', 'GP', 1.0, 1.0, 5, v_pf_dish),
    (v_gp_antiseptic_10, v_org_id, 'GP_ANTISEPTIC_10L', 'Антисептик 10л', 'GP', 0.8, 10.0, 1, v_pf_antiseptic)
ON CONFLICT DO NOTHING;

-- ==========================================
-- 5. ОБОРУДОВАНИЕ: РЕАКТОРЫ
-- ==========================================
v_reactor1 := gen_random_uuid();
v_reactor2 := gen_random_uuid();
v_reactor3 := gen_random_uuid();
v_reactor4 := gen_random_uuid();

INSERT INTO equipment (id, organization_id, name, type, volume_kg, speed_coeff, mixer_type) VALUES
    (v_reactor1, v_org_id, 'Реактор 1', 'REACTOR', 5000, 1.0, 'standard'),
    (v_reactor2, v_org_id, 'Реактор 2', 'REACTOR', 10000, 1.2, 'high_speed'),
    (v_reactor3, v_org_id, 'Реактор 3', 'REACTOR', 8000, 1.1, 'standard'),
    (v_reactor4, v_org_id, 'Реактор 4', 'REACTOR', 5000, 0.9, 'low_speed')
ON CONFLICT DO NOTHING;

-- Бойлер (общий ресурс)
v_boiler := gen_random_uuid();
INSERT INTO equipment (id, organization_id, name, type, volume_kg) VALUES
    (v_boiler, v_org_id, 'Бойлер', 'BOILER', 2000)
ON CONFLICT DO NOTHING;

-- ==========================================
-- 6. ОБОРУДОВАНИЕ: НАКОПИТЕЛЬНАЯ ЕМКОСТЬ
-- ==========================================
v_tank1 := gen_random_uuid();
INSERT INTO equipment (id, organization_id, name, type, volume_kg, speed_coeff) VALUES
    (v_tank1, v_org_id, 'Накопительная емкость 1', 'TANK', 5000, 1.0)
ON CONFLICT DO NOTHING;

-- ==========================================
-- 7. ОБОРУДОВАНИЕ: ЛИНИИ РОЗЛИВА
-- ==========================================
v_line1 := gen_random_uuid();
v_line2 := gen_random_uuid();
v_line3 := gen_random_uuid();

INSERT INTO equipment (id, organization_id, name, type, speed_coeff) VALUES
    (v_line1, v_org_id, 'Линия 1 (1л)', 'FILLING_LINE', 10),
    (v_line2, v_org_id, 'Линия 2 (5/10л)', 'FILLING_LINE', 5),
    (v_line3, v_org_id, 'Линия 3 (ручной слив 10л)', 'MANUAL_STATION', 0.2)
ON CONFLICT DO NOTHING;

-- ==========================================
-- 8. СВЯЗИ ОБОРУДОВАНИЯ (куда можно сливать)
-- ==========================================
-- Реактор 1 -> Накопительная емкость
INSERT INTO equipment_link (organization_id, from_equipment_id, to_equipment_id, is_direct) VALUES
    (v_org_id, v_reactor1, v_tank1, TRUE);

-- Реактор 1 -> Линия 1 (1л)
INSERT INTO equipment_link (organization_id, from_equipment_id, to_equipment_id, is_direct) VALUES
    (v_org_id, v_reactor1, v_line1, TRUE);

-- Реактор 2 -> Линия 1 (1л)
INSERT INTO equipment_link (organization_id, from_equipment_id, to_equipment_id, is_direct) VALUES
    (v_org_id, v_reactor2, v_line1, TRUE);

-- Реактор 2 -> Линия 2 (5/10л)
INSERT INTO equipment_link (organization_id, from_equipment_id, to_equipment_id, is_direct) VALUES
    (v_org_id, v_reactor2, v_line2, TRUE);

-- Реактор 3 -> Линия 2 (5/10л)
INSERT INTO equipment_link (organization_id, from_equipment_id, to_equipment_id, is_direct) VALUES
    (v_org_id, v_reactor3, v_line2, TRUE);

-- Реактор 4 -> Линия 3 (ручной слив)
INSERT INTO equipment_link (organization_id, from_equipment_id, to_equipment_id, is_direct) VALUES
    (v_org_id, v_reactor4, v_line3, TRUE);

-- Накопительная емкость -> Линия 1
INSERT INTO equipment_link (organization_id, from_equipment_id, to_equipment_id, is_direct) VALUES
    (v_org_id, v_tank1, v_line1, TRUE);

-- ==========================================
-- 9. МАТРИЦА СОВМЕСТИМОСТИ (какой ПФ в каком реакторе)
-- ==========================================
-- Реактор 1: только Крем-мыло (70% загрузка)
INSERT INTO equipment_capability (organization_id, equipment_id, product_id, max_fill_percent) VALUES
    (v_org_id, v_reactor1, v_pf_cream, 0.70);

-- Реактор 2: Крем-мыло и Средство для мытья посуды (70% загрузка)
INSERT INTO equipment_capability (organization_id, equipment_id, product_id, max_fill_percent) VALUES
    (v_org_id, v_reactor2, v_pf_cream, 0.70),
    (v_org_id, v_reactor2, v_pf_dish, 0.70);

-- Реактор 3: Средство для мытья посуды и Антисептик (70% загрузка)
INSERT INTO equipment_capability (organization_id, equipment_id, product_id, max_fill_percent) VALUES
    (v_org_id, v_reactor3, v_pf_dish, 0.70),
    (v_org_id, v_reactor3, v_pf_antiseptic, 0.70);

-- Реактор 4: только Антисептик (70% загрузка)
INSERT INTO equipment_capability (organization_id, equipment_id, product_id, max_fill_percent) VALUES
    (v_org_id, v_reactor4, v_pf_antiseptic, 0.70);

-- Линии розлива: совместимость с ГП
INSERT INTO equipment_capability (organization_id, equipment_id, product_id, max_fill_percent) VALUES
    (v_org_id, v_line1, v_gp_cream_1, 1.0),
    (v_org_id, v_line1, v_gp_dish_1, 1.0),
    (v_org_id, v_line2, v_gp_cream_5, 1.0),
    (v_org_id, v_line2, v_gp_antiseptic_10, 1.0),
    (v_org_id, v_line3, v_gp_antiseptic_10, 1.0);

-- ==========================================
-- 10. РЕСУРСНЫЕ ПУЛЫ
-- ==========================================
v_res_operators := gen_random_uuid();
v_res_cooling := gen_random_uuid();
v_res_boiler := gen_random_uuid();

INSERT INTO resource_pool (id, organization_id, name, type, capacity) VALUES
    (v_res_operators, v_org_id, 'Аппаратчики реакторов', 'OPERATOR', 3),
    (v_res_cooling, v_org_id, 'Зона охлаждения', 'COOLING_ZONE', 2),
    (v_res_boiler, v_org_id, 'Бойлер', 'BOILER', 1)
ON CONFLICT DO NOTHING;

-- ==========================================
-- 11. РЕЦЕПТУРЫ ПФ
-- ==========================================

-- Крем-мыло (базовый объем 100 кг)
v_recipe_cream := gen_random_uuid();
INSERT INTO recipe (id, organization_id, product_id, base_volume_kg) VALUES
    (v_recipe_cream, v_org_id, v_pf_cream, 100);

INSERT INTO recipe_item (recipe_id, material_id, qty_per_base) VALUES
    (v_recipe_cream, v_mat_water, 85),
    (v_recipe_cream, v_mat_salt, 5),
    (v_recipe_cream, v_mat_fragrance, 2),
    (v_recipe_cream, v_mat_glycerin, 8);

-- Средство для мытья посуды (базовый объем 100 кг)
v_recipe_dish := gen_random_uuid();
INSERT INTO recipe (id, organization_id, product_id, base_volume_kg) VALUES
    (v_recipe_dish, v_org_id, v_pf_dish, 100);

INSERT INTO recipe_item (recipe_id, material_id, qty_per_base) VALUES
    (v_recipe_dish, v_mat_water, 70),
    (v_recipe_dish, v_mat_salt, 15),
    (v_recipe_dish, v_mat_fragrance, 5),
    (v_recipe_dish, v_mat_betaine, 6),
    (v_recipe_dish, v_mat_alcohol, 4);

-- Антисептик (базовый объем 100 кг)
v_recipe_antiseptic := gen_random_uuid();
INSERT INTO recipe (id, organization_id, product_id, base_volume_kg) VALUES
    (v_recipe_antiseptic, v_org_id, v_pf_antiseptic, 100);

INSERT INTO recipe_item (recipe_id, material_id, qty_per_base) VALUES
    (v_recipe_antiseptic, v_mat_water, 60),
    (v_recipe_antiseptic, v_mat_alcohol, 35),
    (v_recipe_antiseptic, v_mat_chloride, 5);

-- ==========================================
-- 12. ТЕХНОЛОГИЧЕСКИЕ КАРТЫ
-- ==========================================

-- КРЕМ-МЫЛО (11 этапов)
INSERT INTO operation_template (organization_id, product_id, stage_order, name, base_duration_mins, 
    needs_boiler, needs_cooling_zone, needs_operator, needs_lab, duration_formula, parallel_group_id) VALUES
    (v_org_id, v_pf_cream, 1, 'Загрузка сырья (вода)', 60, FALSE, FALSE, TRUE, FALSE, 'water_loading', NULL),
    (v_org_id, v_pf_cream, 2, 'Нагрев воды', 120, TRUE, FALSE, FALSE, FALSE, 'heating', NULL),
    (v_org_id, v_pf_cream, 3, 'Перемешивание', 90, FALSE, FALSE, TRUE, FALSE, 'mixing', 'GROUP1'),
    (v_org_id, v_pf_cream, 4, 'Охлаждение 80→60°C', 120, FALSE, TRUE, FALSE, FALSE, 'cooling', 'GROUP1'),
    (v_org_id, v_pf_cream, 5, 'Лабораторный анализ', 30, FALSE, FALSE, FALSE, TRUE, NULL, NULL),
    (v_org_id, v_pf_cream, 6, 'Загрузка доп. сырья', 30, FALSE, FALSE, TRUE, FALSE, 'water_loading', NULL),
    (v_org_id, v_pf_cream, 7, 'Перемешивание (2 этап)', 60, FALSE, FALSE, TRUE, FALSE, 'mixing', 'GROUP2'),
    (v_org_id, v_pf_cream, 8, 'Охлаждение 60→40°C', 120, FALSE, TRUE, FALSE, FALSE, 'cooling', 'GROUP2'),
    (v_org_id, v_pf_cream, 9, 'Лабораторный анализ (финал)', 30, FALSE, FALSE, FALSE, TRUE, NULL, NULL),
    (v_org_id, v_pf_cream, 10, 'Перекачка в накопительную емкость', 60, FALSE, FALSE, TRUE, FALSE, 'pumping', NULL),
    (v_org_id, v_pf_cream, 11, 'Промывка реактора', 90, FALSE, FALSE, TRUE, FALSE, 'washing', NULL);

-- СРЕДСТВО ДЛЯ МЫТЬЯ ПОСУДЫ (8 этапов)
INSERT INTO operation_template (organization_id, product_id, stage_order, name, base_duration_mins, 
    needs_boiler, needs_cooling_zone, needs_operator, needs_lab, duration_formula, parallel_group_id) VALUES
    (v_org_id, v_pf_dish, 1, 'Загрузка сырья (вода)', 60, FALSE, FALSE, TRUE, FALSE, 'water_loading', NULL),
    (v_org_id, v_pf_dish, 2, 'Перемешивание', 120, FALSE, FALSE, TRUE, FALSE, 'mixing', 'GROUP1'),
    (v_org_id, v_pf_dish, 3, 'Охлаждение 90→50°C', 90, FALSE, TRUE, FALSE, FALSE, 'cooling', 'GROUP1'),
    (v_org_id, v_pf_dish, 4, 'Лабораторный анализ', 30, FALSE, FALSE, FALSE, TRUE, NULL, NULL),
    (v_org_id, v_pf_dish, 5, 'Перемешивание (2 этап)', 60, FALSE, FALSE, TRUE, FALSE, 'mixing', 'GROUP2'),
    (v_org_id, v_pf_dish, 6, 'Охлаждение 50→30°C', 90, FALSE, TRUE, FALSE, FALSE, 'cooling', 'GROUP2'),
    (v_org_id, v_pf_dish, 7, 'Лабораторный анализ (финал)', 30, FALSE, FALSE, FALSE, TRUE, NULL, NULL),
    (v_org_id, v_pf_dish, 8, 'Промывка реактора', 90, FALSE, FALSE, TRUE, FALSE, 'washing', NULL);

-- АНТИСЕПТИК (8 этапов)
INSERT INTO operation_template (organization_id, product_id, stage_order, name, base_duration_mins, 
    needs_boiler, needs_cooling_zone, needs_operator, needs_lab, duration_formula, parallel_group_id) VALUES
    (v_org_id, v_pf_antiseptic, 1, 'Загрузка сырья (вода)', 60, FALSE, FALSE, TRUE, FALSE, 'water_loading', NULL),
    (v_org_id, v_pf_antiseptic, 2, 'Перемешивание', 60, FALSE, FALSE, TRUE, FALSE, 'mixing', NULL),
    (v_org_id, v_pf_antiseptic, 3, 'Лабораторный анализ', 30, FALSE, FALSE, FALSE, TRUE, NULL, NULL),
    (v_org_id, v_pf_antiseptic, 4, 'Загрузка доп. сырья', 30, FALSE, FALSE, TRUE, FALSE, 'water_loading', NULL),
    (v_org_id, v_pf_antiseptic, 5, 'Перемешивание (2 этап)', 30, FALSE, FALSE, TRUE, FALSE, 'mixing', NULL),
    (v_org_id, v_pf_antiseptic, 6, 'Лабораторный анализ (финал)', 30, FALSE, FALSE, FALSE, TRUE, NULL, NULL),
    (v_org_id, v_pf_antiseptic, 7, 'Перекачка в накопительную емкость', 45, FALSE, FALSE, TRUE, FALSE, 'pumping', NULL),
    (v_org_id, v_pf_antiseptic, 8, 'Промывка реактора', 30, FALSE, FALSE, TRUE, FALSE, 'washing', NULL);

-- ==========================================
-- 13. МАТРИЦА ЗАМЫВКИ (время в минутах)
-- ==========================================
-- Тот же ПФ -> 30 мин, другой ПФ -> 90 мин (1.5 часа)
INSERT INTO setup_matrix (organization_id, from_product_id, to_product_id, setup_mins) VALUES
    (v_org_id, v_pf_cream, v_pf_cream, 30),
    (v_org_id, v_pf_cream, v_pf_dish, 90),
    (v_org_id, v_pf_cream, v_pf_antiseptic, 90),
    (v_org_id, v_pf_dish, v_pf_dish, 30),
    (v_org_id, v_pf_dish, v_pf_cream, 90),
    (v_org_id, v_pf_dish, v_pf_antiseptic, 90),
    (v_org_id, v_pf_antiseptic, v_pf_antiseptic, 30),
    (v_org_id, v_pf_antiseptic, v_pf_cream, 90),
    (v_org_id, v_pf_antiseptic, v_pf_dish, 90);

-- ==========================================
-- 14. КАЛЕНДАРЬ ПРОСТОЕВ (сентябрь 2026)
-- ==========================================

-- Выходные дни (суббота-воскресенье)
INSERT INTO calendar_event (organization_id, event_type, starts_at, ends_at, comment) VALUES
    (v_org_id, 'WEEKEND', '2026-09-05 00:00:00+03', '2026-09-07 00:00:00+03', 'Выходные'),
    (v_org_id, 'WEEKEND', '2026-09-12 00:00:00+03', '2026-09-14 00:00:00+03', 'Выходные'),
    (v_org_id, 'WEEKEND', '2026-09-19 00:00:00+03', '2026-09-21 00:00:00+03', 'Выходные'),
    (v_org_id, 'WEEKEND', '2026-09-26 00:00:00+03', '2026-09-28 00:00:00+03', 'Выходные');

-- Плановый ремонт Реактора 3 (10-20 сентября)
INSERT INTO calendar_event (organization_id, equipment_id, event_type, starts_at, ends_at, comment) VALUES
    (v_org_id, v_reactor3, 'REPAIR', '2026-09-10 00:00:00+03', '2026-09-21 00:00:00+03', 'Плановый ремонт Реактора 3');

-- Аварийная остановка Реактора 4 (25-28 сентября) - добавляется после планирования
-- INSERT INTO calendar_event (organization_id, equipment_id, event_type, starts_at, ends_at, comment) VALUES
--     (v_org_id, v_reactor4, 'BREAKDOWN', '2026-09-25 00:00:00+03', '2026-09-29 00:00:00+03', 'Аварийная остановка Реактора 4');

-- ==========================================
-- 15. ПРОИЗВОДСТВЕННЫЕ ЗАКАЗЫ (план на месяц)
-- ==========================================
-- Крем-мыло 1л: 20 000 бутылок × 1 кг = 20 000 кг
-- Крем-мыло 5л: 5 000 бутылок × 5 кг = 25 000 кг
-- Средство для мытья посуды 1л: 15 000 бутылок × 1 кг = 15 000 кг
-- Антисептик 10л: 8 000 бутылок × 10 кг = 80 000 кг

INSERT INTO production_order (organization_id, product_id, target_qty, due_date, priority) VALUES
    (v_org_id, v_gp_cream_1, 20000, '2026-09-30 23:59:59+03', 5),
    (v_org_id, v_gp_cream_5, 5000, '2026-09-30 23:59:59+03', 5),
    (v_org_id, v_gp_dish_1, 15000, '2026-09-30 23:59:59+03', 5),
    (v_org_id, v_gp_antiseptic_10, 8000, '2026-09-30 23:59:59+03', 5);

-- ==========================================
-- 16. ПАРТИИ (разбивка по объему реакторов)
-- ==========================================

-- Заказы для получения ID
DECLARE
    v_order_cream_1 UUID;
    v_order_cream_5 UUID;
    v_order_dish_1 UUID;
    v_order_antiseptic_10 UUID;
BEGIN
    SELECT id INTO v_order_cream_1 FROM production_order WHERE product_id = v_gp_cream_1;
    SELECT id INTO v_order_cream_5 FROM production_order WHERE product_id = v_gp_cream_5;
    SELECT id INTO v_order_dish_1 FROM production_order WHERE product_id = v_gp_dish_1;
    SELECT id INTO v_order_antiseptic_10 FROM production_order WHERE product_id = v_gp_antiseptic_10;

    -- Крем-мыло (ПФ) для ГП 1л: 20 000 кг
    -- Р1 (5000 кг × 70% = 3500 кг): 6 партий
    INSERT INTO batch (organization_id, order_id, product_id, volume_kg, assigned_equipment_id) VALUES
        (v_org_id, v_order_cream_1, v_pf_cream, 3500, v_reactor1),
        (v_org_id, v_order_cream_1, v_pf_cream, 3500, v_reactor1),
        (v_org_id, v_order_cream_1, v_pf_cream, 3500, v_reactor1),
        (v_org_id, v_order_cream_1, v_pf_cream, 3500, v_reactor1),
        (v_org_id, v_order_cream_1, v_pf_cream, 3500, v_reactor1),
        (v_org_id, v_order_cream_1, v_pf_cream, 2500, v_reactor1);

    -- Крем-мыло (ПФ) для ГП 5л: 25 000 кг
    -- Р2 (10000 кг × 70% = 7000 кг): 4 партии
    INSERT INTO batch (organization_id, order_id, product_id, volume_kg, assigned_equipment_id) VALUES
        (v_org_id, v_order_cream_5, v_pf_cream, 7000, v_reactor2),
        (v_org_id, v_order_cream_5, v_pf_cream, 7000, v_reactor2),
        (v_org_id, v_order_cream_5, v_pf_cream, 7000, v_reactor2),
        (v_org_id, v_order_cream_5, v_pf_cream, 4000, v_reactor2);

    -- Средство для мытья посуды: 15 000 кг
    -- Р2 (7000 кг): 2 партии + Р3 (8000 кг × 70% = 5600 кг): 2 партии
    INSERT INTO batch (organization_id, order_id, product_id, volume_kg, assigned_equipment_id) VALUES
        (v_org_id, v_order_dish_1, v_pf_dish, 7000, v_reactor2),
        (v_org_id, v_order_dish_1, v_pf_dish, 7000, v_reactor2),
        (v_org_id, v_order_dish_1, v_pf_dish, 1000, v_reactor3);

    -- Антисептик: 80 000 кг
    -- Р3 (5600 кг): 10 партий + Р4 (3500 кг): 7 партий
    INSERT INTO batch (organization_id, order_id, product_id, volume_kg, assigned_equipment_id) VALUES
        (v_org_id, v_order_antiseptic_10, v_pf_antiseptic, 5600, v_reactor3),
        (v_org_id, v_order_antiseptic_10, v_pf_antiseptic, 5600, v_reactor3),
        (v_org_id, v_order_antiseptic_10, v_pf_antiseptic, 5600, v_reactor3),
        (v_org_id, v_order_antiseptic_10, v_pf_antiseptic, 5600, v_reactor3),
        (v_org_id, v_order_antiseptic_10, v_pf_antiseptic, 5600, v_reactor3),
        (v_org_id, v_order_antiseptic_10, v_pf_antiseptic, 5600, v_reactor3),
        (v_org_id, v_order_antiseptic_10, v_pf_antiseptic, 5600, v_reactor3),
        (v_org_id, v_order_antiseptic_10, v_pf_antiseptic, 5600, v_reactor3),
        (v_org_id, v_order_antiseptic_10, v_pf_antiseptic, 5600, v_reactor3),
        (v_org_id, v_order_antiseptic_10, v_pf_antiseptic, 5600, v_reactor3),
        (v_org_id, v_order_antiseptic_10, v_pf_antiseptic, 3500, v_reactor4),
        (v_org_id, v_order_antiseptic_10, v_pf_antiseptic, 3500, v_reactor4),
        (v_org_id, v_order_antiseptic_10, v_pf_antiseptic, 3500, v_reactor4),
        (v_org_id, v_order_antiseptic_10, v_pf_antiseptic, 3500, v_reactor4),
        (v_org_id, v_order_antiseptic_10, v_pf_antiseptic, 3500, v_reactor4),
        (v_org_id, v_order_antiseptic_10, v_pf_antiseptic, 3500, v_reactor4),
        (v_org_id, v_order_antiseptic_10, v_pf_antiseptic, 2000, v_reactor4);
END;

END $$;

-- ==========================================
-- ГОТОВО! Демо-данные загружены.
-- ==========================================