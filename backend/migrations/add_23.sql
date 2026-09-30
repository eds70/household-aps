-- ==========================================
-- МИГРАЦИЯ 23: АРХИВАЦИЯ ВЕРСИЙ ПЛАНОВ (Итерация 13.21)
-- ==========================================
-- Задача:
--   При пересчёте плана старая версия должна уходить в архив,
--   чтобы не засорять список «Истории планов».
--   Архивные версии можно разархивировать через UI.
--
-- Что делает миграция:
--   1. Добавляет колонку schedule_version.is_archived BOOLEAN DEFAULT FALSE.
--   2. Добавляет индекс idx_schedule_version_archived (для фильтрации).
--   3. Добавляет настройку app_settings.auto_archive_on_recalc (bool, default=true).
--   4. ОДНОРАЗОВО помечает все НЕактивные версии как архивные
--      (в БД накопилось 55 версий, из них 54 неактивные).
--
-- Идемпотентна: можно применять повторно.
-- ==========================================

BEGIN;

-- ==========================================
-- 1. КОЛОНКА is_archived
-- ==========================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'schedule_version'
          AND column_name = 'is_archived'
    ) THEN
ALTER TABLE schedule_version
    ADD COLUMN is_archived BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN schedule_version.is_archived IS
            'Архивная версия плана. Скрыта в UI по умолчанию. '
            'Разархивируется через PUT /api/v1/schedule/versions/{id}/unarchive. '
            'Итерация 13.21.';

        RAISE NOTICE 'Колонка schedule_version.is_archived добавлена';
ELSE
        RAISE NOTICE 'Колонка schedule_version.is_archived уже существует';
END IF;
END $$;

-- ==========================================
-- 2. ИНДЕКС ПО АРХИВНЫМ ВЕРСИЯМ
-- ==========================================
-- Partial-индекс: индексируем только НЕархивные (их обычно 1-2 на организацию).
-- Запросы "SELECT ... WHERE is_archived = FALSE" будут использовать этот индекс.
CREATE INDEX IF NOT EXISTS idx_schedule_version_archived
    ON schedule_version(organization_id, created_at DESC)
    WHERE is_archived = FALSE;

-- ==========================================
-- 3. НАСТРОЙКА auto_archive_on_recalc
-- ==========================================
-- Категория planning, тип bool, default=true.
-- Влияет на поведение кнопки «Пересчитать» на Ганте и в SchedulePage.
INSERT INTO app_settings
(organization_id, category, setting_key, setting_value, value_type,
 label, description, display_order)
VALUES
    (
        '00000000-0000-0000-0000-000000000001',
        'planning',
        'auto_archive_on_recalc',
        'true'::jsonb,
        'bool',
        'Архивировать старую версию после пересчёта',
        'Если включено — при пересчёте плана старая версия уходит в архив '
            '(скрывается из списка). Если выключено — старая версия остаётся '
            'в списке как обычная.',
        50
    )
    ON CONFLICT (organization_id, setting_key) DO NOTHING;

-- ==========================================
-- 4. ОДНОРАЗОВАЯ МИГРАЦИЯ: 54 старые версии → архив
-- ==========================================
-- Помечаем архивными все НЕактивные версии.
-- Активная (is_active = TRUE) остаётся в списке.
--
-- ВАЖНО: условие `is_archived = FALSE` защищает от повторного
-- применения миграции (не перезапишет разархивированные версии,
-- если пользователь их вернул).
DO $$
DECLARE
v_migrated INT;
    v_active INT;
BEGIN
    -- Считаем активные (для контроля)
SELECT COUNT(*) INTO v_active
FROM schedule_version
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
  AND is_active = TRUE;

-- Архивируем всё, что неактивно и ещё не в архиве
UPDATE schedule_version
SET is_archived = TRUE
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
  AND is_active = FALSE
  AND is_archived = FALSE;

GET DIAGNOSTICS v_migrated = ROW_COUNT;

RAISE NOTICE 'Одноразовая миграция: в архив переведено % версий. '
                 'Активных осталось: %.', v_migrated, v_active;
END $$;

COMMIT;

-- ==========================================
-- ФИНАЛЬНАЯ ПРОВЕРКА
-- ==========================================
SELECT
    COUNT(*)                                             AS total_versions,
    COUNT(*) FILTER (WHERE is_active = TRUE)             AS active_versions,
        COUNT(*) FILTER (WHERE is_archived = TRUE)           AS archived_versions,
        COUNT(*) FILTER (WHERE is_archived = FALSE)          AS visible_versions
FROM schedule_version
WHERE organization_id = '00000000-0000-0000-0000-000000000001';

-- Ожидаемый результат после миграции:
--   total_versions   | 55
--   active_versions  | 1
--   archived_versions| 54
--   visible_versions | 1

SELECT setting_key, setting_value, value_type, category
FROM app_settings
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
  AND setting_key = 'auto_archive_on_recalc';