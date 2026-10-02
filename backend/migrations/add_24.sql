-- ==========================================
-- МИГРАЦИЯ 24: ВСТРОЕННАЯ СПРАВКА (Итерация 15.1)
-- ==========================================
-- Таблица help_article — статьи встроенной справки.
--
-- Особенности:
--   - organization_id может быть NULL → статья глобальная
--     (одинаковая для всех организаций).
--   - content_md — markdown-контент (TEXT, не JSONB, чтобы
--     избежать проблем с экранированием).
--   - tags — JSONB-массив строк для поиска.
--   - slug — уникальный человекопонятный идентификатор
--     (используется в URL /help/{slug}).
--
-- Идемпотентна: можно применять повторно.
-- ==========================================

BEGIN;

CREATE TABLE IF NOT EXISTS help_article (
                                            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organization(id) ON DELETE CASCADE,
    slug VARCHAR(100) NOT NULL,
    title VARCHAR(200) NOT NULL,
    category VARCHAR(50) NOT NULL,
    content_md TEXT NOT NULL,
    tags JSONB NOT NULL DEFAULT '[]'::jsonb,
    display_order INT NOT NULL DEFAULT 0,
    is_published BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (slug)
    );

COMMENT ON TABLE help_article IS
    'Статьи встроенной справки. Итерация 15.1.';
COMMENT ON COLUMN help_article.organization_id IS
    'NULL = глобальная статья (одинаковая для всех организаций).';
COMMENT ON COLUMN help_article.slug IS
    'Человекопонятный идентификатор для URL: /help/{slug}.';
COMMENT ON COLUMN help_article.category IS
    'Категория для группировки: getting-started, planning, gantt, '
    'shift, lab, cz, whatif, settings.';
COMMENT ON COLUMN help_article.content_md IS
    'Markdown-контент статьи.';
COMMENT ON COLUMN help_article.tags IS
    'JSONB-массив тегов для поиска: ["гант", "drag", "задача"].';
COMMENT ON COLUMN help_article.display_order IS
    'Порядок сортировки внутри категории (меньше = выше).';

-- Индексы
CREATE INDEX IF NOT EXISTS idx_help_article_category
    ON help_article(category, display_order);

CREATE INDEX IF NOT EXISTS idx_help_article_published
    ON help_article(is_published, category, display_order);

-- GIN-индекс по тегам (для поиска)
CREATE INDEX IF NOT EXISTS idx_help_article_tags
    ON help_article USING GIN (tags);

-- Триггер обновления updated_at
CREATE OR REPLACE FUNCTION help_article_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_help_article_updated_at ON help_article;
CREATE TRIGGER trg_help_article_updated_at
    BEFORE UPDATE ON help_article
    FOR EACH ROW
    EXECUTE FUNCTION help_article_set_updated_at();

COMMIT;

-- ==========================================
-- ФИНАЛЬНАЯ ПРОВЕРКА
-- ==========================================
SELECT
    EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'help_article'
    ) AS has_table,
    EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE indexname = 'idx_help_article_category'
    ) AS has_category_idx,
    EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE indexname = 'idx_help_article_tags'
    ) AS has_tags_idx,
    EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'trg_help_article_updated_at'
    ) AS has_trigger;