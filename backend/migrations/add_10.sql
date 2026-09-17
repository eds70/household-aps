-- ==========================================
-- МИГРАЦИЯ 10: ОХЛАЖДЕНИЕ С ДЕГРАДАЦИЕЙ (Итерация 7)
-- ==========================================
-- Добавляет:
--   1. Feature-флаг enable_cooling_degradation = true
--   2. Настройку cooling_degradation_factor = 1.3
--   3. Настройку cooling_zone_capacity = 2 (проверяем/дублируем)
--
-- Логика:
--   Если в зоне охлаждения работают 2 реакции одновременно,
--   каждая замедляется в 1.3 раза. Это нелинейная зависимость,
--   реализуется через дискретизацию (fast/slow режимы).
--
-- Идемпотентна: можно применять повторно.
-- ==========================================

-- ==========================================
-- 1. FEATURE-ФЛАГ
-- ==========================================
INSERT INTO organization_settings (organization_id, setting_key, setting_value, description) VALUES
    ('00000000-0000-0000-0000-000000000001',
     'enable_cooling_degradation',
     'true',
     'Охлаждение с деградацией — замедление при 2 параллельных реакторах (Итерация 7).')
    ON CONFLICT (organization_id, setting_key) DO UPDATE
                                                      SET setting_value = EXCLUDED.setting_value,
                                                      description = EXCLUDED.description;

-- ==========================================
-- 2. КОЭФФИЦИЕНТ ДЕГРАДАЦИИ
-- ==========================================
INSERT INTO organization_settings (organization_id, setting_key, setting_value, description) VALUES
    ('00000000-0000-0000-0000-000000000001',
     'cooling_degradation_factor',
     '1.3',
     'Во сколько раз замедляется охлаждение при 2 параллельных (Итерация 7).')
    ON CONFLICT (organization_id, setting_key) DO UPDATE
                                                      SET setting_value = EXCLUDED.setting_value,
                                                      description = EXCLUDED.description;

-- ==========================================
-- 3. CAPACITY ЗОНЫ ОХЛАЖДЕНИЯ (проверяем)
-- ==========================================
-- Убедимся, что capacity = 2 в resource_pool.
-- Если записи нет — создадим.
INSERT INTO resource_pool (organization_id, name, type, capacity, comment)
VALUES
    ('00000000-0000-0000-0000-000000000001',
     'Зона охлаждения',
     'COOLING_ZONE',
     2,
     'Максимум 2 реактора остывают одновременно. Итерация 7.')
    ON CONFLICT (organization_id, type) DO UPDATE
                                               SET capacity = EXCLUDED.capacity,
                                               comment = EXCLUDED.comment,
                                               updated_at = NOW();

-- ==========================================
-- ФИНАЛЬНАЯ ПРОВЕРКА
-- ==========================================
SELECT setting_key, setting_value
FROM organization_settings
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
  AND setting_key IN (
                      'enable_cooling_degradation',
                      'cooling_degradation_factor',
                      'cooling_zone_capacity'
    )
ORDER BY setting_key;

SELECT type, capacity
FROM resource_pool
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
  AND type = 'COOLING_ZONE';