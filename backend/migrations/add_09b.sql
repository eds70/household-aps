-- ==========================================
-- МИГРАЦИЯ 09b: БАЗОВЫЕ ПУЛЫ (COOLING_ZONE, BOILER, LAB)
-- ==========================================
-- Дополняет миграцию add_09.sql.
-- Создаёт пулы, которые были в старых версиях schema.sql,
-- но могли отсутствовать в текущей БД.
--
-- Идемпотентна — можно применять повторно.
-- ==========================================

INSERT INTO resource_pool (organization_id, name, type, capacity, comment)
VALUES
    ('00000000-0000-0000-0000-000000000001',
     'Зона охлаждения',
     'COOLING_ZONE',
     2,
     'Максимум реакторов, остывающих одновременно.'),

    ('00000000-0000-0000-0000-000000000001',
     'Бойлер',
     'BOILER',
     1,
     'Один бойлер на весь цех.'),

    ('00000000-0000-0000-0000-000000000001',
     'Лаборатория',
     'LAB',
     1,
     'Один лаборант. Итерация 6.')
    ON CONFLICT (organization_id, type) DO UPDATE
                                               SET name = EXCLUDED.name,
                                               capacity = EXCLUDED.capacity,
                                               comment = EXCLUDED.comment;

-- ==========================================
-- ФИНАЛЬНАЯ ПРОВЕРКА
-- ==========================================
SELECT type, capacity
FROM resource_pool
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
ORDER BY
    CASE type
        WHEN 'REACTOR_OPERATOR' THEN 1
        WHEN 'LINE_OPERATOR' THEN 2
        WHEN 'MANUAL_OPERATOR' THEN 3
        WHEN 'COOLING_ZONE' THEN 4
        WHEN 'BOILER' THEN 5
        WHEN 'LAB' THEN 6
        ELSE 99
        END;