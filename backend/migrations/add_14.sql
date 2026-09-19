-- ==========================================
-- МИГРАЦИЯ 14: Флаг allow_weekend_work
-- ==========================================
-- Разрешает/запрещает работу в выходные (сб, вс).
--   - false (по умолчанию): постпроцессор сдвигает задачи с выходных.
--   - true: постпроцессор не применяется, задачи могут попадать на выходные.
--
-- Идемпотентна.
-- ==========================================

INSERT INTO app_settings
(organization_id, category, setting_key, setting_value,
 value_type, label, description, display_order, is_system)
VALUES
    (
        '00000000-0000-0000-0000-000000000001',
        'calendar',
        'allow_weekend_work',
        'false'::jsonb,
        'bool',
        'Работа в выходные',
        'Разрешить работу в субботу и воскресенье',
        5,
        FALSE
    )
    ON CONFLICT (organization_id, setting_key) DO NOTHING;

SELECT setting_key, setting_value, value_type, label
FROM app_settings
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
  AND setting_key = 'allow_weekend_work';