-- ==========================================
-- APS СИСТЕМА: ПОЛНАЯ СХЕМА БД
-- PostgreSQL 16+
-- Для производства бытовой химии
-- Версия: 1.3.0 (после Итераций 0-2)
-- ==========================================
-- Включает:
--   - Мульти-тенантность и авторизацию
--   - Оборудование с code (для стабильной идентификации)
--   - Продукцию (ПФ/ГП) с route_type (DIRECT / VIA_TANK)
--   - Рецептуры и материалы
--   - Технологические карты с operator_pool
--   - Цепочки рабочих центров (linked_equipment_id, task_role)
--   - Версионирование планов через snapshots
--   - Feature-флаги для поэтапного внедрения
-- ==========================================

-- ⚠️ ВАЖНО: Этот файл — АКТУАЛЬНАЯ СХЕМА на текущую версию (v1.3.0).
-- Применяется ТОЛЬКО на пустую БД.
-- Для апгрейда существующих БД см. цепочку migrations/add_*.sql
-- НЕ ПРИМЕНЯТЬ повторно на существующую БД — упадёт с "relation already exists".

-- ==========================================
-- 1. МУЛЬТИ-ТЕНАНТНОСТЬ И АВТОРИЗАЦИЯ
-- ==========================================
CREATE TABLE organization (
                              id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                              name VARCHAR(200) NOT NULL,
                              slug VARCHAR(50) UNIQUE NOT NULL,
                              settings JSONB DEFAULT '{}',
                              is_active BOOLEAN DEFAULT TRUE,
                              created_at TIMESTAMPTZ DEFAULT NOW(),
                              comment TEXT
);
COMMENT ON TABLE organization IS 'Организации (тенанты). Все бизнес-данные привязаны к организации.';

CREATE TABLE app_user (
                          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                          organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
                          email VARCHAR(200) NOT NULL,
                          full_name VARCHAR(200),
                          role VARCHAR(30) NOT NULL, -- ADMIN, PLANNER, MASTER, LAB, VIEWER
                          password_hash VARCHAR(255),
                          last_login_at TIMESTAMPTZ,
                          is_active BOOLEAN DEFAULT TRUE,
                          UNIQUE (organization_id, email)
);
COMMENT ON TABLE app_user IS 'Пользователи системы с привязкой к организации и ролью.';
COMMENT ON COLUMN app_user.password_hash IS 'Хешированный пароль пользователя (bcrypt)';
COMMENT ON COLUMN app_user.last_login_at IS 'Дата и время последнего входа в систему';

CREATE TABLE organization_settings (
                                       id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                                       organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
                                       setting_key VARCHAR(100) NOT NULL,
                                       setting_value JSONB NOT NULL,
                                       description TEXT,
                                       updated_at TIMESTAMPTZ DEFAULT NOW(),
                                       UNIQUE (organization_id, setting_key)
);
COMMENT ON TABLE organization_settings IS 'Настройки организации. Бизнес-параметры и feature-флаги.';
CREATE INDEX idx_org_settings_org_id ON organization_settings(organization_id);

-- ==========================================
-- 2. СПРАВОЧНИКИ ОБОРУДОВАНИЯ И РЕСУРСОВ
-- ==========================================
CREATE TABLE equipment (
                           id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                           organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
                           code VARCHAR(50),                    -- REACTOR_1, TANK_1, LINE_1, BOILER (с add_04)
                           name VARCHAR(100) NOT NULL,
                           type VARCHAR(30) NOT NULL,           -- REACTOR, TANK, FILLING_LINE, BOILER, MANUAL_STATION
                           volume_kg NUMERIC(10,2),
                           speed_coeff NUMERIC(6,3) DEFAULT 1.0,
                           mixer_type VARCHAR(50),              -- standard, high_speed, low_speed
                           pump_power_kw NUMERIC(6,2),
                           is_active BOOLEAN DEFAULT TRUE,
                           metadata JSONB DEFAULT '{}',
                           comment TEXT,
                           CONSTRAINT equipment_org_code_unique UNIQUE (organization_id, code)
);
COMMENT ON TABLE equipment IS 'Оборудование производственной линии.';
COMMENT ON COLUMN equipment.code IS 'Уникальный код оборудования внутри организации (REACTOR_1, TANK_1, LINE_1, BOILER)';
COMMENT ON COLUMN equipment.type IS 'REACTOR | TANK | FILLING_LINE | BOILER | MANUAL_STATION';

CREATE INDEX idx_equipment_org ON equipment(organization_id);
CREATE INDEX idx_equipment_code ON equipment(organization_id, code) WHERE code IS NOT NULL;

CREATE TABLE equipment_link (
                                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                                organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
                                from_equipment_id UUID NOT NULL REFERENCES equipment(id) ON DELETE CASCADE,
                                to_equipment_id UUID NOT NULL REFERENCES equipment(id) ON DELETE CASCADE,
                                is_direct BOOLEAN DEFAULT TRUE,
                                UNIQUE (from_equipment_id, to_equipment_id)
);
COMMENT ON TABLE equipment_link IS 'Физические связи между оборудованием (реактор → танк, реактор → линия, танк → линия).';

CREATE TABLE resource_pool (
                               id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                               organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
                               name VARCHAR(100) NOT NULL,
                               type VARCHAR(50) NOT NULL,           -- OPERATOR, COOLING_ZONE, BOILER, LAB
                               capacity INT NOT NULL,
                               comment TEXT
);
COMMENT ON TABLE resource_pool IS 'Переиспользуемые ресурсы с ограничением параллельности.';

-- ==========================================
-- 3. МАТЕРИАЛЫ И ОСТАТКИ
-- ==========================================
CREATE TABLE material (
                          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                          organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
                          code VARCHAR(50) NOT NULL,
                          name VARCHAR(200) NOT NULL,
                          unit VARCHAR(20) NOT NULL DEFAULT 'kg',
                          category VARCHAR(30) NOT NULL,       -- RAW, PACKAGING, LABEL
                          comment TEXT,
                          UNIQUE (organization_id, code)
);
COMMENT ON TABLE material IS 'Справочник материалов: сырье, упаковка, этикетки.';

CREATE TABLE material_stock (
                                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                                organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
                                material_id UUID NOT NULL REFERENCES material(id) ON DELETE CASCADE,
                                qty NUMERIC(12,3) NOT NULL DEFAULT 0,
                                reserved_qty NUMERIC(12,3) DEFAULT 0,
                                updated_at TIMESTAMPTZ DEFAULT NOW()
);
COMMENT ON TABLE material_stock IS 'Текущие остатки материалов на складе.';

CREATE TABLE material_supply (
                                 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                                 organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
                                 material_id UUID NOT NULL REFERENCES material(id) ON DELETE CASCADE,
                                 expected_at TIMESTAMPTZ NOT NULL,
                                 qty NUMERIC(12,3) NOT NULL,
                                 status VARCHAR(20) DEFAULT 'PLANNED'
);
COMMENT ON TABLE material_supply IS 'График поставок сырья от поставщиков.';

-- ==========================================
-- 4. ПРОДУКЦИЯ (ПФ и ГП) И РЕЦЕПТУРЫ
-- ==========================================
CREATE TABLE product (
                         id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                         organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
                         code VARCHAR(50) NOT NULL,
                         name VARCHAR(200) NOT NULL,
                         type VARCHAR(10) NOT NULL,           -- PF, GP
                         viscosity_coeff NUMERIC(5,2) DEFAULT 1.0,
                         requires_heating BOOLEAN DEFAULT FALSE,
                         bottle_volume_l NUMERIC(5,2),
                         fill_speed_per_min NUMERIC(8,2),
                         parent_pf_id UUID REFERENCES product(id),
                         route_type VARCHAR(20) DEFAULT 'DIRECT',  -- DIRECT | VIA_TANK (с add_03)
                         comment TEXT,
                         UNIQUE (organization_id, code)
);
COMMENT ON TABLE product IS 'Продукция: полуфабрикаты (ПФ) и готовая продукция (ГП).';
COMMENT ON COLUMN product.route_type IS 'Способ слива ПФ: DIRECT (напрямую на линию) или VIA_TANK (через накопительную емкость)';

CREATE INDEX idx_product_org ON product(organization_id);

CREATE TABLE recipe (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
                        product_id UUID NOT NULL REFERENCES product(id) ON DELETE CASCADE,
                        base_volume_kg NUMERIC(10,2) NOT NULL,
                        comment TEXT
);
COMMENT ON TABLE recipe IS 'Рецептура полуфабриката. Пропорции компонентов на базовый объем.';

CREATE TABLE recipe_item (
                             id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                             recipe_id UUID NOT NULL REFERENCES recipe(id) ON DELETE CASCADE,
                             material_id UUID NOT NULL REFERENCES material(id),
                             qty_per_base NUMERIC(10,3) NOT NULL
);
COMMENT ON TABLE recipe_item IS 'Компоненты рецептуры.';

CREATE TABLE equipment_capability (
                                      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                                      organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
                                      equipment_id UUID NOT NULL REFERENCES equipment(id) ON DELETE CASCADE,
                                      product_id UUID NOT NULL REFERENCES product(id) ON DELETE CASCADE,
                                      max_fill_percent NUMERIC(3,2) DEFAULT 0.80,
                                      UNIQUE (organization_id, equipment_id, product_id)
);
COMMENT ON TABLE equipment_capability IS 'Матрица совместимости оборудования и продукции.';

-- ==========================================
-- 5. ТЕХНОЛОГИЧЕСКИЕ КАРТЫ
-- ==========================================
CREATE TABLE operation_template (
                                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                                    organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
                                    product_id UUID NOT NULL REFERENCES product(id) ON DELETE CASCADE,
                                    stage_order INT NOT NULL,
                                    name VARCHAR(100) NOT NULL,
                                    base_duration_mins INT NOT NULL,
                                    is_setup BOOLEAN DEFAULT FALSE,
                                    is_parallel_group BOOLEAN DEFAULT FALSE,
                                    parallel_group_id VARCHAR(50),
                                    needs_boiler BOOLEAN DEFAULT FALSE,
                                    needs_cooling_zone BOOLEAN DEFAULT FALSE,
                                    needs_operator BOOLEAN DEFAULT FALSE,
                                    needs_lab BOOLEAN DEFAULT FALSE,
                                    duration_formula VARCHAR(200),       -- water_loading, heating, mixing, cooling, pumping, washing
                                    operator_pool VARCHAR(50),           -- REACTOR_OPERATOR | LINE_OPERATOR (с add_03)
                                    comment TEXT
);
COMMENT ON TABLE operation_template IS 'Технологическая карта: этапы производства полуфабриката.';
COMMENT ON COLUMN operation_template.operator_pool IS 'Пул операторов: REACTOR_OPERATOR (аппаратчики) или LINE_OPERATOR (операторы линий)';

CREATE TABLE setup_matrix (
                              id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                              organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
                              from_product_id UUID NOT NULL REFERENCES product(id),
                              to_product_id UUID NOT NULL REFERENCES product(id),
                              setup_mins INT NOT NULL,
                              UNIQUE (organization_id, from_product_id, to_product_id)
);
COMMENT ON TABLE setup_matrix IS 'Матрица времени переналадки (замывки) при переходе между полуфабрикатами.';

-- ==========================================
-- 6. КАЛЕНДАРЬ (выходные, ремонты, аварии)
-- ==========================================
CREATE TABLE calendar_event (
                                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                                organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
                                equipment_id UUID REFERENCES equipment(id) ON DELETE CASCADE,
                                event_type VARCHAR(30) NOT NULL,     -- WEEKEND, REPAIR, BREAKDOWN, SHIFT_END, LUNCH
                                starts_at TIMESTAMPTZ NOT NULL,
                                ends_at TIMESTAMPTZ NOT NULL,
                                comment TEXT,
                                CONSTRAINT chk_dates CHECK (ends_at > starts_at)
);
COMMENT ON TABLE calendar_event IS 'Календарь простоев оборудования.';

-- ==========================================
-- 7. ПЛАНИРОВАНИЕ: ЗАКАЗЫ, ПАРТИИ, ГАНТ
-- ==========================================
CREATE TABLE production_order (
                                  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                                  organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
                                  product_id UUID NOT NULL REFERENCES product(id),
                                  target_qty NUMERIC(10,2) NOT NULL,
                                  due_date TIMESTAMPTZ NOT NULL,
                                  priority INT DEFAULT 5,
                                  status VARCHAR(20) DEFAULT 'PLANNED',
                                  created_at TIMESTAMPTZ DEFAULT NOW(),
                                  comment TEXT
);
COMMENT ON TABLE production_order IS 'Заказ на производство готовой продукции.';

CREATE INDEX idx_production_order_org ON production_order(organization_id);

CREATE TABLE batch (
                       id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                       organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
                       order_id UUID NOT NULL REFERENCES production_order(id) ON DELETE CASCADE,
                       product_id UUID NOT NULL REFERENCES product(id),
                       volume_kg NUMERIC(10,2) NOT NULL,
                       assigned_equipment_id UUID REFERENCES equipment(id),
                       planned_start TIMESTAMPTZ,
                       planned_end TIMESTAMPTZ,
                       status VARCHAR(20) DEFAULT 'NOT_STARTED',
                       comment TEXT
);
COMMENT ON TABLE batch IS 'Производственная партия полуфабриката.';

CREATE INDEX idx_batch_org ON batch(organization_id);

CREATE TABLE schedule_version (
                                  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                                  organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
                                  name VARCHAR(100) NOT NULL,
                                  version_type VARCHAR(20) NOT NULL,   -- MONTHLY, SHIFT, WHAT_IF
                                  is_active BOOLEAN DEFAULT FALSE,
                                  created_at TIMESTAMPTZ DEFAULT NOW(),
                                  created_by UUID REFERENCES app_user(id),
                                  comment TEXT
);
COMMENT ON TABLE schedule_version IS 'Версии производственного плана.';

CREATE TABLE scheduled_task (
                                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                                organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
                                schedule_version_id UUID NOT NULL REFERENCES schedule_version(id) ON DELETE CASCADE,
                                batch_id UUID REFERENCES batch(id) ON DELETE CASCADE,
                                operation_template_id UUID NOT NULL REFERENCES operation_template(id),
                                equipment_id UUID NOT NULL REFERENCES equipment(id),
                                linked_equipment_id UUID REFERENCES equipment(id),   -- второй ресурс (с add_03)
                                resource_pool_id UUID REFERENCES resource_pool(id),
                                task_role VARCHAR(30),               -- REACTOR_OP | TANK_TRANSFER | LINE_FILL | WASH | SETUP (с add_03)
                                planned_start TIMESTAMPTZ NOT NULL,
                                planned_end TIMESTAMPTZ NOT NULL,
                                actual_start TIMESTAMPTZ,
                                actual_end TIMESTAMPTZ,
                                is_pinned BOOLEAN DEFAULT FALSE,
                                comment TEXT
);
COMMENT ON TABLE scheduled_task IS 'Задача на диаграмме Ганта.';
COMMENT ON COLUMN scheduled_task.linked_equipment_id IS 'Второй ресурс задачи (слив занимает реактор+линию, перекачка — реактор+танк)';
COMMENT ON COLUMN scheduled_task.task_role IS 'Роль задачи в цепочке: REACTOR_OP, TANK_TRANSFER, LINE_FILL, WASH, SETUP';

CREATE INDEX idx_scheduled_task_org ON scheduled_task(organization_id);
CREATE INDEX idx_scheduled_task_linked_eq ON scheduled_task(linked_equipment_id) WHERE linked_equipment_id IS NOT NULL;
CREATE INDEX idx_task_equipment_time ON scheduled_task USING GIST (
    organization_id,
    equipment_id,
    tstzrange(planned_start, planned_end)
    );

-- ==========================================
-- 8. SNAPSHOT-ТАБЛИЦЫ ДЛЯ ВЕРСИОНИРОВАНИЯ
-- ==========================================
CREATE TABLE equipment_snapshot (
                                    id UUID NOT NULL,
                                    organization_id UUID NOT NULL,
                                    code VARCHAR(50),
                                    name VARCHAR(100) NOT NULL,
                                    type VARCHAR(30) NOT NULL,
                                    volume_kg NUMERIC(10,2),
                                    speed_coeff NUMERIC(6,3),
                                    mixer_type VARCHAR(50),
                                    is_active BOOLEAN,
                                    version_id UUID NOT NULL REFERENCES schedule_version(id) ON DELETE CASCADE,
                                    PRIMARY KEY (id, version_id)
);

CREATE TABLE product_snapshot (
                                  id UUID NOT NULL,
                                  organization_id UUID NOT NULL,
                                  code VARCHAR(50) NOT NULL,
                                  name VARCHAR(200) NOT NULL,
                                  type VARCHAR(10) NOT NULL,
                                  viscosity_coeff NUMERIC(5,2),
                                  requires_heating BOOLEAN,
                                  bottle_volume_l NUMERIC(5,2),
                                  fill_speed_per_min NUMERIC(8,2),
                                  parent_pf_id UUID,
                                  route_type VARCHAR(20),
                                  version_id UUID NOT NULL REFERENCES schedule_version(id) ON DELETE CASCADE,
                                  PRIMARY KEY (id, version_id)
);

CREATE TABLE operation_snapshot (
                                    id UUID NOT NULL,
                                    organization_id UUID NOT NULL,
                                    product_id UUID NOT NULL,
                                    stage_order INT NOT NULL,
                                    name VARCHAR(100) NOT NULL,
                                    base_duration_mins INT NOT NULL,
                                    is_setup BOOLEAN,
                                    is_parallel_group BOOLEAN,
                                    parallel_group_id VARCHAR(50),
                                    needs_boiler BOOLEAN,
                                    needs_cooling_zone BOOLEAN,
                                    needs_operator BOOLEAN,
                                    needs_lab BOOLEAN,
                                    duration_formula VARCHAR(200),
                                    operator_pool VARCHAR(50),
                                    comment TEXT,
                                    version_id UUID NOT NULL REFERENCES schedule_version(id) ON DELETE CASCADE,
                                    PRIMARY KEY (id, version_id)
);

CREATE TABLE calendar_snapshot (
                                   id UUID NOT NULL,
                                   organization_id UUID NOT NULL,
                                   equipment_id UUID,
                                   event_type VARCHAR(30) NOT NULL,
                                   starts_at TIMESTAMPTZ NOT NULL,
                                   ends_at TIMESTAMPTZ NOT NULL,
                                   comment TEXT,
                                   version_id UUID NOT NULL REFERENCES schedule_version(id) ON DELETE CASCADE,
                                   PRIMARY KEY (id, version_id)
);

CREATE INDEX idx_equip_snap_ver ON equipment_snapshot(version_id);
CREATE INDEX idx_prod_snap_ver ON product_snapshot(version_id);
CREATE INDEX idx_oper_snap_ver ON operation_snapshot(version_id);
CREATE INDEX idx_cal_snap_ver ON calendar_snapshot(version_id);

-- ==========================================
-- 9. ДЕМО-НАСТРОЙКИ ОРГАНИЗАЦИИ
-- ==========================================
-- Базовые параметры (добавлены в add_01.sql)
-- Feature-флаги (добавлены в add_02.sql, активированы в add_03/add_05)
-- ==========================================

INSERT INTO organization_settings (organization_id, setting_key, setting_value, description) VALUES
                                                                                                 -- Базовые параметры
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'max_operators',              '3',                        'Максимальное количество операторов'),
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'cooling_zone_capacity',      '2',                        'Максимум реакторов в зоне охлаждения'),
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'default_horizon_hours',      '2160',                     'Горизонт планирования по умолчанию (часы)'),
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'max_fill_percent',           '0.70',                     'Максимальная загрузка реактора'),
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'planning_start_date',        '"2026-09-01T08:00:00"',    'Дата начала планирования'),
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'work_start_time',            '"08:00"',                  'Начало рабочего дня'),
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'work_end_time',              '"20:00"',                  'Конец рабочего дня'),

                                                                                                 -- Feature-флаги Итерации 1 (ВКЛЮЧЕНО)
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'enable_tank_routing',        'true',                     'Цепочки реактор→танк→линия (Итерация 1)'),

                                                                                                 -- Feature-флаги Итерации 2 (ВКЛЮЧЕНО)
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'enable_advisor',             'true',                     'Подсказки планировщика (Итерация 2)'),
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'enable_material_constraints','true',                     'Учёт остатков сырья (Итерация 2)'),

                                                                                                 -- Feature-флаги будущих итераций (ВЫКЛЮЧЕНО)
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'enable_shift_planning',      'false',                    'Посменное планирование (Итерация 3)'),
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'enable_rescheduling',        'false',                    'Перепланирование (Итерация 4)'),
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'enable_lab_blocking',        'false',                    'Блокировка лабой (Итерация 5)'),
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'enable_operator_pools',      'false',                    'Пулы операторов (Итерация 6)'),
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'enable_manual_station',      'false',                    'Ручная станция (Итерация 6)'),
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'enable_cooling_degradation', 'false',                    'Деградация охлаждения (Итерация 7)'),
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'enable_cz_integration',      'false',                    'Интеграция с ЧЗ (Итерация 8)')
    ON CONFLICT (organization_id, setting_key) DO NOTHING;

-- ==========================================
-- ГОТОВО! Схема создана.
-- ==========================================