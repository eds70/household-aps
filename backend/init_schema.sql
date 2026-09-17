-- ==========================================
-- APS СИСТЕМА: ПОЛНАЯ СХЕМА БД
-- PostgreSQL 16+
-- Для производства бытовой химии
-- Версия: 1.6.1 (после Итераций 0-5 + hotfix)
-- ==========================================
-- Включает:
--   - Мульти-тенантность и авторизацию
--   - Оборудование с code (для стабильной идентификации)
--   - Продукцию (ПФ/ГП) с route_type (DIRECT / VIA_TANK)
--   - Рецептуры и материалы
--   - Технологические карты с operator_pool
--   - Цепочки рабочих центров (linked_equipment_id, task_role)
--   - Сменное планирование (shift, shift_id, actual_*, status)
--   - Версионирование планов через snapshots
--   - Feature-флаги для поэтапного внедрения
--   - Перепланирование (reschedule_log, frozen_before, is_pinned)
--   - Лабораторные блокировки (is_lab_blocked, lab_status, lab_analysis_log)
-- ==========================================

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
                           code VARCHAR(50),                    -- REACTOR_1, TANK_1, LINE_1, BOILER
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
COMMENT ON COLUMN equipment.code IS 'Уникальный код оборудования (REACTOR_1, TANK_1, LINE_1, BOILER)';
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
                         route_type VARCHAR(20) DEFAULT 'DIRECT',  -- DIRECT | VIA_TANK
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
                                    operator_pool VARCHAR(50),           -- REACTOR_OPERATOR | LINE_OPERATOR
                                    comment TEXT
);
COMMENT ON TABLE operation_template IS 'Технологическая карта: этапы производства полуфабриката.';
COMMENT ON COLUMN operation_template.operator_pool IS 'Пул операторов: REACTOR_OPERATOR или LINE_OPERATOR';

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
-- 7. СМЕНЫ (Итерация 3)
-- ==========================================
CREATE TABLE shift (
                       id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                       organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
                       name VARCHAR(50) NOT NULL,
                       starts_at TIMESTAMPTZ NOT NULL,
                       ends_at TIMESTAMPTZ NOT NULL,
                       is_working BOOLEAN DEFAULT TRUE,
                       comment TEXT,
                       CONSTRAINT chk_shift_dates CHECK (ends_at > starts_at)
);
COMMENT ON TABLE shift IS 'Производственные смены (одна в день, 08:00-20:00)';

CREATE INDEX idx_shift_org_start ON shift(organization_id, starts_at);
CREATE INDEX idx_shift_org_date ON shift(organization_id, starts_at, ends_at);

-- ==========================================
-- 8. ПЛАНИРОВАНИЕ: ЗАКАЗЫ, ПАРТИИ, ГАНТ
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
                       comment TEXT,
    -- Итерация 5: Лабораторные блокировки
                       is_lab_blocked BOOLEAN DEFAULT FALSE,
                       lab_status VARCHAR(30) DEFAULT 'NOT_REQUIRED',
                       lab_block_reason TEXT,
                       lab_blocked_at TIMESTAMPTZ,
                       lab_blocked_by UUID REFERENCES app_user(id) ON DELETE SET NULL
);
COMMENT ON TABLE batch IS 'Производственная партия полуфабриката.';
COMMENT ON COLUMN batch.is_lab_blocked IS 'Партия заблокирована лабораторией до одобрения';
COMMENT ON COLUMN batch.lab_status IS 'NOT_REQUIRED | PENDING_LAB | APPROVED | BLOCKED';
COMMENT ON COLUMN batch.lab_block_reason IS 'Причина блокировки партии лабораторией';
COMMENT ON COLUMN batch.lab_blocked_at IS 'Когда партия была заблокирована лабораторией';
COMMENT ON COLUMN batch.lab_blocked_by IS 'Кто заблокировал партию (лаборант)';

CREATE INDEX idx_batch_org ON batch(organization_id);
CREATE INDEX idx_batch_lab_blocked ON batch(organization_id, is_lab_blocked) WHERE is_lab_blocked = TRUE;
CREATE INDEX idx_batch_lab_status ON batch(organization_id, lab_status) WHERE lab_status IS NOT NULL AND lab_status != 'NOT_REQUIRED';

CREATE TABLE schedule_version (
                                  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                                  organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
                                  name VARCHAR(100) NOT NULL,
                                  version_type VARCHAR(20) NOT NULL,   -- MONTHLY, SHIFT, WHAT_IF
                                  is_active BOOLEAN DEFAULT FALSE,
                                  created_at TIMESTAMPTZ DEFAULT NOW(),
                                  created_by UUID REFERENCES app_user(id),
                                  frozen_before TIMESTAMPTZ,
                                  parent_version_id UUID REFERENCES schedule_version(id) ON DELETE SET NULL,
                                  comment TEXT
);
COMMENT ON TABLE schedule_version IS 'Версии производственного плана.';
COMMENT ON COLUMN schedule_version.frozen_before IS 'Задачи, начавшиеся до этого момента, заморожены — не двигаются при перепланировании';
COMMENT ON COLUMN schedule_version.parent_version_id IS 'Родительская версия — от какой версии плана перепланировали';

CREATE TABLE scheduled_task (
                                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                                organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
                                schedule_version_id UUID NOT NULL REFERENCES schedule_version(id) ON DELETE CASCADE,
                                batch_id UUID REFERENCES batch(id) ON DELETE CASCADE,
                                operation_template_id UUID NOT NULL REFERENCES operation_template(id),
                                equipment_id UUID NOT NULL REFERENCES equipment(id),
                                linked_equipment_id UUID REFERENCES equipment(id),   -- второй ресурс (Итерация 1)
                                resource_pool_id UUID REFERENCES resource_pool(id),
                                task_role VARCHAR(30),               -- REACTOR_OP | TANK_TRANSFER | LINE_FILL | WASH | SETUP
                                shift_id UUID REFERENCES shift(id) ON DELETE SET NULL,  -- смена (Итерация 3)
                                planned_start TIMESTAMPTZ NOT NULL,
                                planned_end TIMESTAMPTZ NOT NULL,
                                actual_start TIMESTAMPTZ,
                                actual_end TIMESTAMPTZ,
                                actual_qty NUMERIC(12,3),            -- факт. количество (Итерация 3)
                                material_load_at TIMESTAMPTZ,        -- загрузка сырья (Итерация 3)
                                status VARCHAR(20) DEFAULT 'PLANNED',-- PLANNED | IN_PROGRESS | DONE | CANCELLED
                                is_pinned BOOLEAN DEFAULT FALSE,
                                comment TEXT
);
COMMENT ON TABLE scheduled_task IS 'Задача на диаграмме Ганта.';
COMMENT ON COLUMN scheduled_task.linked_equipment_id IS 'Второй ресурс задачи (слив занимает реактор+линию, перекачка — реактор+танк)';
COMMENT ON COLUMN scheduled_task.task_role IS 'Роль задачи в цепочке: REACTOR_OP, TANK_TRANSFER, LINE_FILL, WASH, SETUP';
COMMENT ON COLUMN scheduled_task.shift_id IS 'Смена, к которой относится задача';
COMMENT ON COLUMN scheduled_task.actual_qty IS 'Фактическое количество (для слива — бутылок)';
COMMENT ON COLUMN scheduled_task.material_load_at IS 'Когда мастер отметил загрузку сырья в реактор';
COMMENT ON COLUMN scheduled_task.status IS 'PLANNED | IN_PROGRESS | DONE | CANCELLED';

CREATE INDEX idx_scheduled_task_org ON scheduled_task(organization_id);
CREATE INDEX idx_scheduled_task_linked_eq ON scheduled_task(linked_equipment_id) WHERE linked_equipment_id IS NOT NULL;
CREATE INDEX idx_scheduled_task_shift ON scheduled_task(shift_id) WHERE shift_id IS NOT NULL;
CREATE INDEX idx_task_equipment_time ON scheduled_task USING GIST (
    organization_id,
    equipment_id,
    tstzrange(planned_start, planned_end)
    );

-- ==========================================
-- 9. ЛАБОРАТОРИЯ (Итерация 5)
-- ==========================================
CREATE TABLE lab_analysis_log (
                                  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                                  organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
                                  batch_id UUID NOT NULL REFERENCES batch(id) ON DELETE CASCADE,
                                  scheduled_task_id UUID REFERENCES scheduled_task(id) ON DELETE SET NULL,
                                  action VARCHAR(30) NOT NULL,           -- REQUESTED | APPROVED | BLOCKED | UNBLOCKED | EXTENDED
                                  result VARCHAR(30),                    -- PASSED | FAILED | PENDING
                                  reason TEXT,
                                  performed_by UUID REFERENCES app_user(id) ON DELETE SET NULL,
                                  performed_at TIMESTAMPTZ DEFAULT NOW(),
                                  comment TEXT
);
COMMENT ON TABLE lab_analysis_log IS
    'Журнал лабораторных проверок: запросы, одобрения, блокировки, разблокировки.';
COMMENT ON COLUMN lab_analysis_log.action IS
    'REQUESTED — запрошен анализ, APPROVED — одобрено, BLOCKED — заблокировано, UNBLOCKED — разблокировано, EXTENDED — продлено';
COMMENT ON COLUMN lab_analysis_log.result IS 'PASSED | FAILED | PENDING';

CREATE INDEX idx_lab_log_org ON lab_analysis_log(organization_id);
CREATE INDEX idx_lab_log_batch ON lab_analysis_log(batch_id);
CREATE INDEX idx_lab_log_performed_at ON lab_analysis_log(performed_at DESC);

-- ==========================================
-- 10. ПЕРЕПЛАНИРОВАНИЕ (Итерация 4)
-- ==========================================
CREATE TABLE reschedule_log (
                                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                                organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
                                from_version_id UUID REFERENCES schedule_version(id) ON DELETE SET NULL,
                                to_version_id UUID REFERENCES schedule_version(id) ON DELETE SET NULL,
                                reason VARCHAR(30) NOT NULL,          -- DELAY | BREAKDOWN | QTY_CHANGE | MANUAL
                                changes JSONB NOT NULL DEFAULT '{}',
                                affected_task_count INT DEFAULT 0,
                                moved_task_count INT DEFAULT 0,
                                frozen_before TIMESTAMPTZ,
                                created_at TIMESTAMPTZ DEFAULT NOW(),
                                created_by UUID REFERENCES app_user(id),
                                comment TEXT
);
COMMENT ON TABLE reschedule_log IS 'Журнал перепланирований. Связывает старую и новую версии плана.';

CREATE INDEX idx_reschedule_log_org ON reschedule_log(organization_id);
CREATE INDEX idx_reschedule_log_from_version ON reschedule_log(from_version_id);
CREATE INDEX idx_reschedule_log_to_version ON reschedule_log(to_version_id);

-- ==========================================
-- 11. SNAPSHOT-ТАБЛИЦЫ ДЛЯ ВЕРСИОНИРОВАНИЯ
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
-- 12. НАСТРОЙКИ ОРГАНИЗАЦИИ И FEATURE-ФЛАГИ
-- ==========================================
-- Итерации 0-5 завершены. Активны:
--   enable_tank_routing, enable_advisor,
--   enable_material_constraints, enable_shift_planning,
--   enable_rescheduling, enable_lab_blocking.
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

                                                                                                 -- Feature-флаги Итерации 3 (ВКЛЮЧЕНО)
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'enable_shift_planning',      'true',                     'Посменное планирование и РМ мастера (Итерация 3)'),

                                                                                                 -- Feature-флаги Итерации 4 (ВКЛЮЧЕНО)
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'enable_rescheduling',        'true',                     'Перепланирование (Итерация 4)'),

                                                                                                 -- Feature-флаги Итерации 5 (ВКЛЮЧЕНО)
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'enable_lab_blocking',        'true',                     'Блокировка партии лабораторией (Итерация 5)'),

                                                                                                 -- Feature-флаги будущих итераций (ВЫКЛЮЧЕНО)
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'enable_cooling_degradation', 'false',                    'Деградация охлаждения (Итерация 7)'),
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'enable_operator_pools',      'false',                    'Пулы операторов (Итерация 6)'),
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'enable_manual_station',      'false',                    'Ручная станция (Итерация 6)'),
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'enable_cz_integration',      'false',                    'Интеграция с ЧЗ (Итерация 8)')
    ON CONFLICT (organization_id, setting_key) DO NOTHING;

-- ==========================================
-- ГОТОВО! Схема создана (v1.6.0).
-- ==========================================