-- Фикс work_start_time / work_end_time в app_settings
UPDATE app_settings
SET setting_value = '"08:00"'::jsonb,
    updated_at = NOW()
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
  AND setting_key = 'work_start_time';

UPDATE app_settings
SET setting_value = '"20:00"'::jsonb,
    updated_at = NOW()
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
  AND setting_key = 'work_end_time';

-- Проверка
SELECT setting_key, setting_value, updated_at
FROM app_settings
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
  AND setting_key IN ('work_start_time', 'work_end_time')
ORDER BY setting_key;