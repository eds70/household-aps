-- ==========================================
-- МИГРАЦИЯ 28: СОХРАНЁННЫЕ ПРЕДСТАВЛЕНИЯ АУДИТА (Итерация 16.2)
-- ==========================================
-- Задача:
--   Пользователь настраивает фильтры на странице «Аудит»
--   (источники, severity, даты, поиск, лимит) и хочет сохранить
--   эту комбинацию под именем, чтобы возвращаться к ней одной
--   кнопкой.
--
-- Что делает миграция:
--   1. Создаёт таблицу audit_saved_view.
--   2. Индексы по (organization_id, user_id) и (organization_id, is_default).
--   3. Триггер автообновления updated_at.
--
-- Идемпотентна: можно применять повторно.
-- ==========================================

BEGIN;

-- ==========================================
-- 1. ТАБЛИЦА audit_saved_view
-- ==========================================
CREATE TABLE IF NOT EXISTS audit_saved_view (
                                                id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES app_user(id)   ON DELETE CASCADE,

    name            VARCHAR(100) NOT NULL,
    comment         TEXT,

    -- Фильтры страницы «Аудит» в виде JSONB:
    -- {
    --   "sources":    ["STOCK", "RESCHEDULE"],   -- массив строк или null
    --   "severity":   "WARNING",                 -- строка или null
    --   "date_from":  "2026-10-01T00:00:00Z",    -- ISO-строка или null
    --   "date_to":    "2026-10-07T23:59:59Z",    -- ISO-строка или null
    --   "search":     "крем",                    -- строка или null
    --   "limit":      200                        -- int (10..2000)
    -- }
    filters         JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- Одно представление может быть «по умолчанию» — открывается
    -- автоматически при входе на /audit (если пользователь не пришёл
    -- по ссылке с явными query-параметрами).
    is_default      BOOLEAN NOT NULL DEFAULT FALSE,

    display_order   INT NOT NULL DEFAULT 0,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Имя представления уникально в рамках пользователя.
    CONSTRAINT audit_saved_view_user_name_unique
    UNIQUE (organization_id, user_id, name)
    );

COMMENT ON TABLE audit_saved_view IS
    'Сохранённые представления фильтров страницы «Аудит» (per-user). Итерация 16.2.';
COMMENT ON COLUMN audit_saved_view.user_id IS
    'Владелец представления. Каждый пользователь видит только свои.';
COMMENT ON COLUMN audit_saved_view.filters IS
    'JSONB с полями фильтров: sources, severity, date_from, date_to, search, limit.';
COMMENT ON COLUMN audit_saved_view.is_default IS
    'Если TRUE — представление открывается автоматически при входе на /audit '
    '(одно на пользователя; при установке нового — предыдущее снимается).';
COMMENT ON COLUMN audit_saved_view.display_order IS
    'Порядок сортировки в выпадающем списке (по возрастанию).';

-- ==========================================
-- 2. ИНДЕКСЫ
-- ==========================================
-- Основной сценарий: "покажи мои представления в моей организации".
CREATE INDEX IF NOT EXISTS idx_audit_saved_view_user
    ON audit_saved_view(organization_id, user_id, display_order, name);

-- Частичный индекс: быстро находим default-представление пользователя.
CREATE INDEX IF NOT EXISTS idx_audit_saved_view_default
    ON audit_saved_view(organization_id, user_id)
    WHERE is_default = TRUE;

-- ==========================================
-- 3. ТРИГГЕР updated_at
-- ==========================================
CREATE OR REPLACE FUNCTION audit_saved_view_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := NOW();
RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_audit_saved_view_updated_at ON audit_saved_view;
CREATE TRIGGER trg_audit_saved_view_updated_at
    BEFORE UPDATE ON audit_saved_view
    FOR EACH ROW
    EXECUTE FUNCTION audit_saved_view_set_updated_at();

COMMIT;

-- ==========================================
-- ФИНАЛЬНАЯ ПРОВЕРКА
-- ==========================================
SELECT
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'audit_saved_view'
ORDER BY ordinal_position;

-- Ожидаемо: 10 колонок — id, organization_id, user_id, name, comment,
-- filters, is_default, display_order, created_at, updated_at.

SELECT indexname
FROM pg_indexes
WHERE tablename = 'audit_saved_view'
ORDER BY indexname;

-- Ожидаемо: 4 индекса:
--   audit_saved_view_pkey                    (PK)
--   audit_saved_view_user_name_unique        (UNIQUE)
--   idx_audit_saved_view_user
--   idx_audit_saved_view_default

SELECT trigger_name, event_manipulation, action_timing
FROM information_schema.triggers
WHERE event_object_table = 'audit_saved_view';

-- Ожидаемо: trg_audit_saved_view_updated_at, UPDATE, BEFORE