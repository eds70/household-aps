-- add_31_advisor_notes.sql
-- Итерация 26 (advisor):
--  - advisor_note — сохранённые выводы solver'а / календарной
--    постобработки для конкретной версии плана.
--  - schedule_version.has_advisor_notes — быстрая метка для
--    списка истории версий.

BEGIN;

-- 1. Флаг на версии плана
ALTER TABLE schedule_version
    ADD COLUMN IF NOT EXISTS has_advisor_notes BOOLEAN NOT NULL DEFAULT FALSE;

-- 2. Таблица заметок
CREATE TABLE IF NOT EXISTS advisor_note (
                                            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
    schedule_version_id UUID NOT NULL REFERENCES schedule_version(id) ON DELETE CASCADE,

    severity            VARCHAR(20)  NOT NULL,   -- 'INFO' | 'WARNING' | 'CRITICAL'
    code                VARCHAR(50)  NOT NULL,   -- 'OVER_HORIZON', 'SHIFTED_TASK', ...
    title               VARCHAR(200) NOT NULL,
    message             TEXT         NOT NULL,
    details             JSONB        NOT NULL DEFAULT '{}'::jsonb,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

CREATE INDEX IF NOT EXISTS idx_advisor_note_version
    ON advisor_note (schedule_version_id, severity, created_at DESC);

-- 3. Хелпер: отметить версию, если есть заметки
CREATE OR REPLACE FUNCTION update_schedule_version_advisor_flag()
RETURNS TRIGGER AS $$
BEGIN
UPDATE schedule_version
SET has_advisor_notes = TRUE
WHERE id = NEW.schedule_version_id;
RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_advisor_note_set_flag ON advisor_note;
CREATE TRIGGER trg_advisor_note_set_flag
    AFTER INSERT ON advisor_note
    FOR EACH ROW
    EXECUTE FUNCTION update_schedule_version_advisor_flag();

COMMIT;