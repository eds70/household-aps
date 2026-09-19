-- ==========================================
-- 15. ДЕМО-ДАННЫЕ: НАСТРОЙКИ ОРГАНИЗАЦИИ
-- ==========================================
-- Все настройки хранятся в app_settings (Итерация 11).
-- organization_settings — только для обратной совместимости,
-- заполняется ключевыми флагами для совместимости со старыми миграциями.
--
-- Читаются через settings_reader.py.
-- Метаданные (label, description, value_type, options) — в settings.py.
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
     'Начало рабочего дня', 'Начало первого рабочего интервала',
     40),
    ('00000000-0000-0000-0000-000000000001', 'shifts', 'work_end_time', '"20:00"', 'str',
     'Конец рабочего дня', 'Конец последнего рабочего интервала',
     50)
    ON CONFLICT (organization_id, setting_key) DO NOTHING;

-- ------------------------------------------
-- 15.4. КАЛЕНДАРЬ (Итерация 11, Шаг 6)
-- ------------------------------------------
INSERT INTO app_settings
(organization_id, category, setting_key, setting_value, value_type,
 label, description, display_order)
VALUES
    ('00000000-0000-0000-0000-000000000001', 'calendar', 'allow_weekend_work', 'false', 'bool',
     'Работа в выходные', 'Разрешить работу в субботу и воскресенье',
     5),
    ('00000000-0000-0000-0000-000000000001', 'calendar', 'max_task_hours_for_calendar', '12.0', 'float',
     'Макс. длительность задачи (ч)', 'Задачи длиннее — пропускаются в календарных ограничениях',
     10),
    ('00000000-0000-0000-0000-000000000001', 'calendar', 'max_fill_part_hours', '8.0', 'float',
     'Макс. длительность части слива (ч)', 'Длинные LINE_FILL разбиваются на части по этой длительности',
     20)
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
     'API-ключ ЧЗ', 'Заголовок X-CZ-Api-Key для вебхука',
     30),
    ('00000000-0000-0000-0000-000000000001', 'cz', 'enable_cz_auto_close', 'false', 'bool',
     'Автозакрытие при ЧЗ', 'Закрывать задачу слива при завершении маркировки',
     40)
    ON CONFLICT (organization_id, setting_key) DO NOTHING;

-- ------------------------------------------
-- 15.7. ОБРАТНАЯ СОВМЕСТИМОСТЬ: organization_settings
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
     'Горизонт планирования по умолчанию (устар., см. app_settings.horizon_hours)'),
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
-- ГОТОВО! Схема создана (v2.0.0).
-- ==========================================
-- Что дальше:
--   1. Применить seed_demo_data.sql (демо-данные).
--   2. python -m scripts.create_admin_user (создать админа).
--   3. Запустить backend и frontend.
--
-- Миграции add_12.sql, add_13.sql, add_14.sql — уже включены в эту схему.
-- Для существующих БД они остаются как история изменений.
-- ==========================================