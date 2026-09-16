-- ==========================================
-- МИГРАЦИЯ 06: СМЕННОЕ ПЛАНИРОВАНИЕ И РМ МАСТЕРА
-- ==========================================
-- Итерация 3. Добавляет:
--   1. Таблица shift — смены (одна в день, 08:00-20:00)
--   2. Поля в scheduled_task: shift_id, actual_qty, material_load_at, status
--   3. Заполняет смены на сентябрь 2026 (по одной в день, кроме выходных)
--   4. Feature-флаг enable_shift_planning = true
-- ==========================================

-- ==========================================
-- 1. ТАБЛИЦА SHIFT
-- ==========================================
CREATE TABLE IF NOT EXISTS shift (
                                     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
    name VARCHAR(50) NOT NULL,
    starts_at TIMESTAMPTZ NOT NULL,
    ends_at TIMESTAMPTZ NOT NULL,
    is_working BOOLEAN DEFAULT TRUE,
    comment TEXT,
    CONSTRAINT chk_shift_dates CHECK (ends_at > starts_at)
    );
COMMENT ON TABLE shift IS 'Производственные смены (одна в день, 08:00-20:00)';

CREATE INDEX IF NOT EXISTS idx_shift_org_start ON shift(organization_id, starts_at);
CREATE INDEX IF NOT EXISTS idx_shift_org_date ON shift(organization_id, starts_at, ends_at);

-- ==========================================
-- 2. ПОЛЯ В SCHEDULED_TASK
-- ==========================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'scheduled_task' AND column_name = 'shift_id'
    ) THEN
ALTER TABLE scheduled_task ADD COLUMN shift_id UUID REFERENCES shift(id) ON DELETE SET NULL;
COMMENT ON COLUMN scheduled_task.shift_id IS 'Смена, к которой относится задача';
END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'scheduled_task' AND column_name = 'actual_qty'
    ) THEN
ALTER TABLE scheduled_task ADD COLUMN actual_qty NUMERIC(12,3);
COMMENT ON COLUMN scheduled_task.actual_qty IS 'Фактическое количество (для слива — бутылок)';
END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'scheduled_task' AND column_name = 'material_load_at'
    ) THEN
ALTER TABLE scheduled_task ADD COLUMN material_load_at TIMESTAMPTZ;
COMMENT ON COLUMN scheduled_task.material_load_at IS 'Когда мастер отметил загрузку сырья в реактор';
END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'scheduled_task' AND column_name = 'status'
    ) THEN
ALTER TABLE scheduled_task ADD COLUMN status VARCHAR(20) DEFAULT 'PLANNED';
COMMENT ON COLUMN scheduled_task.status IS 'PLANNED | IN_PROGRESS | DONE | CANCELLED';
END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_scheduled_task_shift ON scheduled_task(shift_id) WHERE shift_id IS NOT NULL;

-- ==========================================
-- 3. СМЕНЫ НА СЕНТЯБРЬ 2026
-- ==========================================
-- Одна смена в день: 08:00-20:00.
-- Выходные (сб-вс) — смены создаются, но is_working = FALSE.
-- Формат: 01.09.2026 - 30.09.2026

DO $$
DECLARE
v_org_id UUID := '00000000-0000-0000-0000-000000000001';
    v_date DATE := '2026-09-01';
    v_end_date DATE := '2026-09-30';
    v_starts_at TIMESTAMPTZ;
    v_ends_at TIMESTAMPTZ;
    v_dow INT;
    v_name VARCHAR(50);
    v_is_working BOOLEAN;
BEGIN
    -- Очищаем старые смены (идемпотентность)
DELETE FROM shift WHERE organization_id = v_org_id
                    AND starts_at >= '2026-09-01 00:00:00+03'
                    AND starts_at < '2026-10-01 00:00:00+03';

WHILE v_date <= v_end_date LOOP
        v_dow := EXTRACT(DOW FROM v_date);  -- 0=воскресенье, 6=суббота

        v_starts_at := (v_date::text || ' 08:00:00+03')::TIMESTAMPTZ;
        v_ends_at   := (v_date::text || ' 20:00:00+03')::TIMESTAMPTZ;

        v_is_working := (v_dow <> 0 AND v_dow <> 6);
        v_name := 'Смена ' || TO_CHAR(v_date, 'DD.MM.YYYY');

INSERT INTO shift (organization_id, name, starts_at, ends_at, is_working, comment)
VALUES (
           v_org_id,
           v_name,
           v_starts_at,
           v_ends_at,
           v_is_working,
           CASE WHEN v_is_working THEN 'Рабочая смена' ELSE 'Выходной' END
       );

v_date := v_date + 1;
END LOOP;

    RAISE NOTICE 'Создано смен: %',
        (SELECT COUNT(*) FROM shift WHERE organization_id = v_org_id
            AND starts_at >= '2026-09-01 00:00:00+03'
            AND starts_at < '2026-10-01 00:00:00+03');
END $$;

-- ==========================================
-- 4. FEATURE-ФЛАГ
-- ==========================================
INSERT INTO organization_settings (organization_id, setting_key, setting_value, description) VALUES
    ('00000000-0000-0000-0000-000000000001', 'enable_shift_planning',
     'true', 'Посменное планирование и РМ мастера (Итерация 3)')
    ON CONFLICT (organization_id, setting_key) DO UPDATE
                                                      SET setting_value = EXCLUDED.setting_value,
                                                      description = EXCLUDED.description;

-- ==========================================
-- ФИНАЛЬНАЯ ПРОВЕРКА
-- ==========================================
SELECT 'shift (сентябрь)' AS table_name, COUNT(*) AS rows
FROM shift WHERE organization_id = '00000000-0000-0000-0000-000000000001'
             AND starts_at >= '2026-09-01 00:00:00+03'
             AND starts_at < '2026-10-01 00:00:00+03'
UNION ALL
SELECT 'shift (рабочих)', COUNT(*)
FROM shift WHERE organization_id = '00000000-0000-0000-0000-000000000001'
             AND is_working = TRUE
             AND starts_at >= '2026-09-01 00:00:00+03'
             AND starts_at < '2026-10-01 00:00:00+03'
UNION ALL
SELECT 'enable_shift_planning', COUNT(*)
FROM organization_settings
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
  AND setting_key = 'enable_shift_planning'
  AND setting_value = 'true'::jsonb;

-- Ожидаемый результат:
--   shift (сентябрь):  30
--   shift (рабочих):   22
--   enable_shift_planning: 1