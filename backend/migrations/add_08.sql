-- ==========================================
-- МИГРАЦИЯ 08: ЛАБОРАТОРИЯ И БЛОКИРОВКИ
-- ==========================================
-- Итерация 5. Добавляет:
--   1. Поле batch.is_lab_blocked — флаг блокировки партии лабораторией
--   2. Поле batch.lab_status — статус лабораторной проверки (PENDING_LAB | APPROVED | BLOCKED)
--   3. Таблица lab_analysis_log — журнал всех проверок лаборатории
--   4. Feature-флаг enable_lab_blocking = true
-- ==========================================

-- ==========================================
-- 1. BATCH: поля блокировки
-- ==========================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'batch' AND column_name = 'is_lab_blocked'
    ) THEN
ALTER TABLE batch ADD COLUMN is_lab_blocked BOOLEAN DEFAULT FALSE;
COMMENT ON COLUMN batch.is_lab_blocked IS
            'Партия заблокирована лабораторией до одобрения';
END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'batch' AND column_name = 'lab_status'
    ) THEN
ALTER TABLE batch ADD COLUMN lab_status VARCHAR(30) DEFAULT 'NOT_REQUIRED';
COMMENT ON COLUMN batch.lab_status IS
            'Статус лабораторной проверки: NOT_REQUIRED | PENDING_LAB | APPROVED | BLOCKED';
END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'batch' AND column_name = 'lab_block_reason'
    ) THEN
ALTER TABLE batch ADD COLUMN lab_block_reason TEXT;
COMMENT ON COLUMN batch.lab_block_reason IS
            'Причина блокировки партии лабораторией';
END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'batch' AND column_name = 'lab_blocked_at'
    ) THEN
ALTER TABLE batch ADD COLUMN lab_blocked_at TIMESTAMPTZ;
COMMENT ON COLUMN batch.lab_blocked_at IS
            'Когда партия была заблокирована лабораторией';
END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'batch' AND column_name = 'lab_blocked_by'
    ) THEN
ALTER TABLE batch ADD COLUMN lab_blocked_by UUID REFERENCES app_user(id) ON DELETE SET NULL;
COMMENT ON COLUMN batch.lab_blocked_by IS
            'Кто заблокировал партию (лаборант)';
END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_batch_lab_blocked
    ON batch(organization_id, is_lab_blocked)
    WHERE is_lab_blocked = TRUE;

CREATE INDEX IF NOT EXISTS idx_batch_lab_status
    ON batch(organization_id, lab_status)
    WHERE lab_status IS NOT NULL AND lab_status != 'NOT_REQUIRED';

-- ==========================================
-- 2. LAB_ANALYSIS_LOG: журнал проверок
-- ==========================================
CREATE TABLE IF NOT EXISTS lab_analysis_log (
                                                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
    batch_id UUID NOT NULL REFERENCES batch(id) ON DELETE CASCADE,
    scheduled_task_id UUID REFERENCES scheduled_task(id) ON DELETE SET NULL,
    action VARCHAR(30) NOT NULL,           -- REQUESTED | APPROVED | BLOCKED | UNBLOCKED | EXTENDED
    result VARCHAR(30),                    -- PASSED | FAILED | PENDING
    reason TEXT,
    performed_by UUID REFERENCES app_user(id) ON DELETE SET NULL,
    performed_at TIMESTAMPTZ DEFAULT NOW(),
    comment TEXT
    );
COMMENT ON TABLE lab_analysis_log IS
    'Журнал лабораторных проверок: запросы, одобрения, блокировки, разблокировки.';
COMMENT ON COLUMN lab_analysis_log.action IS
    'REQUESTED — запрошен анализ, APPROVED — одобрено, BLOCKED — заблокировано, UNBLOCKED — разблокировано, EXTENDED — продлено';

CREATE INDEX IF NOT EXISTS idx_lab_log_org ON lab_analysis_log(organization_id);
CREATE INDEX IF NOT EXISTS idx_lab_log_batch ON lab_analysis_log(batch_id);
CREATE INDEX IF NOT EXISTS idx_lab_log_performed_at ON lab_analysis_log(performed_at DESC);

-- ==========================================
-- 3. ВКЛЮЧАЕМ FEATURE-ФЛАГ
-- ==========================================
INSERT INTO organization_settings (organization_id, setting_key, setting_value, description) VALUES
    ('00000000-0000-0000-0000-000000000001', 'enable_lab_blocking',
     'true', 'Блокировка партии лабораторией (Итерация 5)')
    ON CONFLICT (organization_id, setting_key) DO UPDATE
                                                      SET setting_value = EXCLUDED.setting_value,
                                                      description = EXCLUDED.description;

-- ==========================================
-- 4. ЗАПОЛНЕНИЕ: все партии с операцией needs_lab получают PENDING_LAB
-- ==========================================
-- Находим партии, у которых ПФ имеет операцию needs_lab = TRUE,
-- и устанавливаем им lab_status = 'PENDING_LAB'
UPDATE batch b
SET lab_status = 'PENDING_LAB'
WHERE b.organization_id = '00000000-0000-0000-0000-000000000001'
  AND EXISTS (
    SELECT 1 FROM operation_template ot
    WHERE ot.product_id = b.product_id
      AND ot.needs_lab = TRUE
);

-- ==========================================
-- ФИНАЛЬНАЯ ПРОВЕРКА
-- ==========================================
SELECT 'batch (с is_lab_blocked)' AS check_name, COUNT(*) AS rows
FROM batch WHERE organization_id = '00000000-0000-0000-0000-000000000001'
             AND is_lab_blocked = FALSE
UNION ALL
SELECT 'batch (PENDING_LAB)', COUNT(*)
FROM batch WHERE organization_id = '00000000-0000-0000-0000-000000000001'
             AND lab_status = 'PENDING_LAB'
UNION ALL
SELECT 'lab_analysis_log', COUNT(*) FROM lab_analysis_log
UNION ALL
SELECT 'enable_lab_blocking', COUNT(*) FROM organization_settings
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
  AND setting_key = 'enable_lab_blocking'
  AND setting_value = 'true'::jsonb;

-- Ожидаемо:
--   batch (с is_lab_blocked):  28
--   batch (PENDING_LAB):       28
--   lab_analysis_log:          0
--   enable_lab_blocking:       1