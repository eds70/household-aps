-- ==========================================
-- HOTFIX ИТЕРАЦИИ 5: ДЕАКТИВАЦИЯ СТАРЫХ ВЕРСИЙ ПЛАНА
-- ==========================================
-- Проблема: saver.py из Итерации 3 не деактивирует старые версии
-- при создании новой. В результате накапливается N версий с
-- is_active = TRUE, и UI (Мастер смены, Гант) показывает задачи
-- из ВСЕХ версий — возникает визуальное задвоение.
--
-- Решение:
--   1. Деактивировать ВСЕ версии.
--   2. Активировать ТОЛЬКО самую свежую (по created_at).
--   3. (Опционально) Оставить только версии за последние N дней?
--      Пока не трогаем — просто деактивируем старые.
--
-- Миграция идемпотентна, можно применять повторно.
-- ==========================================

DO $$
DECLARE
v_org_id UUID := '00000000-0000-0000-0000-000000000001';
    v_latest_id UUID;
    v_total_versions INT;
    v_active_before INT;
    v_active_after INT;
BEGIN
    -- 1. Считаем, сколько версий ДО
SELECT COUNT(*) INTO v_total_versions
FROM schedule_version
WHERE organization_id = v_org_id;

SELECT COUNT(*) INTO v_active_before
FROM schedule_version
WHERE organization_id = v_org_id AND is_active = TRUE;

RAISE NOTICE 'Версий всего: %, активных до фикса: %', v_total_versions, v_active_before;

    -- 2. Находим самую свежую версию
SELECT id INTO v_latest_id
FROM schedule_version
WHERE organization_id = v_org_id
ORDER BY created_at DESC
    LIMIT 1;

IF v_latest_id IS NULL THEN
        RAISE NOTICE 'Нет версий для обработки';
        RETURN;
END IF;

    RAISE NOTICE 'Оставляем активной: %', v_latest_id;

    -- 3. Деактивируем ВСЕ версии
UPDATE schedule_version
SET is_active = FALSE
WHERE organization_id = v_org_id;

-- 4. Активируем только последнюю
UPDATE schedule_version
SET is_active = TRUE
WHERE id = v_latest_id;

-- 5. Считаем, сколько версий ПОСЛЕ
SELECT COUNT(*) INTO v_active_after
FROM schedule_version
WHERE organization_id = v_org_id AND is_active = TRUE;

RAISE NOTICE 'Активных после фикса: %', v_active_after;
END $$;

-- ==========================================
-- ФИНАЛЬНАЯ ПРОВЕРКА
-- ==========================================
SELECT
    COUNT(*) AS total_versions,
    COUNT(*) FILTER (WHERE is_active = TRUE) AS active_versions
FROM schedule_version
WHERE organization_id = '00000000-0000-0000-0000-000000000001';

-- Ожидаемо:
--   total_versions  | active_versions
--   ----------------+----------------
--             14   |               1

-- ==========================================
-- ДОПОЛНИТЕЛЬНАЯ ПРОВЕРКА: задачи в активной версии
-- ==========================================
SELECT
    sv.id::text AS version_id,
        sv.name,
    COUNT(st.id) AS task_count
FROM schedule_version sv
         LEFT JOIN scheduled_task st ON st.schedule_version_id = sv.id
WHERE sv.organization_id = '00000000-0000-0000-0000-000000000001'
  AND sv.is_active = TRUE
GROUP BY sv.id, sv.name;

-- Ожидаемо: одна строка с последней активной версией и ~282 задачами.