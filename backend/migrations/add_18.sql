-- ==========================================
-- МИГРАЦИЯ 18: ЖУРНАЛ ИЗМЕНЕНИЙ ОСТАТКОВ
-- ==========================================
-- Добавляет:
--   1. Таблицу material_stock_log — аудит всех изменений остатков.
--   2. Функцию-триггер log_material_stock_change().
--   3. Триггер на material_stock (AFTER INSERT/UPDATE/DELETE).
--   4. Индексы для быстрого поиска.
--
-- Триггер ловит ВСЕ изменения остатков — включая:
--   - прямые SQL-правки (source='SYSTEM');
--   - изменения через API (source='MANUAL', указывается через set_config);
--   - импорт из Excel (source='IMPORT', указывается через set_config).
--
-- Для передачи контекста пользователя используется session variable
-- app.current_user_id (устанавливается через set_config(..., true)).
--
-- Идемпотентна: можно применять повторно.
-- ==========================================

-- ==========================================
-- 1. ТАБЛИЦА ЖУРНАЛА
-- ==========================================
CREATE TABLE IF NOT EXISTS material_stock_log (
                                                  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
    material_id UUID NOT NULL REFERENCES material(id) ON DELETE CASCADE,
    action VARCHAR(20) NOT NULL,
    old_qty NUMERIC(12,3),
    new_qty NUMERIC(12,3),
    old_reserved_qty NUMERIC(12,3),
    new_reserved_qty NUMERIC(12,3),
    delta_qty NUMERIC(12,3),
    delta_reserved_qty NUMERIC(12,3),
    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    changed_by UUID REFERENCES app_user(id) ON DELETE SET NULL,
    source VARCHAR(30) DEFAULT 'SYSTEM',
    reason TEXT,
    comment TEXT
    );

COMMENT ON TABLE material_stock_log IS
    'Журнал изменений остатков материалов. Заполняется триггером автоматически.';
COMMENT ON COLUMN material_stock_log.action IS
    'INSERT | UPDATE | DELETE — что произошло с записью остатков.';
COMMENT ON COLUMN material_stock_log.source IS
    'MANUAL (из UI/API) | IMPORT (из Excel) | SYSTEM (прямой SQL/seed/миграция).';
COMMENT ON COLUMN material_stock_log.delta_qty IS
    'Изменение qty: new_qty - old_qty. Положительное — приход, отрицательное — расход.';

CREATE INDEX IF NOT EXISTS idx_material_stock_log_material
    ON material_stock_log(organization_id, material_id, changed_at DESC);

CREATE INDEX IF NOT EXISTS idx_material_stock_log_changed_at
    ON material_stock_log(organization_id, changed_at DESC);

CREATE INDEX IF NOT EXISTS idx_material_stock_log_source
    ON material_stock_log(organization_id, source, changed_at DESC);


-- ==========================================
-- 2. ФУНКЦИЯ-ТРИГГЕР
-- ==========================================
CREATE OR REPLACE FUNCTION log_material_stock_change()
RETURNS TRIGGER AS $$
DECLARE
v_user_id UUID;
    v_source  VARCHAR(30);
    v_reason  TEXT;
BEGIN
    -- Читаем session variable app.current_user_id (устанавливается через
    -- set_config('app.current_user_id', ..., true) в API-слое).
BEGIN
        v_user_id := NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid;
EXCEPTION WHEN OTHERS THEN
        v_user_id := NULL;
END;

BEGIN
        v_source := NULLIF(current_setting('app.change_source', TRUE), '');
EXCEPTION WHEN OTHERS THEN
        v_source := NULL;
END;

BEGIN
        v_reason := NULLIF(current_setting('app.change_reason', TRUE), '');
EXCEPTION WHEN OTHERS THEN
        v_reason := NULL;
END;

    IF v_source IS NULL THEN
        v_source := 'SYSTEM';
END IF;

    -- ---------------- INSERT ----------------
    IF TG_OP = 'INSERT' THEN
        INSERT INTO material_stock_log (
            organization_id, material_id, action,
            old_qty, new_qty, old_reserved_qty, new_reserved_qty,
            delta_qty, delta_reserved_qty,
            changed_by, source, reason, comment
        ) VALUES (
            NEW.organization_id, NEW.material_id, 'INSERT',
            NULL, NEW.qty,
            NULL, NEW.reserved_qty,
            COALESCE(NEW.qty, 0),
            COALESCE(NEW.reserved_qty, 0),
            v_user_id, v_source, v_reason,
            'Создание записи остатков'
        );
RETURN NEW;
END IF;

    -- ---------------- UPDATE ----------------
    IF TG_OP = 'UPDATE' THEN
        -- Логируем только если значения реально изменились
        IF (OLD.qty IS DISTINCT FROM NEW.qty)
           OR (OLD.reserved_qty IS DISTINCT FROM NEW.reserved_qty) THEN
            INSERT INTO material_stock_log (
                organization_id, material_id, action,
                old_qty, new_qty, old_reserved_qty, new_reserved_qty,
                delta_qty, delta_reserved_qty,
                changed_by, source, reason
            ) VALUES (
                NEW.organization_id, NEW.material_id, 'UPDATE',
                OLD.qty, NEW.qty,
                OLD.reserved_qty, NEW.reserved_qty,
                COALESCE(NEW.qty, 0) - COALESCE(OLD.qty, 0),
                COALESCE(NEW.reserved_qty, 0) - COALESCE(OLD.reserved_qty, 0),
                v_user_id, v_source, v_reason
            );
END IF;
RETURN NEW;
END IF;

    -- ---------------- DELETE ----------------
    IF TG_OP = 'DELETE' THEN
        -- Не логируем DELETE, если материал уже удалён (каскадный delete
        -- от `DELETE FROM material`). Иначе FK violation.
        IF NOT EXISTS (
            SELECT 1 FROM material WHERE id = OLD.material_id
        ) THEN
            RETURN OLD;
END IF;

INSERT INTO material_stock_log (
    organization_id, material_id, action,
    old_qty, new_qty, old_reserved_qty, new_reserved_qty,
    delta_qty, delta_reserved_qty,
    changed_by, source, reason, comment
) VALUES (
             OLD.organization_id, OLD.material_id, 'DELETE',
             OLD.qty, NULL,
             OLD.reserved_qty, NULL,
             -COALESCE(OLD.qty, 0),
             -COALESCE(OLD.reserved_qty, 0),
             v_user_id, v_source, v_reason,
             'Удаление записи остатков'
         );
RETURN OLD;
END IF;

RETURN NULL;
END;
$$ LANGUAGE plpgsql;


-- ==========================================
-- 3. ТРИГГЕР
-- ==========================================
DROP TRIGGER IF EXISTS trg_material_stock_log ON material_stock;
CREATE TRIGGER trg_material_stock_log
    AFTER INSERT OR UPDATE OR DELETE ON material_stock
    FOR EACH ROW EXECUTE FUNCTION log_material_stock_change();


-- ==========================================
-- 4. ФИНАЛЬНАЯ ПРОВЕРКА
-- ==========================================
SELECT 'material_stock'      AS table_name, COUNT(*) AS rows FROM material_stock
UNION ALL
SELECT 'material_stock_log',  COUNT(*) FROM material_stock_log
UNION ALL
SELECT 'triggers',            COUNT(*) FROM pg_trigger
WHERE tgname = 'trg_material_stock_log';

-- Ожидаемо: material_stock=11, material_stock_log=0, triggers=1