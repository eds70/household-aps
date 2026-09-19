-- ==========================================
-- МИГРАЦИЯ 13: Единая таблица app_settings
-- ==========================================
-- Создаёт централизованное хранилище всех настроек приложения:
--   1. Таблица app_settings с метаданными (тип, min/max, options, label).
--   2. Переносит существующие настройки из organization_settings.
--   3. Добавляет настройки режима смен (shift_mode, shift_intervals,
--      shift_duration_hours).
--
-- Идемпотентна: можно применять повторно.
-- ==========================================

-- ==========================================
-- 1. СОЗДАНИЕ ТАБЛИЦЫ app_settings
-- ==========================================
CREATE TABLE IF NOT EXISTS app_settings (
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
    'Централизованное хранилище всех настроек приложения с метаданными для UI.';

COMMENT ON COLUMN app_settings.category IS
    'Категория для группировки в UI: planning, shifts, cooling, calendar, '
    'materials, lab, cz, resources, features.';

COMMENT ON COLUMN app_settings.value_type IS
    'Тип значения: int | float | bool | str | json | select.';

COMMENT ON COLUMN app_settings.is_system IS
    'Системные настройки нельзя изменить через UI '
    '(управляются программно, например shift_intervals).';

CREATE INDEX IF NOT EXISTS idx_app_settings_category
    ON app_settings(organization_id, category);

CREATE INDEX IF NOT EXISTS idx_app_settings_updated
    ON app_settings(organization_id, updated_at DESC);


-- ==========================================
-- 2. ПЕРЕНОС СУЩЕСТВУЮЩИХ НАСТРОЕК
-- ==========================================
-- Переносим все настройки из organization_settings в app_settings.
-- Для каждой настройки задаём метаданные (category, label, type).
-- ==========================================

DO $$
BEGIN

-- ==========================================
-- 2.1. PLANNING
-- ==========================================
INSERT INTO app_settings
(organization_id, category, setting_key, setting_value,
 value_type, label, description, min_value, max_value,
 display_order, is_system)
SELECT
    organization_id,
    'planning',
    'planning_start_date',
    setting_value,
    'str',
    'Дата начала планирования',
    'Дата и время старта планирования (МСК)',
    NULL, NULL, 10, FALSE
FROM organization_settings
WHERE setting_key = 'planning_start_date'
    ON CONFLICT (organization_id, setting_key) DO NOTHING;

INSERT INTO app_settings
(organization_id, category, setting_key, setting_value,
 value_type, label, description, min_value, max_value,
 display_order, is_system)
SELECT
    organization_id, 'planning', 'horizon_hours', setting_value,
    'int', 'Горизонт планирования (ч)',
    'Сколько часов вперёд строить план',
    24, 8760, 20, FALSE
FROM organization_settings
WHERE setting_key = 'default_horizon_hours'
    ON CONFLICT (organization_id, setting_key) DO NOTHING;

INSERT INTO app_settings
(organization_id, category, setting_key, setting_value,
 value_type, label, description, min_value, max_value,
 display_order, is_system)
SELECT
    organization_id, 'planning', 'max_fill_percent', setting_value,
    'float', 'Максимальная загрузка реактора',
    'Доля от объёма реактора (0.0–1.0)',
    0.1, 1.0, 30, FALSE
FROM organization_settings
WHERE setting_key = 'max_fill_percent'
    ON CONFLICT (organization_id, setting_key) DO NOTHING;

INSERT INTO app_settings
(organization_id, category, setting_key, setting_value,
 value_type, label, description, min_value, max_value,
 display_order, is_system)
SELECT
    organization_id, 'planning', 'timeout_seconds', '600'::jsonb,
        'int', 'Таймаут solver (сек)',
    'Максимальное время работы CP-SAT solver',
    10, 3600, 40, FALSE
FROM organization_settings
WHERE setting_key = 'planning_start_date'
    ON CONFLICT (organization_id, setting_key) DO NOTHING;


-- ==========================================
-- 2.2. SHIFTS (новые настройки)
-- ==========================================
INSERT INTO app_settings
(organization_id, category, setting_key, setting_value,
 value_type, label, description,
 options, display_order, is_system)
SELECT
    organization_id, 'shifts', 'shift_mode', '"2x12"'::jsonb,
        'select', 'Режим смен',
    'Режим работы: одна 8ч, три 8ч или две 12ч',
    '[
        {"value": "1x8", "label": "1 смена × 8 часов"},
        {"value": "3x8", "label": "3 смены × 8 часов"},
        {"value": "2x12", "label": "2 смены × 12 часов"}
    ]'::jsonb,
        10, FALSE
FROM organization_settings
WHERE setting_key = 'planning_start_date'
    ON CONFLICT (organization_id, setting_key) DO NOTHING;

INSERT INTO app_settings
(organization_id, category, setting_key, setting_value,
 value_type, label, description, display_order, is_system)
SELECT
    organization_id, 'shifts', 'shift_intervals',
    '[{"start": "08:00", "end": "20:00"}, {"start": "20:00", "end": "08:00"}]'::jsonb,
        'json', 'Интервалы смен',
    'Список интервалов смен в сутках (управляется режимом)',
    20, TRUE
FROM organization_settings
WHERE setting_key = 'planning_start_date'
    ON CONFLICT (organization_id, setting_key) DO NOTHING;

INSERT INTO app_settings
(organization_id, category, setting_key, setting_value,
 value_type, label, description, min_value, max_value,
 display_order, is_system)
SELECT
    organization_id, 'shifts', 'shift_duration_hours', '12'::jsonb,
        'int', 'Длительность смены (ч)',
    'Длительность одной смены (управляется режимом)',
    1, 24, 30, TRUE
FROM organization_settings
WHERE setting_key = 'planning_start_date'
    ON CONFLICT (organization_id, setting_key) DO NOTHING;

INSERT INTO app_settings
(organization_id, category, setting_key, setting_value,
 value_type, label, description, display_order, is_system)
SELECT
    organization_id, 'shifts', 'work_start_time', setting_value,
    'str', 'Начало рабочего дня',
    'Начало первого рабочего интервала',
    40, FALSE
FROM organization_settings
WHERE setting_key = 'work_start_time'
    ON CONFLICT (organization_id, setting_key) DO NOTHING;

INSERT INTO app_settings
(organization_id, category, setting_key, setting_value,
 value_type, label, description, display_order, is_system)
SELECT
    organization_id, 'shifts', 'work_end_time', setting_value,
    'str', 'Конец рабочего дня',
    'Конец последнего рабочего интервала',
    50, FALSE
FROM organization_settings
WHERE setting_key = 'work_end_time'
    ON CONFLICT (organization_id, setting_key) DO NOTHING;


-- ==========================================
-- 2.3. COOLING
-- ==========================================
INSERT INTO app_settings
(organization_id, category, setting_key, setting_value,
 value_type, label, description, display_order, is_system)
SELECT
    organization_id, 'cooling', 'enable_cooling_degradation', setting_value,
    'bool', 'Деградация охлаждения',
    'Замедлять охлаждение при 2+ параллельных реакторах',
    10, FALSE
FROM organization_settings
WHERE setting_key = 'enable_cooling_degradation'
    ON CONFLICT (organization_id, setting_key) DO NOTHING;

INSERT INTO app_settings
(organization_id, category, setting_key, setting_value,
 value_type, label, description, min_value, max_value,
 display_order, is_system)
SELECT
    organization_id, 'cooling', 'cooling_degradation_factor', setting_value,
    'float', 'Коэффициент замедления',
    'Во сколько раз замедлять охлаждение',
    1.0, 3.0, 20, FALSE
FROM organization_settings
WHERE setting_key = 'cooling_degradation_factor'
    ON CONFLICT (organization_id, setting_key) DO NOTHING;

INSERT INTO app_settings
(organization_id, category, setting_key, setting_value,
 value_type, label, description, min_value, max_value,
 display_order, is_system)
SELECT
    organization_id, 'cooling', 'cooling_zone_capacity', setting_value,
    'int', 'Ёмкость зоны охлаждения',
    'Сколько реакторов могут охлаждаться одновременно',
    1, 10, 30, FALSE
FROM organization_settings
WHERE setting_key = 'cooling_zone_capacity'
    ON CONFLICT (organization_id, setting_key) DO NOTHING;


-- ==========================================
-- 2.4. CALENDAR
-- ==========================================
INSERT INTO app_settings
(organization_id, category, setting_key, setting_value,
 value_type, label, description, min_value, max_value,
 display_order, is_system)
SELECT
    organization_id, 'calendar', 'max_task_hours_for_calendar', '12.0'::jsonb,
        'float', 'Макс. длительность задачи (ч)',
    'Задачи длиннее — пропускаются в календарных ограничениях',
    1.0, 48.0, 10, FALSE
FROM organization_settings
WHERE setting_key = 'planning_start_date'
    ON CONFLICT (organization_id, setting_key) DO NOTHING;

INSERT INTO app_settings
(organization_id, category, setting_key, setting_value,
 value_type, label, description, min_value, max_value,
 display_order, is_system)
SELECT
    organization_id, 'calendar', 'max_fill_part_hours', '8.0'::jsonb,
        'float', 'Макс. длительность части слива (ч)',
    'Длинные LINE_FILL разбиваются на части по этой длительности',
    2.0, 12.0, 20, FALSE
FROM organization_settings
WHERE setting_key = 'planning_start_date'
    ON CONFLICT (organization_id, setting_key) DO NOTHING;


-- ==========================================
-- 2.5. LAB
-- ==========================================
INSERT INTO app_settings
(organization_id, category, setting_key, setting_value,
 value_type, label, description, display_order, is_system)
SELECT
    organization_id, 'lab', 'enable_lab_blocking', setting_value,
    'bool', 'Блокировка лабораторией',
    'Партия не участвует в планировании до одобрения',
    10, FALSE
FROM organization_settings
WHERE setting_key = 'enable_lab_blocking'
    ON CONFLICT (organization_id, setting_key) DO NOTHING;


-- ==========================================
-- 2.6. MATERIALS
-- ==========================================
INSERT INTO app_settings
(organization_id, category, setting_key, setting_value,
 value_type, label, description, display_order, is_system)
SELECT
    organization_id, 'materials', 'enable_material_constraints', setting_value,
    'bool', 'Учёт остатков сырья',
    'Advisor проверяет дефицит сырья',
    10, FALSE
FROM organization_settings
WHERE setting_key = 'enable_material_constraints'
    ON CONFLICT (organization_id, setting_key) DO NOTHING;


-- ==========================================
-- 2.7. CZ
-- ==========================================
INSERT INTO app_settings
(organization_id, category, setting_key, setting_value,
 value_type, label, description, display_order, is_system)
SELECT
    organization_id, 'cz', 'enable_cz_integration', setting_value,
    'bool', 'Интеграция с ЧЗ',
    'Приём сканов от камер ТС',
    10, FALSE
FROM organization_settings
WHERE setting_key = 'enable_cz_integration'
    ON CONFLICT (organization_id, setting_key) DO NOTHING;

INSERT INTO app_settings
(organization_id, category, setting_key, setting_value,
 value_type, label, description, min_value, max_value,
 display_order, is_system)
SELECT
    organization_id, 'cz', 'cz_completion_threshold', setting_value,
    'float', 'Порог завершения ЧЗ',
    'Доля от плана (0.0–1.0)',
    0.1, 1.0, 20, FALSE
FROM organization_settings
WHERE setting_key = 'cz_completion_threshold'
    ON CONFLICT (organization_id, setting_key) DO NOTHING;

INSERT INTO app_settings
(organization_id, category, setting_key, setting_value,
 value_type, label, description, display_order, is_system)
SELECT
    organization_id, 'cz', 'cz_api_key', setting_value,
    'str', 'API-ключ ЧЗ',
    'Заголовок X-CZ-Api-Key для вебхука',
    30, FALSE
FROM organization_settings
WHERE setting_key = 'cz_api_key'
    ON CONFLICT (organization_id, setting_key) DO NOTHING;

INSERT INTO app_settings
(organization_id, category, setting_key, setting_value,
 value_type, label, description, display_order, is_system)
SELECT
    organization_id, 'cz', 'enable_cz_auto_close', setting_value,
    'bool', 'Автозакрытие при ЧЗ',
    'Закрывать задачу слива при завершении маркировки',
    40, FALSE
FROM organization_settings
WHERE setting_key = 'enable_cz_auto_close'
    ON CONFLICT (organization_id, setting_key) DO NOTHING;


-- ==========================================
-- 2.8. RESOURCES
-- ==========================================
INSERT INTO app_settings
(organization_id, category, setting_key, setting_value,
 value_type, label, description, display_order, is_system)
SELECT
    organization_id, 'resources', 'enable_operator_pools', setting_value,
    'bool', 'Пулы операторов',
    'Учитывать ограничения по людям',
    10, FALSE
FROM organization_settings
WHERE setting_key = 'enable_operator_pools'
    ON CONFLICT (organization_id, setting_key) DO NOTHING;

INSERT INTO app_settings
(organization_id, category, setting_key, setting_value,
 value_type, label, description, display_order, is_system)
SELECT
    organization_id, 'resources', 'enable_manual_station', setting_value,
    'bool', 'Ручная станция',
    'Использовать LINE_3 (ручной слив)',
    20, FALSE
FROM organization_settings
WHERE setting_key = 'enable_manual_station'
    ON CONFLICT (organization_id, setting_key) DO NOTHING;


-- ==========================================
-- 2.9. FEATURES
-- ==========================================
INSERT INTO app_settings
(organization_id, category, setting_key, setting_value,
 value_type, label, description, display_order, is_system)
SELECT
    organization_id, 'features', 'enable_tank_routing', setting_value,
    'bool', 'Маршруты через танк',
    'Реактор → танк → линия',
    10, FALSE
FROM organization_settings
WHERE setting_key = 'enable_tank_routing'
    ON CONFLICT (organization_id, setting_key) DO NOTHING;

INSERT INTO app_settings
(organization_id, category, setting_key, setting_value,
 value_type, label, description, display_order, is_system)
SELECT
    organization_id, 'features', 'enable_shift_planning', setting_value,
    'bool', 'Сменное планирование',
    'Разбивка по сменам и РМ мастера',
    20, FALSE
FROM organization_settings
WHERE setting_key = 'enable_shift_planning'
    ON CONFLICT (organization_id, setting_key) DO NOTHING;

INSERT INTO app_settings
(organization_id, category, setting_key, setting_value,
 value_type, label, description, display_order, is_system)
SELECT
    organization_id, 'features', 'enable_rescheduling', setting_value,
    'bool', 'Перепланирование',
    'Пересчёт при изменениях',
    30, FALSE
FROM organization_settings
WHERE setting_key = 'enable_rescheduling'
    ON CONFLICT (organization_id, setting_key) DO NOTHING;

INSERT INTO app_settings
(organization_id, category, setting_key, setting_value,
 value_type, label, description, display_order, is_system)
SELECT
    organization_id, 'features', 'enable_advisor', setting_value,
    'bool', 'Advisor (подсказки)',
    'Анализ плана и подсказки',
    40, FALSE
FROM organization_settings
WHERE setting_key = 'enable_advisor'
    ON CONFLICT (organization_id, setting_key) DO NOTHING;

RAISE NOTICE 'Перенос настроек завершён';
END $$;


-- ==========================================
-- 3. ФИНАЛЬНАЯ ПРОВЕРКА
-- ==========================================
SELECT
    category,
    COUNT(*) AS settings_count
FROM app_settings
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
GROUP BY category
ORDER BY category;

SELECT
    category,
    setting_key,
    value_type,
    label,
    setting_value
FROM app_settings
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
  AND category IN ('shifts', 'planning')
ORDER BY category, display_order;

-- ==========================================
-- ФИКС: принудительно обновляем work_start_time и work_end_time
-- на случай, если они были испорчены или созданы с 00:00
-- ==========================================
UPDATE app_settings
SET setting_value = '"08:00"'::jsonb,
    updated_at = NOW()
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
  AND setting_key = 'work_start_time'
  AND (
    setting_value IS NULL
   OR setting_value = 'null'::jsonb
   OR setting_value = '"00:00"'::jsonb
   OR setting_value = '""'::jsonb
    );

UPDATE app_settings
SET setting_value = '"20:00"'::jsonb,
    updated_at = NOW()
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
  AND setting_key = 'work_end_time'
  AND (
    setting_value IS NULL
   OR setting_value = 'null'::jsonb
   OR setting_value = '"00:00"'::jsonb
   OR setting_value = '""'::jsonb
    );