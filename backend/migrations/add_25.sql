-- ==========================================
-- МИГРАЦИЯ 25: КОНТЕКСТНЫЕ ПОДСКАЗКИ (Итерация 15.2)
-- ==========================================
-- Таблица help_hint — короткие подсказки, привязанные к элементам UI.
--
-- Отличие от help_article:
--   - help_article — полные статьи (markdown, категории, поиск).
--   - help_hint    — короткая подсказка (2-3 предложения) + ссылка
--                    на статью для подробностей.
--
-- Связь hint → article через article_slug (опционально).
-- Если article_slug = NULL — подсказка самодостаточна.
--
-- Ключ подсказки (hint_key) — строка вида 'planning.recalc',
-- 'gantt.edit_mode', 'shift.lab_block'. На фронте используется
-- как <Hint id="planning.recalc"/>.
--
-- Идемпотентна: можно применять повторно.
-- ==========================================

BEGIN;

CREATE TABLE IF NOT EXISTS help_hint (
                                         id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organization(id) ON DELETE CASCADE,
    hint_key VARCHAR(100) NOT NULL,
    title VARCHAR(200) NOT NULL,
    body_md TEXT NOT NULL,
    article_slug VARCHAR(100),
    display_order INT NOT NULL DEFAULT 0,
    is_published BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (hint_key)
    );

COMMENT ON TABLE help_hint IS
    'Контекстные подсказки для элементов UI. Итерация 15.2.';

COMMENT ON COLUMN help_hint.hint_key IS
    'Уникальный ключ, используется на фронте: <Hint id="planning.recalc"/>';

COMMENT ON COLUMN help_hint.body_md IS
    'Markdown-тело подсказки (короткое, 2-3 предложения).';

COMMENT ON COLUMN help_hint.article_slug IS
    'Slug статьи справки для подробностей. NULL = подсказка самодостаточна.';

CREATE INDEX IF NOT EXISTS idx_help_hint_published
    ON help_hint(is_published, display_order);

CREATE INDEX IF NOT EXISTS idx_help_hint_org
    ON help_hint(organization_id)
    WHERE organization_id IS NOT NULL;

-- Триггер updated_at
CREATE OR REPLACE FUNCTION help_hint_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_help_hint_updated_at ON help_hint;
CREATE TRIGGER trg_help_hint_updated_at
    BEFORE UPDATE ON help_hint
    FOR EACH ROW
    EXECUTE FUNCTION help_hint_set_updated_at();

COMMIT;

-- ==========================================
-- ПРОВЕРКА
-- ==========================================
SELECT
    EXISTS (SELECT 1 FROM information_schema.tables
            WHERE table_name = 'help_hint') AS has_table,
    EXISTS (SELECT 1 FROM pg_indexes
            WHERE indexname = 'idx_help_hint_published') AS has_index,
    EXISTS (SELECT 1 FROM pg_trigger
            WHERE tgname = 'trg_help_hint_updated_at') AS has_trigger;