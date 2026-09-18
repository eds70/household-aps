-- ==========================================
-- APS СИСТЕМА: ПОЛНАЯ СХЕМА БД
-- PostgreSQL 16+
-- Для производства бытовой химии
-- Версия: 1.9.0 (после Итераций 0-8)
-- ==========================================
-- Включает:
--   - Мульти-тенантность и авторизацию
--   - Оборудование с code
--   - Продукцию (ПФ/ГП) с route_type
--   - Рецептуры и материалы
--   - Технологические карты с operator_pool
--   - Цепочки рабочих центров
--   - Сменное планирование
--   - Версионирование планов через snapshots
--   - Feature-флаги
--   - Перепланирование
--   - Лабораторные блокировки
--   - Пулы операторов (люди как ресурс)
--   - Охлаждение с деградацией (cooling_mode: fast/slow)
--   - Честный Знак: маркировка ГП (Итерация 8)
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
                          role VARCHAR(30) NOT NULL,
                          password_hash VARCHAR(255),
                          last_login_at TIMESTAMPTZ,
                          is_active BOOLEAN DEFAULT TRUE,
                          UNIQUE (organization_id, email)
);
COMMENT ON TABLE app_user IS 'Пользователи системы с привязкой к организации и ролью.';

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
                           code VARCHAR(50),
                           name VARCHAR(100) NOT NULL,
                           type VARCHAR(30) NOT NULL,
                           volume_kg NUMERIC(10,2),
                           speed_coeff NUMERIC(6,3) DEFAULT 1.0,
                           mixer_type VARCHAR(50),
                           pump_power_kw NUMERIC(6,2),
                           is_active BOOLEAN DEFAULT TRUE,
                           metadata JSONB DEFAULT '{}',
                           comment TEXT,
                           CONSTRAINT equipment_org_code_unique UNIQUE (organization_id, code)
);
COMMENT ON TABLE equipment IS 'Оборудование производственной линии.';

CREATE TABLE equipment_link (
                                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                                organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
                                from_equipment_id UUID NOT NULL REFERENCES equipment(id) ON DELETE CASCADE,
                                to_equipment_id UUID NOT NULL REFERENCES equipment(id) ON DELETE CASCADE,
                                is_direct BOOLEAN DEFAULT TRUE,
                                UNIQUE (from_equipment_id, to_equipment_id)
);
COMMENT ON TABLE equipment_link IS 'Физические связи между оборудованием.';

CREATE TABLE resource_pool (
                               id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                               organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
                               name VARCHAR(100) NOT NULL,
                               type VARCHAR(50) NOT NULL,
                               capacity INT NOT NULL,
                               comment TEXT,
                               updated_at TIMESTAMPTZ DEFAULT NOW(),
                               CONSTRAINT resource_pool_org_type_unique UNIQUE (organization_id, type)
);
COMMENT ON TABLE resource_pool IS 'Переиспользуемые ресурсы с ограничением параллельности.';
COMMENT ON COLUMN resource_pool.type IS 'OPERATOR | REACTOR_OPERATOR | LINE_OPERATOR | MANUAL_OPERATOR | COOLING_ZONE | BOILER | LAB';
COMMENT ON COLUMN resource_pool.updated_at IS 'Дата последнего изменения (Итерация 6)';

-- ==========================================
-- 3. МАТЕРИАЛЫ И ОСТАТКИ
-- ==========================================
CREATE TABLE material (
                          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                          organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
                          code VARCHAR(50) NOT NULL,
                          name VARCHAR(200) NOT NULL,
                          unit VARCHAR(20) NOT NULL DEFAULT 'kg',
                          category VARCHAR(30) NOT NULL,
                          comment TEXT,
                          UNIQUE (organization_id, code)
);
COMMENT ON TABLE material IS 'Справочник материалов.';

CREATE TABLE material_stock (
                                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                                organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
                                material_id UUID NOT NULL REFERENCES material(id) ON DELETE CASCADE,
                                qty NUMERIC(12,3) NOT NULL DEFAULT 0,
                                reserved_qty NUMERIC(12,3) DEFAULT 0,
                                updated_at TIMESTAMPTZ DEFAULT NOW()
);
COMMENT ON TABLE material_stock IS 'Текущие остатки материалов.';

CREATE TABLE material_supply (
                                 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                                 organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
                                 material_id UUID NOT NULL REFERENCES material(id) ON DELETE CASCADE,
                                 expected_at TIMESTAMPTZ NOT NULL,
                                 qty NUMERIC(12,3) NOT NULL,
                                 status VARCHAR(20) DEFAULT 'PLANNED'
);
COMMENT ON TABLE material_supply IS 'График поставок сырья.';

-- ==========================================
-- 4. ПРОДУКЦИЯ (ПФ и ГП) И РЕЦЕПТУРЫ
-- ==========================================
CREATE TABLE product (
                         id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                         organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
                         code VARCHAR(50) NOT NULL,
                         name VARCHAR(200) NOT NULL,
                         type VARCHAR(10) NOT NULL,
                         viscosity_coeff NUMERIC(5,2) DEFAULT 1.0,
                         requires_heating BOOLEAN DEFAULT FALSE,
                         bottle_volume_l NUMERIC(5,2),
                         fill_speed_per_min NUMERIC(8,2),
                         parent_pf_id UUID REFERENCES product(id),
                         route_type VARCHAR(20) DEFAULT 'DIRECT',
                         comment TEXT,
                         UNIQUE (organization_id, code)
);
COMMENT ON TABLE product IS 'Продукция: полуфабрикаты (ПФ) и готовая продукция (ГП).';

CREATE TABLE recipe (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
                        product_id UUID NOT NULL REFERENCES product(id) ON DELETE CASCADE,
                        base_volume_kg NUMERIC(10,2) NOT NULL,
                        comment TEXT
);
COMMENT ON TABLE recipe IS 'Рецептура полуфабриката.';

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
                                    duration_formula VARCHAR(200),
                                    operator_pool VARCHAR(50),
                                    comment TEXT
);
COMMENT ON TABLE operation_template IS 'Технологическая карта.';
COMMENT ON COLUMN operation_template.operator_pool IS 'REACTOR_OPERATOR | LINE_OPERATOR | MANUAL_OPERATOR | LAB | COOLING_ZONE';

CREATE TABLE setup_matrix (
                              id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                              organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
                              from_product_id UUID NOT NULL REFERENCES product(id),
                              to_product_id UUID NOT NULL REFERENCES product(id),
                              setup_mins INT NOT NULL,
                              UNIQUE (organization_id, from_product_id, to_product_id)
);
COMMENT ON TABLE setup_matrix IS 'Матрица времени переналадки.';

-- ==========================================
-- 6. КАЛЕНДАРЬ
-- ==========================================
CREATE TABLE calendar_event (
                                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                                organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
                                equipment_id UUID REFERENCES equipment(id) ON DELETE CASCADE,
                                event_type VARCHAR(30) NOT NULL,
                                starts_at TIMESTAMPTZ NOT NULL,
                                ends_at TIMESTAMPTZ NOT NULL,
                                comment TEXT,
                                CONSTRAINT chk_dates CHECK (ends_at > starts_at)
);
COMMENT ON TABLE calendar_event IS 'Календарь простоев оборудования.';

-- ==========================================
-- 7. СМЕНЫ
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
COMMENT ON TABLE shift IS 'Производственные смены (одна в день, 08:00-20:00).';

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
                       is_lab_blocked BOOLEAN DEFAULT FALSE,
                       lab_status VARCHAR(30) DEFAULT 'NOT_REQUIRED',
                       lab_block_reason TEXT,
                       lab_blocked_at TIMESTAMPTZ,
                       lab_blocked_by UUID REFERENCES app_user(id) ON DELETE SET NULL,
    -- Итерация 8: Честный Знак
                       cz_marked_qty NUMERIC(12,3) DEFAULT 0,
                       cz_last_scan_at TIMESTAMPTZ,
                       cz_status VARCHAR(30) DEFAULT 'PENDING'
);
COMMENT ON TABLE batch IS 'Производственная партия полуфабриката.';
COMMENT ON COLUMN batch.lab_status IS 'NOT_REQUIRED | PENDING_LAB | APPROVED | BLOCKED';
COMMENT ON COLUMN batch.cz_marked_qty IS 'Промаркировано ЧЗ (штук). Итерация 8.';
COMMENT ON COLUMN batch.cz_last_scan_at IS 'Время последнего сканирования ЧЗ. Итерация 8.';
COMMENT ON COLUMN batch.cz_status IS 'Статус маркировки ЧЗ: NOT_APPLICABLE | PENDING | IN_PROGRESS | COMPLETED. Итерация 8.';

CREATE INDEX idx_batch_org ON batch(organization_id);
CREATE INDEX idx_batch_lab_blocked ON batch(organization_id, is_lab_blocked) WHERE is_lab_blocked = TRUE;

-- Итерация 8: индекс для быстрого поиска партий по статусу маркировки
CREATE INDEX idx_batch_cz_status
    ON batch(organization_id, cz_status)
    WHERE cz_status IS NOT NULL AND cz_status != 'NOT_APPLICABLE';

CREATE TABLE schedule_version (
                                  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                                  organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
                                  name VARCHAR(100) NOT NULL,
                                  version_type VARCHAR(20) NOT NULL,
                                  is_active BOOLEAN DEFAULT FALSE,
                                  created_at TIMESTAMPTZ DEFAULT NOW(),
                                  created_by UUID REFERENCES app_user(id),
                                  frozen_before TIMESTAMPTZ,
                                  parent_version_id UUID REFERENCES schedule_version(id) ON DELETE SET NULL,
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
                                linked_equipment_id UUID REFERENCES equipment(id),
                                resource_pool_id UUID REFERENCES resource_pool(id),
                                task_role VARCHAR(30),
                                shift_id UUID REFERENCES shift(id) ON DELETE SET NULL,
                                planned_start TIMESTAMPTZ NOT NULL,
                                planned_end TIMESTAMPTZ NOT NULL,
                                actual_start TIMESTAMPTZ,
                                actual_end TIMESTAMPTZ,
                                actual_qty NUMERIC(12,3),
                                material_load_at TIMESTAMPTZ,
                                status VARCHAR(20) DEFAULT 'PLANNED',
                                is_pinned BOOLEAN DEFAULT FALSE,
                                operator_pool VARCHAR(50),
                                cooling_mode VARCHAR(10),
                                comment TEXT
);
COMMENT ON TABLE scheduled_task IS 'Задача на диаграмме Ганта.';
COMMENT ON COLUMN scheduled_task.operator_pool IS 'REACTOR_OPERATOR | LINE_OPERATOR | MANUAL_OPERATOR | LAB (Итерация 6)';
COMMENT ON COLUMN scheduled_task.cooling_mode IS 'fast (обычное) | slow (×1.3, при 2+ параллельных охлаждениях) | NULL (не охлаждение). Итерация 7';

CREATE INDEX idx_scheduled_task_org ON scheduled_task(organization_id);
CREATE INDEX idx_scheduled_task_linked_eq ON scheduled_task(linked_equipment_id) WHERE linked_equipment_id IS NOT NULL;
CREATE INDEX idx_scheduled_task_shift ON scheduled_task(shift_id) WHERE shift_id IS NOT NULL;
CREATE INDEX idx_scheduled_task_operator_pool ON scheduled_task(organization_id, schedule_version_id, operator_pool) WHERE operator_pool IS NOT NULL;
CREATE INDEX idx_scheduled_task_cooling_mode ON scheduled_task(organization_id, schedule_version_id, cooling_mode) WHERE cooling_mode IS NOT NULL;
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
                                  action VARCHAR(30) NOT NULL,
                                  result VARCHAR(30),
                                  reason TEXT,
                                  performed_by UUID REFERENCES app_user(id) ON DELETE SET NULL,
                                  performed_at TIMESTAMPTZ DEFAULT NOW(),
                                  comment TEXT
);
COMMENT ON TABLE lab_analysis_log IS 'Журнал лабораторных проверок.';

CREATE INDEX idx_lab_log_org ON lab_analysis_log(organization_id);
CREATE INDEX idx_lab_log_batch ON lab_analysis_log(batch_id);
CREATE INDEX idx_lab_log_performed_at ON lab_analysis_log(performed_at DESC);

-- ==========================================
-- 9b. ЧЕСТНЫЙ ЗНАК (Итерация 8)
-- ==========================================
CREATE TABLE cz_scan_log (
                             id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                             organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
                             batch_id UUID REFERENCES batch(id) ON DELETE SET NULL,
                             scheduled_task_id UUID REFERENCES scheduled_task(id) ON DELETE SET NULL,
                             cz_code VARCHAR(200) NOT NULL,
                             gtin VARCHAR(50),
                             qty NUMERIC(12,3) DEFAULT 1,
                             line_code VARCHAR(50),
                             camera_id VARCHAR(50),
                             scanned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                             created_at TIMESTAMPTZ DEFAULT NOW(),
                             comment TEXT,
                             CONSTRAINT cz_scan_log_code_unique UNIQUE (organization_id, cz_code)
);
COMMENT ON TABLE cz_scan_log IS
    'Журнал сканирований кодов Честного Знака. Итерация 8.';
COMMENT ON COLUMN cz_scan_log.cz_code IS 'Полный код маркировки ЧЗ (DataMatrix).';
COMMENT ON COLUMN cz_scan_log.gtin IS 'GTIN продукта (опционально).';
COMMENT ON COLUMN cz_scan_log.qty IS 'Количество единиц в скане (обычно 1 — бутылка).';
COMMENT ON COLUMN cz_scan_log.line_code IS 'Код линии розлива (LINE_1, LINE_2, ...) для fallback-сопоставления.';
COMMENT ON COLUMN cz_scan_log.camera_id IS 'ID камеры технического зрения.';

CREATE INDEX idx_cz_scan_batch ON cz_scan_log(batch_id) WHERE batch_id IS NOT NULL;
CREATE INDEX idx_cz_scan_task ON cz_scan_log(scheduled_task_id) WHERE scheduled_task_id IS NOT NULL;
CREATE INDEX idx_cz_scan_time ON cz_scan_log(organization_id, scanned_at DESC);
CREATE INDEX idx_cz_scan_unresolved ON cz_scan_log(organization_id) WHERE batch_id IS NULL;
CREATE INDEX idx_cz_scan_camera ON cz_scan_log(organization_id, camera_id) WHERE camera_id IS NOT NULL;

-- ==========================================
-- 10. ПЕРЕПЛАНИРОВАНИЕ (Итерация 4)
-- ==========================================
CREATE TABLE reschedule_log (
                                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                                organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
                                from_version_id UUID REFERENCES schedule_version(id) ON DELETE SET NULL,
                                to_version_id UUID REFERENCES schedule_version(id) ON DELETE SET NULL,
                                reason VARCHAR(30) NOT NULL,
                                changes JSONB NOT NULL DEFAULT '{}',
                                affected_task_count INT DEFAULT 0,
                                moved_task_count INT DEFAULT 0,
                                frozen_before TIMESTAMPTZ,
                                created_at TIMESTAMPTZ DEFAULT NOW(),
                                created_by UUID REFERENCES app_user(id),
                                comment TEXT
);
COMMENT ON TABLE reschedule_log IS 'Журнал перепланирований.';

CREATE INDEX idx_reschedule_log_org ON reschedule_log(organization_id);

-- ==========================================
-- 11. SNAPSHOT-ТАБЛИЦЫ
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
-- Итерации 0-6 завершены. Активны:
--   enable_tank_routing, enable_advisor,
--   enable_material_constraints, enable_shift_planning,
--   enable_rescheduling, enable_lab_blocking,
--   enable_operator_pools, enable_manual_station.
--
-- Итерация 7 завершена (+ hotfix модели деградации охлаждения):
--   enable_cooling_degradation = true
--   cooling_degradation_factor = 1.3
--
-- Итерация 8 завершена (Честный Знак):
--   enable_cz_integration = true
--   cz_completion_threshold = 0.95
--   cz_api_key = "dev-cz-api-key-change-in-production"
--   enable_cz_auto_close = false
-- ==========================================

INSERT INTO organization_settings (organization_id, setting_key, setting_value, description) VALUES
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'max_operators',              '3',                        'Максимальное количество операторов (устар.)'),
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'cooling_zone_capacity',      '2',                        'Максимум реакторов в зоне охлаждения'),
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'default_horizon_hours',      '2160',                     'Горизонт планирования по умолчанию'),
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'max_fill_percent',           '0.70',                     'Максимальная загрузка реактора'),
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'planning_start_date',        '"2026-09-01T08:00:00"',    'Дата начала планирования'),
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'work_start_time',            '"08:00"',                  'Начало рабочего дня'),
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'work_end_time',              '"20:00"',                  'Конец рабочего дня'),

                                                                                                 ('00000000-0000-0000-0000-000000000001', 'enable_tank_routing',        'true',                     'Цепочки реактор→танк→линия (Итерация 1)'),
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'enable_advisor',             'true',                     'Подсказки планировщика (Итерация 2)'),
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'enable_material_constraints','true',                     'Учёт остатков сырья (Итерация 2)'),
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'enable_shift_planning',      'true',                     'Сменное планирование (Итерация 3)'),
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'enable_rescheduling',        'true',                     'Перепланирование (Итерация 4)'),
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'enable_lab_blocking',        'true',                     'Блокировка партии лабораторией (Итерация 5)'),
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'enable_operator_pools',      'true',                     'Пулы операторов (Итерация 6)'),
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'enable_manual_station',      'true',                     'Ручная станция (Итерация 6)'),

                                                                                                 ('00000000-0000-0000-0000-000000000001', 'enable_cooling_degradation', 'true',                     'Деградация охлаждения (Итерация 7)'),
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'cooling_degradation_factor', '1.3',                      'Коэффициент замедления охлаждения ×1.3 (Итерация 7)'),

                                                                                                 ('00000000-0000-0000-0000-000000000001', 'enable_cz_integration',      'true',                     'Интеграция с Честным Знаком (Итерация 8)'),
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'cz_completion_threshold',    '0.95',                     'Порог завершения маркировки партии (Итерация 8)'),
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'cz_api_key',                 '"dev-cz-api-key-change-in-production"', 'API-ключ для вебхука от камер ЧЗ (Итерация 8)'),
                                                                                                 ('00000000-0000-0000-0000-000000000001', 'enable_cz_auto_close',       'false',                    'Автоматически закрывать задачу слива при завершении маркировки (Итерация 8)')
    ON CONFLICT (organization_id, setting_key) DO NOTHING;

-- ==========================================
-- ГОТОВО! Схема создана (v1.9.0).
-- ==========================================