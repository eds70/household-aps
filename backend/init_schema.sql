-- ==========================================
-- APS СИСТЕМА: ПОЛНАЯ СХЕМА БД
-- PostgreSQL 16+
-- Для производства бытовой химии
-- Версия: 4.0.0 (после Итераций 0-12)
-- ==========================================
-- Включает:
--   - Мульти-тенантность и авторизацию
--   - Оборудование с code
--   - Продукцию (ПФ/ГП) с route_type
--   - Рецептуры и материалы
--   - Технологические карты с operator_pool
--   - Цепочки рабочих центров
--   - Сменное планирование (режимы 1x8/3x8/2x12)
--   - Версионирование планов через snapshots
--   - Feature-флаги
--   - Перепланирование
--   - Лабораторные блокировки
--   - Пулы операторов (люди как ресурс)
--   - Охлаждение с деградацией (cooling_mode: fast/slow)
--   - Честный Знак: маркировка ГП (Итерация 8)
--   - operation_name в scheduled_task (Итерация 10)
--   - Централизованные настройки app_settings (Итерация 11)
--   - allow_weekend_work (Итерация 11)
--   - Multi-objective optimization веса (Итерация 12)
--   - What-if сценарии (Итерация 12)
-- ==========================================

-- ==========================================
-- 1. МУЛЬТИ-ТЕНАНТНОСТЬ И АВТОРИЗАЦИЯ
-- ==========================================
CREATE EXTENSION IF NOT EXISTS btree_gist;

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

-- Организация по умолчанию. Нужна до INSERT'ов app_settings/organization_settings
-- из-за FK-ограничений (seed_demo_data.sql делает ON CONFLICT DO NOTHING).
INSERT INTO organization (id, name, slug, settings)
VALUES ('00000000-0000-0000-0000-000000000001', 'Бытовая Химия ООО', 'household-demo',
        '{"work_start": "08:00", "work_end": "20:00"}')
    ON CONFLICT (id) DO NOTHING;

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
COMMENT ON COLUMN app_user.password_hash IS 'Хешированный пароль пользователя (bcrypt)';
COMMENT ON COLUMN app_user.last_login_at IS 'Дата и время последнего входа';

-- ------------------------------------------
-- organization_settings: DEPRECATED (Итерация 11)
-- Оставлена для обратной совместимости.
-- Все новые настройки — в app_settings (см. раздел 14).
-- ------------------------------------------
CREATE TABLE organization_settings (
                                       id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                                       organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
                                       setting_key VARCHAR(100) NOT NULL,
                                       setting_value JSONB NOT NULL,
                                       description TEXT,
                                       updated_at TIMESTAMPTZ DEFAULT NOW(),
                                       UNIQUE (organization_id, setting_key)
);
COMMENT ON TABLE organization_settings IS
    'УСТАРЕВШАЯ таблица настроек. Итерация 11 перенесла настройки в app_settings. '
    'Оставлена для обратной совместимости с миграциями add_history_0_2.sql и add_06..add_12.sql.';
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
COMMENT ON COLUMN equipment.code IS 'Уникальный код (REACTOR_1, TANK_1, LINE_1, BOILER)';

CREATE TABLE equipment_link (
                                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                                organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
                                from_equipment_id UUID NOT NULL REFERENCES equipment(id) ON DELETE CASCADE,
                                to_equipment_id UUID NOT NULL REFERENCES equipment(id) ON DELETE CASCADE,
                                is_direct BOOLEAN DEFAULT TRUE,
                                UNIQUE (from_equipment_id, to_equipment_id)
);
COMMENT ON TABLE equipment_link IS 'Физические связи между оборудованием.';

CREATE TABLE equipment_capability (
                                      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                                      organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
                                      equipment_id UUID NOT NULL REFERENCES equipment(id) ON DELETE CASCADE,
                                      product_id UUID NOT NULL,
                                      max_fill_percent NUMERIC(3,2) DEFAULT 0.80,
                                      UNIQUE (organization_id, equipment_id, product_id)
);
-- FK на product добавляется отдельным ALTER, т.к. product создаётся ниже в этом же скрипте.
COMMENT ON TABLE equipment_capability IS 'Матрица совместимости оборудования и продукции.';

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
COMMENT ON COLUMN resource_pool.type IS
    'OPERATOR | REACTOR_OPERATOR | LINE_OPERATOR | MANUAL_OPERATOR | COOLING_ZONE | BOILER | LAB';
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
                                updated_at TIMESTAMPTZ DEFAULT NOW(),
                                CONSTRAINT material_stock_org_mat_unique
                                    UNIQUE (organization_id, material_id)
);
COMMENT ON TABLE material_stock IS 'Текущие остатки материалов. UNIQUE (organization_id, material_id).';

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
COMMENT ON COLUMN product.route_type IS 'Способ слива ПФ: DIRECT (напрямую на линию) или VIA_TANK (через накопительную емкость)';

ALTER TABLE equipment_capability
    ADD CONSTRAINT equipment_capability_product_fk
    FOREIGN KEY (product_id) REFERENCES product(id) ON DELETE CASCADE;

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
COMMENT ON COLUMN operation_template.operator_pool IS
    'REACTOR_OPERATOR | LINE_OPERATOR | MANUAL_OPERATOR | LAB | COOLING_ZONE';

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
-- 7. СМЕНЫ (Итерация 3, 11)
-- ==========================================
-- Режимы: 1x8 (одна 8ч), 3x8 (три 8ч), 2x12 (две 12ч).
-- Настраивается через app_settings.shift_mode.
-- При смене режима — таблица пересоздаётся через shift_regenerator.py.
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
COMMENT ON TABLE shift IS 'Производственные смены. Режим (1x8/3x8/2x12) задаётся через app_settings.shift_mode.';

CREATE INDEX idx_shift_org_start ON shift(organization_id, starts_at);
CREATE INDEX idx_shift_org_date ON shift(organization_id, starts_at, ends_at);

-- ==========================================
-- 8. ПЛАНИРОВАНИЕ: ЗАКАЗЫ, ПАРТИИ
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
COMMENT ON COLUMN batch.cz_status IS
    'Статус маркировки ЧЗ: NOT_APPLICABLE | PENDING | IN_PROGRESS | COMPLETED. Итерация 8.';

CREATE INDEX idx_batch_org ON batch(organization_id);
CREATE INDEX idx_batch_lab_blocked ON batch(organization_id, is_lab_blocked) WHERE is_lab_blocked = TRUE;
CREATE INDEX idx_batch_cz_status
    ON batch(organization_id, cz_status)
    WHERE cz_status IS NOT NULL AND cz_status != 'NOT_APPLICABLE';
-- ==========================================
-- 9. ВЕРСИИ ПЛАНА И ЗАДАЧИ
-- ==========================================
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
COMMENT ON COLUMN schedule_version.frozen_before IS
    'Задачи, начавшиеся до этого момента, заморожены. Итерация 4.';
COMMENT ON COLUMN schedule_version.parent_version_id IS
    'Родительская версия — от какой версии плана перепланировали. Итерация 4.';

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
    -- Итерация 10: фактическое имя операции (в т.ч. для динамических fill_* подзадач)
                                operation_name VARCHAR(200),
                                comment TEXT
);
COMMENT ON TABLE scheduled_task IS 'Задача на диаграмме Ганта.';
COMMENT ON COLUMN scheduled_task.task_role IS
    'Роль задачи в цепочке: REACTOR_OP, TANK_TRANSFER, LINE_FILL, WASH, SETUP.';
COMMENT ON COLUMN scheduled_task.operator_pool IS
    'REACTOR_OPERATOR | LINE_OPERATOR | MANUAL_OPERATOR | LAB (Итерация 6)';
COMMENT ON COLUMN scheduled_task.cooling_mode IS
    'fast (обычное) | slow (×1.3, при 2+ параллельных охлаждениях) | NULL (не охлаждение). Итерация 7';
COMMENT ON COLUMN scheduled_task.operation_name IS
    'Фактическое имя операции (в т.ч. для динамических fill_*). Итерация 10.';

CREATE INDEX idx_scheduled_task_org ON scheduled_task(organization_id);
CREATE INDEX idx_scheduled_task_linked_eq ON scheduled_task(linked_equipment_id) WHERE linked_equipment_id IS NOT NULL;
CREATE INDEX idx_scheduled_task_shift ON scheduled_task(shift_id) WHERE shift_id IS NOT NULL;
CREATE INDEX idx_scheduled_task_operator_pool
    ON scheduled_task(organization_id, schedule_version_id, operator_pool)
    WHERE operator_pool IS NOT NULL;
CREATE INDEX idx_scheduled_task_cooling_mode
    ON scheduled_task(organization_id, schedule_version_id, cooling_mode)
    WHERE cooling_mode IS NOT NULL;
CREATE INDEX idx_scheduled_task_operation_name
    ON scheduled_task(organization_id, operation_name)
    WHERE operation_name IS NOT NULL;
CREATE INDEX idx_task_equipment_time ON scheduled_task USING GIST (
    organization_id,
    equipment_id,
    tstzrange(planned_start, planned_end)
    );

-- ==========================================
-- 10. ЛАБОРАТОРИЯ (Итерация 5)
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
COMMENT ON COLUMN lab_analysis_log.action IS
    'REQUESTED — запрошен анализ, APPROVED — одобрено, BLOCKED — заблокировано, UNBLOCKED — разблокировано, EXTENDED — продлено';

CREATE INDEX idx_lab_log_org ON lab_analysis_log(organization_id);
CREATE INDEX idx_lab_log_batch ON lab_analysis_log(batch_id);
CREATE INDEX idx_lab_log_performed_at ON lab_analysis_log(performed_at DESC);

-- ==========================================
-- 11. ЧЕСТНЫЙ ЗНАК (Итерация 8)
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
COMMENT ON COLUMN cz_scan_log.line_code IS
    'Код линии розлива (LINE_1, LINE_2, ...) для fallback-сопоставления.';
COMMENT ON COLUMN cz_scan_log.camera_id IS 'ID камеры технического зрения.';

CREATE INDEX idx_cz_scan_batch ON cz_scan_log(batch_id) WHERE batch_id IS NOT NULL;
CREATE INDEX idx_cz_scan_task ON cz_scan_log(scheduled_task_id) WHERE scheduled_task_id IS NOT NULL;
CREATE INDEX idx_cz_scan_time ON cz_scan_log(organization_id, scanned_at DESC);
CREATE INDEX idx_cz_scan_unresolved ON cz_scan_log(organization_id) WHERE batch_id IS NULL;
CREATE INDEX idx_cz_scan_camera ON cz_scan_log(organization_id, camera_id) WHERE camera_id IS NOT NULL;

-- ==========================================
-- 12. ПЕРЕПЛАНИРОВАНИЕ (Итерация 4)
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
COMMENT ON COLUMN reschedule_log.reason IS 'DELAY | BREAKDOWN | QTY_CHANGE | MANUAL';

CREATE INDEX idx_reschedule_log_org ON reschedule_log(organization_id);
CREATE INDEX idx_reschedule_log_from_version ON reschedule_log(from_version_id);
CREATE INDEX idx_reschedule_log_to_version ON reschedule_log(to_version_id);

-- ==========================================
-- 13. SNAPSHOT-ТАБЛИЦЫ
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
COMMENT ON COLUMN equipment_snapshot.code IS 'Код оборудования (снимок на момент планирования)';

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
COMMENT ON COLUMN product_snapshot.route_type IS 'Способ слива: DIRECT | VIA_TANK (снимок)';

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
COMMENT ON COLUMN operation_snapshot.operator_pool IS 'Пул операторов (снимок)';

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
-- 14. ЦЕНТРАЛИЗОВАННЫЕ НАСТРОЙКИ (Итерация 11, Шаг 5)
-- ==========================================
-- Единый источник правды для всех настроек приложения.
-- Заменяет organization_settings.
--
-- Хранит:
--   - feature-флаги (enable_*)
--   - параметры планирования (horizon_hours, timeout_seconds, max_fill_percent)
--   - режим смен (shift_mode, shift_intervals, shift_duration_hours)
--   - работу в выходные (allow_weekend_work)
--   - охлаждение (enable_cooling_degradation, cooling_degradation_factor)
--   - ЧЗ (enable_cz_integration, cz_completion_threshold, cz_api_key)
--   - веса multi-objective (weight_makespan, weight_setup, ...)
--
-- Чтение: через модуль settings_reader.py.
-- Метаданные (label, description, value_type, min/max, options)
-- описаны в settings.py — SETTINGS_REGISTRY.
-- ==========================================
CREATE TABLE app_settings (
                              id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                              organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
                              category VARCHAR(50) NOT NULL,
                              setting_key VARCHAR(100) NOT NULL,
                              setting_value JSONB NOT NULL,
                              default_value JSONB,
                              value_type VARCHAR(20) NOT NULL,
                              label VARCHAR(200) NOT NULL,
                              description TEXT,
                              min_value NUMERIC,
                              max_value NUMERIC,
                              options JSONB,
                              display_order INT DEFAULT 0,
                              is_system BOOLEAN DEFAULT FALSE,
                              updated_at TIMESTAMPTZ DEFAULT NOW(),
                              UNIQUE (organization_id, setting_key)
);
COMMENT ON TABLE app_settings IS
    'Централизованное хранилище всех настроек приложения с метаданными для UI. Итерация 11.';
COMMENT ON COLUMN app_settings.category IS
    'Категория для группировки в UI: planning, shifts, cooling, calendar, '
    'materials, lab, cz, resources, features, optimization.';
COMMENT ON COLUMN app_settings.value_type IS
    'Тип значения: int | float | bool | str | json | select.';
COMMENT ON COLUMN app_settings.is_system IS
    'Системные настройки нельзя изменить через UI '
    '(управляются программно, например shift_intervals).';

CREATE INDEX idx_app_settings_category ON app_settings(organization_id, category);
CREATE INDEX idx_app_settings_updated ON app_settings(organization_id, updated_at DESC);

-- ==========================================
-- 14b. ЖУРНАЛ ИЗМЕНЕНИЙ ОСТАТКОВ (Итерация 13.2)
-- ==========================================
CREATE TABLE material_stock_log (
                                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                                    organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
                                    material_id UUID NOT NULL REFERENCES material(id) ON DELETE CASCADE,
                                    action VARCHAR(20) NOT NULL,
                                    old_qty NUMERIC(12,3),
                                    new_qty NUMERIC(12,3),
                                    old_reserved_qty NUMERIC(12,3),
                                    new_reserved_qty NUMERIC(12,3),
                                    delta_qty NUMERIC(12,3),
                                    delta_reserved_qty NUMERIC(12,3),
                                    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                                    changed_by UUID REFERENCES app_user(id) ON DELETE SET NULL,
                                    source VARCHAR(30) DEFAULT 'SYSTEM',
                                    reason TEXT,
                                    comment TEXT
);
COMMENT ON TABLE material_stock_log IS 'Журнал изменений остатков материалов.';

CREATE INDEX idx_material_stock_log_material
    ON material_stock_log(organization_id, material_id, changed_at DESC);
CREATE INDEX idx_material_stock_log_changed_at
    ON material_stock_log(organization_id, changed_at DESC);
CREATE INDEX idx_material_stock_log_source
    ON material_stock_log(organization_id, source, changed_at DESC);

-- ==========================================
-- 2. ФУНКЦИЯ-ТРИГГЕР
-- ==========================================
CREATE OR REPLACE FUNCTION log_material_stock_change()
RETURNS TRIGGER AS $$
DECLARE
v_user_id UUID;
    v_source  VARCHAR(30);
    v_reason  TEXT;
BEGIN
    -- Читаем session variable app.current_user_id (устанавливается через
    -- set_config('app.current_user_id', ..., true) в API-слое).
BEGIN
        v_user_id := NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid;
EXCEPTION WHEN OTHERS THEN
        v_user_id := NULL;
END;

BEGIN
        v_source := NULLIF(current_setting('app.change_source', TRUE), '');
EXCEPTION WHEN OTHERS THEN
        v_source := NULL;
END;

BEGIN
        v_reason := NULLIF(current_setting('app.change_reason', TRUE), '');
EXCEPTION WHEN OTHERS THEN
        v_reason := NULL;
END;

    IF v_source IS NULL THEN
        v_source := 'SYSTEM';
END IF;

    -- ---------------- INSERT ----------------
    IF TG_OP = 'INSERT' THEN
        INSERT INTO material_stock_log (
            organization_id, material_id, action,
            old_qty, new_qty, old_reserved_qty, new_reserved_qty,
            delta_qty, delta_reserved_qty,
            changed_by, source, reason, comment
        ) VALUES (
            NEW.organization_id, NEW.material_id, 'INSERT',
            NULL, NEW.qty,
            NULL, NEW.reserved_qty,
            COALESCE(NEW.qty, 0),
            COALESCE(NEW.reserved_qty, 0),
            v_user_id, v_source, v_reason,
            'Создание записи остатков'
        );
RETURN NEW;
END IF;

    -- ---------------- UPDATE ----------------
    IF TG_OP = 'UPDATE' THEN
        -- Логируем только если значения реально изменились
        IF (OLD.qty IS DISTINCT FROM NEW.qty)
           OR (OLD.reserved_qty IS DISTINCT FROM NEW.reserved_qty) THEN
            INSERT INTO material_stock_log (
                organization_id, material_id, action,
                old_qty, new_qty, old_reserved_qty, new_reserved_qty,
                delta_qty, delta_reserved_qty,
                changed_by, source, reason
            ) VALUES (
                NEW.organization_id, NEW.material_id, 'UPDATE',
                OLD.qty, NEW.qty,
                OLD.reserved_qty, NEW.reserved_qty,
                COALESCE(NEW.qty, 0) - COALESCE(OLD.qty, 0),
                COALESCE(NEW.reserved_qty, 0) - COALESCE(OLD.reserved_qty, 0),
                v_user_id, v_source, v_reason
            );
END IF;
RETURN NEW;
END IF;

    -- ---------------- DELETE ----------------
    IF TG_OP = 'DELETE' THEN
        -- Не логируем DELETE, если материал уже удалён (каскадный delete
        -- от `DELETE FROM material`). Иначе FK violation.
        IF NOT EXISTS (
            SELECT 1 FROM material WHERE id = OLD.material_id
        ) THEN
            RETURN OLD;
END IF;

INSERT INTO material_stock_log (
    organization_id, material_id, action,
    old_qty, new_qty, old_reserved_qty, new_reserved_qty,
    delta_qty, delta_reserved_qty,
    changed_by, source, reason, comment
) VALUES (
             OLD.organization_id, OLD.material_id, 'DELETE',
             OLD.qty, NULL,
             OLD.reserved_qty, NULL,
             -COALESCE(OLD.qty, 0),
             -COALESCE(OLD.reserved_qty, 0),
             v_user_id, v_source, v_reason,
             'Удаление записи остатков'
         );
RETURN OLD;
END IF;

RETURN NULL;
END;
$$ LANGUAGE plpgsql;


-- ==========================================
-- 3. ТРИГГЕР
-- ==========================================
DROP TRIGGER IF EXISTS trg_material_stock_log ON material_stock;
CREATE TRIGGER trg_material_stock_log
    AFTER INSERT OR UPDATE OR DELETE ON material_stock
    FOR EACH ROW EXECUTE FUNCTION log_material_stock_change();

-- TANK_2 (Итерация 13.4, fix C2)
-- Будет создан через seed_demo_data.sql

-- ==========================================
-- 15. ДЕМО-ДАННЫЕ: НАСТРОЙКИ ОРГАНИЗАЦИИ
-- ==========================================
-- Все настройки хранятся в app_settings (Итерация 11).
-- organization_settings — только для обратной совместимости,
-- заполняется ключевыми флагами для совместимости со старыми миграциями.
--
-- Идемпотентно: ON CONFLICT DO NOTHING.
-- ==========================================

-- ------------------------------------------
-- 15.1. FEATURE-ФЛАГИ (10 штук)
-- ------------------------------------------
INSERT INTO app_settings
(organization_id, category, setting_key, setting_value, value_type,
 label, description, display_order)
VALUES
    ('00000000-0000-0000-0000-000000000001', 'features', 'enable_tank_routing', 'true', 'bool',
     'Маршруты через танк', 'Реактор → танк → линия (Итерация 1)', 10),
    ('00000000-0000-0000-0000-000000000001', 'features', 'enable_advisor', 'true', 'bool',
     'Advisor (подсказки)', 'Анализ плана и подсказки (Итерация 2)', 40),
    ('00000000-0000-0000-0000-000000000001', 'materials', 'enable_material_constraints', 'true', 'bool',
     'Учёт остатков сырья', 'Advisor проверяет дефицит сырья (Итерация 2)', 10),
    ('00000000-0000-0000-0000-000000000001', 'features', 'enable_shift_planning', 'true', 'bool',
     'Сменное планирование', 'Разбивка по сменам и РМ мастера (Итерация 3)', 20),
    ('00000000-0000-0000-0000-000000000001', 'features', 'enable_rescheduling', 'true', 'bool',
     'Перепланирование', 'Пересчёт при изменениях (Итерация 4)', 30),
    ('00000000-0000-0000-0000-000000000001', 'lab', 'enable_lab_blocking', 'true', 'bool',
     'Блокировка лабораторией', 'Партия не участвует в планировании до одобрения (Итерация 5)', 10),
    ('00000000-0000-0000-0000-000000000001', 'resources', 'enable_operator_pools', 'true', 'bool',
     'Пулы операторов', 'Учитывать ограничения по людям (Итерация 6)', 10),
    ('00000000-0000-0000-0000-000000000001', 'resources', 'enable_manual_station', 'true', 'bool',
     'Ручная станция', 'Использовать LINE_3 (ручной слив) (Итерация 6)', 20),
    ('00000000-0000-0000-0000-000000000001', 'cooling', 'enable_cooling_degradation', 'true', 'bool',
     'Деградация охлаждения', 'Замедлять охлаждение при 2+ параллельных (Итерация 7)', 10),
    ('00000000-0000-0000-0000-000000000001', 'cz', 'enable_cz_integration', 'true', 'bool',
     'Интеграция с ЧЗ', 'Приём сканов от камер ТС (Итерация 8)', 10)
    ON CONFLICT (organization_id, setting_key) DO NOTHING;

-- ------------------------------------------
-- 15.2. ПАРАМЕТРЫ ПЛАНИРОВАНИЯ
-- ------------------------------------------
INSERT INTO app_settings
(organization_id, category, setting_key, setting_value, value_type,
 label, description, min_value, max_value, display_order)
VALUES
    ('00000000-0000-0000-0000-000000000001', 'planning', 'planning_start_date', '"2026-09-01T08:00:00"', 'str',
     'Дата начала планирования', 'Дата и время старта планирования (МСК)',
     NULL, NULL, 10),
    ('00000000-0000-0000-0000-000000000001', 'planning', 'horizon_hours', '720', 'int',
     'Горизонт планирования (ч)', 'Сколько часов вперёд строить план (по умолчанию 30 дней)',
     24, 8760, 20),
    ('00000000-0000-0000-0000-000000000001', 'planning', 'timeout_seconds', '600', 'int',
     'Таймаут solver (сек)', 'Максимальное время работы CP-SAT solver',
     10, 3600, 30),
    ('00000000-0000-0000-0000-000000000001', 'planning', 'max_fill_percent', '0.70', 'float',
     'Максимальная загрузка реактора', 'Доля от объёма реактора (0.0–1.0)',
     0.1, 1.0, 40)
    ON CONFLICT (organization_id, setting_key) DO NOTHING;

-- ------------------------------------------
-- 15.3. РЕЖИМ СМЕН (Итерация 11, Шаг 6)
-- ------------------------------------------
INSERT INTO app_settings
(organization_id, category, setting_key, setting_value, value_type,
 label, description, options, display_order, is_system)
VALUES
    ('00000000-0000-0000-0000-000000000001', 'shifts', 'shift_mode', '"2x12"', 'select',
     'Режим смен', 'Режим работы: одна 8ч, три 8ч или две 12ч',
     '[
       {"value": "1x8",  "label": "1 смена × 8 часов"},
       {"value": "3x8",  "label": "3 смены × 8 часов"},
       {"value": "2x12", "label": "2 смены × 12 часов"}
     ]'::jsonb,
     10, FALSE)
    ON CONFLICT (organization_id, setting_key) DO NOTHING;

INSERT INTO app_settings
(organization_id, category, setting_key, setting_value, value_type,
 label, description, display_order, is_system)
VALUES
    ('00000000-0000-0000-0000-000000000001', 'shifts', 'shift_intervals',
     '[{"start": "08:00", "end": "20:00"}, {"start": "20:00", "end": "08:00"}]'::jsonb,
     'json', 'Интервалы смен',
     'Список интервалов смен в сутках (управляется режимом)',
     20, TRUE)
    ON CONFLICT (organization_id, setting_key) DO NOTHING;

INSERT INTO app_settings
(organization_id, category, setting_key, setting_value, value_type,
 label, description, min_value, max_value, display_order, is_system)
VALUES
    ('00000000-0000-0000-0000-000000000001', 'shifts', 'shift_duration_hours', '12', 'int',
     'Длительность смены (ч)', 'Длительность одной смены (управляется режимом)',
     1, 24, 30, TRUE)
    ON CONFLICT (organization_id, setting_key) DO NOTHING;

INSERT INTO app_settings
(organization_id, category, setting_key, setting_value, value_type,
 label, description, display_order)
VALUES
    ('00000000-0000-0000-0000-000000000001', 'shifts', 'work_start_time', '"08:00"', 'str',
     'Начало рабочего дня', 'Начало первого рабочего интервала', 40),
    ('00000000-0000-0000-0000-000000000001', 'shifts', 'work_end_time', '"20:00"', 'str',
     'Конец рабочего дня', 'Конец последнего рабочего интервала', 50)
    ON CONFLICT (organization_id, setting_key) DO NOTHING;

-- ------------------------------------------
-- 15.4. КАЛЕНДАРЬ (Итерация 11, Шаг 6)
-- ------------------------------------------
INSERT INTO app_settings
(organization_id, category, setting_key, setting_value, value_type,
 label, description, display_order)
VALUES
    ('00000000-0000-0000-0000-000000000001', 'calendar', 'allow_weekend_work', 'false', 'bool',
     'Работа в выходные', 'Разрешить работу в субботу и воскресенье', 5),
    ('00000000-0000-0000-0000-000000000001', 'calendar', 'max_task_hours_for_calendar', '12.0', 'float',
     'Макс. длительность задачи (ч)', 'Задачи длиннее — пропускаются в календарных ограничениях', 10),
    ('00000000-0000-0000-0000-000000000001', 'calendar', 'max_fill_part_hours', '8.0', 'float',
     'Макс. длительность части слива (ч)', 'Длинные LINE_FILL разбиваются на части по этой длительности', 20)
    ON CONFLICT (organization_id, setting_key) DO NOTHING;

-- ------------------------------------------
-- 15.5. ОХЛАЖДЕНИЕ (Итерация 7)
-- ------------------------------------------
INSERT INTO app_settings
(organization_id, category, setting_key, setting_value, value_type,
 label, description, min_value, max_value, display_order)
VALUES
    ('00000000-0000-0000-0000-000000000001', 'cooling', 'cooling_degradation_factor', '1.3', 'float',
     'Коэффициент замедления', 'Во сколько раз замедлять охлаждение (например, 1.3)',
     1.0, 3.0, 20),
    ('00000000-0000-0000-0000-000000000001', 'cooling', 'cooling_zone_capacity', '2', 'int',
     'Ёмкость зоны охлаждения', 'Сколько реакторов могут охлаждаться одновременно',
     1, 10, 30)
    ON CONFLICT (organization_id, setting_key) DO NOTHING;

-- ------------------------------------------
-- 15.6. ЧЕСТНЫЙ ЗНАК (Итерация 8)
-- ------------------------------------------
INSERT INTO app_settings
(organization_id, category, setting_key, setting_value, value_type,
 label, description, min_value, max_value, display_order)
VALUES
    ('00000000-0000-0000-0000-000000000001', 'cz', 'cz_completion_threshold', '0.95', 'float',
     'Порог завершения ЧЗ', 'Доля от плана (0.0–1.0)',
     0.1, 1.0, 20)
    ON CONFLICT (organization_id, setting_key) DO NOTHING;

INSERT INTO app_settings
(organization_id, category, setting_key, setting_value, value_type,
 label, description, display_order)
VALUES
    ('00000000-0000-0000-0000-000000000001', 'cz', 'cz_api_key',
     '"dev-cz-api-key-change-in-production"', 'str',
     'API-ключ ЧЗ', 'Заголовок X-CZ-Api-Key для вебхука', 30),
    ('00000000-0000-0000-0000-000000000001', 'cz', 'enable_cz_auto_close', 'false', 'bool',
     'Автозакрытие при ЧЗ', 'Закрывать задачу слива при завершении маркировки', 40)
    ON CONFLICT (organization_id, setting_key) DO NOTHING;

-- ------------------------------------------
-- 15.7. MULTI-OBJECTIVE (Итерация 12)
-- ------------------------------------------
-- Веса в [0, 1]. Хотя бы один должен быть > 0.
-- По умолчанию: только makespan = 1.0 (обратная совместимость).
--
-- Компоненты целевой функции:
--   - makespan        — общее время плана (мин)
--   - setup           — сумма переналадок (мин)
--   - underload       — сумма недогрузки реакторов (кг)
--   - cooling_slow    — число замедленных охлаждений (шт)
--   - tardiness       — сумма просрочек due_date (мин)
-- ------------------------------------------
INSERT INTO app_settings
(organization_id, category, setting_key, setting_value, value_type,
 label, description, min_value, max_value, display_order)
VALUES
    ('00000000-0000-0000-0000-000000000001', 'optimization', 'weight_makespan', '1.0', 'float',
     'Вес: Makespan', 'Приоритет минимизации общего времени плана (0 — отключено)',
     0.0, 1.0, 10),
    ('00000000-0000-0000-0000-000000000001', 'optimization', 'weight_setup', '0.0', 'float',
     'Вес: Переналадки', 'Приоритет минимизации времени переналадок (setup)',
     0.0, 1.0, 20),
    ('00000000-0000-0000-0000-000000000001', 'optimization', 'weight_underload', '0.0', 'float',
     'Вес: Недогрузка реакторов', 'Приоритет равномерной загрузки реакторов',
     0.0, 1.0, 30),
    ('00000000-0000-0000-0000-000000000001', 'optimization', 'weight_cooling_slow', '0.0', 'float',
     'Вес: Замедленное охлаждение', 'Приоритет избегания замедленного охлаждения',
     0.0, 1.0, 40),
    ('00000000-0000-0000-0000-000000000001', 'optimization', 'weight_tardiness', '0.0', 'float',
     'Вес: Просрочка заказов', 'Приоритет соблюдения due_date',
     0.0, 1.0, 50)
    ON CONFLICT (organization_id, setting_key) DO NOTHING;

-- ------------------------------------------
-- 15.8. ОБРАТНАЯ СОВМЕСТИМОСТЬ: organization_settings
-- ------------------------------------------
-- Дублируем feature-флаги в organization_settings для совместимости
-- со старыми миграциями (add_history_0_2.sql, add_06..add_12.sql).
-- УДАЛИТЬ в будущих версиях, когда все миграции будут переведены на app_settings.
-- ------------------------------------------
INSERT INTO organization_settings
(organization_id, setting_key, setting_value, description)
VALUES
    ('00000000-0000-0000-0000-000000000001', 'max_operators', '3',
     'Максимальное количество операторов (устар.)'),
    ('00000000-0000-0000-0000-000000000001', 'cooling_zone_capacity', '2',
     'Максимум реакторов в зоне охлаждения'),
    ('00000000-0000-0000-0000-000000000001', 'default_horizon_hours', '2160',
     'Горизонт планирования по умолчанию (устар.)'),
    ('00000000-0000-0000-0000-000000000001', 'max_fill_percent', '0.70',
     'Максимальная загрузка реактора'),
    ('00000000-0000-0000-0000-000000000001', 'planning_start_date', '"2026-09-01T08:00:00"',
     'Дата начала планирования'),
    ('00000000-0000-0000-0000-000000000001', 'work_start_time', '"08:00"',
     'Начало рабочего дня'),
    ('00000000-0000-0000-0000-000000000001', 'work_end_time', '"20:00"',
     'Конец рабочего дня'),

    ('00000000-0000-0000-0000-000000000001', 'enable_tank_routing', 'true',
     'Цепочки реактор→танк→линия (Итерация 1)'),
    ('00000000-0000-0000-0000-000000000001', 'enable_advisor', 'true',
     'Подсказки планировщика (Итерация 2)'),
    ('00000000-0000-0000-0000-000000000001', 'enable_material_constraints', 'true',
     'Учёт остатков сырья (Итерация 2)'),
    ('00000000-0000-0000-0000-000000000001', 'enable_shift_planning', 'true',
     'Сменное планирование (Итерация 3)'),
    ('00000000-0000-0000-0000-000000000001', 'enable_rescheduling', 'true',
     'Перепланирование (Итерация 4)'),
    ('00000000-0000-0000-0000-000000000001', 'enable_lab_blocking', 'true',
     'Блокировка партии лабораторией (Итерация 5)'),
    ('00000000-0000-0000-0000-000000000001', 'enable_operator_pools', 'true',
     'Пулы операторов (Итерация 6)'),
    ('00000000-0000-0000-0000-000000000001', 'enable_manual_station', 'true',
     'Ручная станция (Итерация 6)'),
    ('00000000-0000-0000-0000-000000000001', 'enable_cooling_degradation', 'true',
     'Деградация охлаждения (Итерация 7)'),
    ('00000000-0000-0000-0000-000000000001', 'cooling_degradation_factor', '1.3',
     'Коэффициент замедления охлаждения ×1.3 (Итерация 7)'),
    ('00000000-0000-0000-0000-000000000001', 'enable_cz_integration', 'true',
     'Интеграция с Честным Знаком (Итерация 8)'),
    ('00000000-0000-0000-0000-000000000001', 'cz_completion_threshold', '0.95',
     'Порог завершения маркировки партии (Итерация 8)'),
    ('00000000-0000-0000-0000-000000000001', 'cz_api_key',
     '"dev-cz-api-key-change-in-production"',
     'API-ключ для вебхука от камер ЧЗ (Итерация 8)'),
    ('00000000-0000-0000-0000-000000000001', 'enable_cz_auto_close', 'false',
     'Автоматически закрывать задачу слива при завершении маркировки (Итерация 8)')
    ON CONFLICT (organization_id, setting_key) DO NOTHING;
-- ==========================================
-- 16. WHAT-IF СЦЕНАРИИ (Итерация 12)
-- ==========================================
-- Сценарное планирование: пользователь задаёт изменения (JSONB),
-- запускает расчёт и сравнивает результат с базовым планом.
--
-- Изменения НЕ применяются к основной БД — используется
-- архитектура 2 транзакций (rollback + commit).
-- Результат сохраняется как отдельная schedule_version.
--
-- Формат changes (JSONB):
--   {
--     "orders": [
--       {"action": "add_order", "product_code": "...", "target_qty": N, "due_date": "..."},
--       {"action": "cancel_order", "order_id": "uuid"},
--       {"action": "change_qty", "order_id": "uuid", "new_qty": N},
--       {"action": "change_due_date", "order_id": "uuid", "new_due_date": "..."}
--     ],
--     "shift_mode": "1x8" | "3x8" | "2x12",
--     "resource_capacity": {"REACTOR_OPERATOR": N, "LINE_OPERATOR": M},
--     "calendar_events": [
--       {"action": "add", "event_type": "...", "equipment_code": "...",
--        "starts_at": "...", "ends_at": "...", "comment": "..."},
--       {"action": "remove", "event_id": "uuid"}
--     ]
--   }
-- ==========================================
CREATE TABLE whatif_scenario (
                                 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                                 organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
                                 name VARCHAR(200) NOT NULL,
                                 comment TEXT,
                                 base_version_id UUID NOT NULL REFERENCES schedule_version(id) ON DELETE CASCADE,
                                 result_version_id UUID REFERENCES schedule_version(id) ON DELETE SET NULL,
                                 changes JSONB NOT NULL DEFAULT '{}',
                                 status VARCHAR(30) NOT NULL DEFAULT 'DRAFT',
                                 created_at TIMESTAMPTZ DEFAULT NOW(),
                                 updated_at TIMESTAMPTZ DEFAULT NOW(),
                                 created_by UUID REFERENCES app_user(id) ON DELETE SET NULL
);

COMMENT ON TABLE whatif_scenario IS
    'What-if сценарии. Сравнение альтернативных планов. Итерация 12.';
COMMENT ON COLUMN whatif_scenario.status IS
    'DRAFT | RUNNING | DONE | FAILED';
COMMENT ON COLUMN whatif_scenario.changes IS
    'JSON с изменениями. Формат: {orders: [...], shift_mode: "...", '
    'resource_capacity: {...}, calendar_events: [...]}';
COMMENT ON COLUMN whatif_scenario.base_version_id IS
    'Базовый план, от которого считается сценарий.';
COMMENT ON COLUMN whatif_scenario.result_version_id IS
    'Результат расчёта — новая версия плана. Заполняется после run.';

CREATE INDEX idx_whatif_scenario_org
    ON whatif_scenario(organization_id);
CREATE INDEX idx_whatif_scenario_base
    ON whatif_scenario(base_version_id);
CREATE INDEX idx_whatif_scenario_status
    ON whatif_scenario(organization_id, status);
CREATE INDEX idx_whatif_scenario_created
    ON whatif_scenario(organization_id, created_at DESC);

-- ==========================================
-- ГОТОВО! Схема создана (v4.0.0).
-- ==========================================
-- Что дальше:
--   1. Применить seed_demo_data.sql (демо-данные).
--   2. python -m scripts.create_admin_user (создать админа).
--   3. Запустить backend и frontend.
--
-- Миграции add_12.sql, add_13.sql, add_14.sql, add_15.sql, add_16.sql
-- уже включены в эту схему. Для существующих БД они остаются как
-- история изменений.
-- ==========================================