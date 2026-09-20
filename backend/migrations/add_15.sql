-- ==========================================
-- МИГРАЦИЯ 15: Multi-objective оптимизация (Итерация 12)
-- ==========================================
-- Добавляет 5 весов в app_settings (категория optimization):
--   - weight_makespan       — общее время плана
--   - weight_setup          — переналадки
--   - weight_underload      — недогрузка реакторов
--   - weight_cooling_slow   — замедленное охлаждение
--   - weight_tardiness      — просрочка заказов
--
-- Все веса в [0, 1]. Хотя бы один должен быть > 0.
-- По умолчанию: только makespan = 1.0 (обратная совместимость).
--
-- Идемпотентна: можно применять повторно.
-- ==========================================

INSERT INTO app_settings
(organization_id, category, setting_key, setting_value, value_type,
 label, description, min_value, max_value, display_order)
VALUES
    ('00000000-0000-0000-0000-000000000001', 'optimization', 'weight_makespan', '1.0', 'float',
     'Вес: Makespan',
     'Приоритет минимизации общего времени плана (0 — отключено)',
     0.0, 1.0, 10),

    ('00000000-0000-0000-0000-000000000001', 'optimization', 'weight_setup', '0.0', 'float',
     'Вес: Переналадки',
     'Приоритет минимизации времени переналадок (setup)',
     0.0, 1.0, 20),

    ('00000000-0000-0000-0000-000000000001', 'optimization', 'weight_underload', '0.0', 'float',
     'Вес: Недогрузка реакторов',
     'Приоритет равномерной загрузки реакторов',
     0.0, 1.0, 30),

    ('00000000-0000-0000-0000-000000000001', 'optimization', 'weight_cooling_slow', '0.0', 'float',
     'Вес: Замедленное охлаждение',
     'Приоритет избегания замедленного охлаждения',
     0.0, 1.0, 40),

    ('00000000-0000-0000-0000-000000000001', 'optimization', 'weight_tardiness', '0.0', 'float',
     'Вес: Просрочка заказов',
     'Приоритет соблюдения due_date',
     0.0, 1.0, 50)
    ON CONFLICT (organization_id, setting_key) DO NOTHING;

-- ==========================================
-- ФИНАЛЬНАЯ ПРОВЕРКА
-- ==========================================
SELECT setting_key, setting_value, value_type, min_value, max_value
FROM app_settings
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
  AND category = 'optimization'
ORDER BY display_order;

-- Ожидаемый результат: 5 строк:
--   weight_makespan       | 1.0  | float | 0.0 | 1.0
--   weight_setup          | 0.0  | float | 0.0 | 1.0
--   weight_underload      | 0.0  | float | 0.0 | 1.0
--   weight_cooling_slow   | 0.0  | float | 0.0 | 1.0
--   weight_tardiness      | 0.0  | float | 0.0 | 1.0