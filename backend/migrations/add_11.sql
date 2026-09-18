-- ==========================================
-- МИГРАЦИЯ 11: ИНТЕГРАЦИЯ С ЧЕСТНЫМ ЗНАКОМ (Итерация 8)
-- ==========================================
-- Добавляет:
--   1. Поля в batch для учёта маркировки ЧЗ:
--      - cz_marked_qty     — промаркировано (штук)
--      - cz_last_scan_at   — последний скан
--      - cz_status         — NOT_APPLICABLE | PENDING | IN_PROGRESS | COMPLETED
--   2. Таблица cz_scan_log — журнал всех сканирований ЧЗ.
--   3. Feature-флаг enable_cz_integration = true.
--   4. Настройки: cz_completion_threshold, cz_api_key, enable_cz_auto_close.
--
-- Логика:
--   - Камеры технического зрения шлют POST /api/v1/cz/scan с API-ключом.
--   - Один код ЧЗ = одна бутылка (по умолчанию).
--   - Идемпотентность через UNIQUE (organization_id, cz_code).
--   - Порог завершения маркировки партии — 95% по умолчанию.
--
-- Идемпотентна: можно применять повторно.
-- ==========================================

-- ==========================================
-- 1. ПОЛЯ В BATCH
-- ==========================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'batch' AND column_name = 'cz_marked_qty'
    ) THEN
ALTER TABLE batch ADD COLUMN cz_marked_qty NUMERIC(12,3) DEFAULT 0;
COMMENT ON COLUMN batch.cz_marked_qty IS
            'Промаркировано ЧЗ (штук). Итерация 8.';
        RAISE NOTICE 'Колонка batch.cz_marked_qty добавлена';
ELSE
        RAISE NOTICE 'Колонка batch.cz_marked_qty уже существует';
END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'batch' AND column_name = 'cz_last_scan_at'
    ) THEN
ALTER TABLE batch ADD COLUMN cz_last_scan_at TIMESTAMPTZ;
COMMENT ON COLUMN batch.cz_last_scan_at IS
            'Время последнего сканирования ЧЗ. Итерация 8.';
        RAISE NOTICE 'Колонка batch.cz_last_scan_at добавлена';
ELSE
        RAISE NOTICE 'Колонка batch.cz_last_scan_at уже существует';
END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'batch' AND column_name = 'cz_status'
    ) THEN
ALTER TABLE batch ADD COLUMN cz_status VARCHAR(30) DEFAULT 'PENDING';
COMMENT ON COLUMN batch.cz_status IS
            'Статус маркировки ЧЗ: NOT_APPLICABLE | PENDING | IN_PROGRESS | COMPLETED. Итерация 8.';
        RAISE NOTICE 'Колонка batch.cz_status добавлена';
ELSE
        RAISE NOTICE 'Колонка batch.cz_status уже существует';
END IF;
END $$;

-- Индекс для быстрого поиска партий по статусу маркировки
CREATE INDEX IF NOT EXISTS idx_batch_cz_status
    ON batch(organization_id, cz_status)
    WHERE cz_status IS NOT NULL AND cz_status != 'NOT_APPLICABLE';

-- ==========================================
-- 2. ТАБЛИЦА CZ_SCAN_LOG
-- ==========================================
CREATE TABLE IF NOT EXISTS cz_scan_log (
                                           id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
    batch_id UUID REFERENCES batch(id) ON DELETE SET NULL,
    scheduled_task_id UUID REFERENCES scheduled_task(id) ON DELETE SET NULL,
    cz_code VARCHAR(200) NOT NULL,
    gtin VARCHAR(50),
    qty NUMERIC(12,3) DEFAULT 1,
    line_code VARCHAR(50),
    camera_id VARCHAR(50),
    scanned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    comment TEXT,
    -- Идемпотентность: один код ЧЗ — одна запись на организацию
    CONSTRAINT cz_scan_log_code_unique UNIQUE (organization_id, cz_code)
    );
COMMENT ON TABLE cz_scan_log IS
    'Журнал сканирований кодов Честного Знака. Итерация 8.';
COMMENT ON COLUMN cz_scan_log.cz_code IS
    'Полный код маркировки ЧЗ (DataMatrix).';
COMMENT ON COLUMN cz_scan_log.gtin IS
    'GTIN продукта (опционально).';
COMMENT ON COLUMN cz_scan_log.qty IS
    'Количество единиц в скане (обычно 1 — бутылка).';
COMMENT ON COLUMN cz_scan_log.line_code IS
    'Код линии розлива (LINE_1, LINE_2, ...) для fallback-сопоставления.';
COMMENT ON COLUMN cz_scan_log.camera_id IS
    'ID камеры технического зрения.';

-- Индексы
CREATE INDEX IF NOT EXISTS idx_cz_scan_batch
    ON cz_scan_log(batch_id)
    WHERE batch_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_cz_scan_task
    ON cz_scan_log(scheduled_task_id)
    WHERE scheduled_task_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_cz_scan_time
    ON cz_scan_log(organization_id, scanned_at DESC);

CREATE INDEX IF NOT EXISTS idx_cz_scan_unresolved
    ON cz_scan_log(organization_id)
    WHERE batch_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_cz_scan_camera
    ON cz_scan_log(organization_id, camera_id)
    WHERE camera_id IS NOT NULL;

-- ==========================================
-- 3. FEATURE-ФЛАГИ И НАСТРОЙКИ
-- ==========================================
INSERT INTO organization_settings (organization_id, setting_key, setting_value, description) VALUES
                                                                                                 ('00000000-0000-0000-0000-000000000001',
                                                                                                  'enable_cz_integration',
                                                                                                  'true',
                                                                                                  'Интеграция с Честным Знаком (Итерация 8).'),

                                                                                                 ('00000000-0000-0000-0000-000000000001',
                                                                                                  'cz_completion_threshold',
                                                                                                  '0.95',
                                                                                                  'Порог завершения маркировки партии (доля от плана, 0..1).'),

                                                                                                 ('00000000-0000-0000-0000-000000000001',
                                                                                                  'cz_api_key',
                                                                                                  '"dev-cz-api-key-change-in-production"',
                                                                                                  'API-ключ для вебхука от камер ЧЗ (заголовок X-CZ-Api-Key).'),

                                                                                                 ('00000000-0000-0000-0000-000000000001',
                                                                                                  'enable_cz_auto_close',
                                                                                                  'false',
                                                                                                  'Автоматически закрывать задачу слива при завершении маркировки.')
    ON CONFLICT (organization_id, setting_key) DO UPDATE
                                                      SET setting_value = EXCLUDED.setting_value,
                                                      description = EXCLUDED.description;

-- ==========================================
-- ФИНАЛЬНАЯ ПРОВЕРКА
-- ==========================================
SELECT 'batch (cz_status)' AS check_name, COUNT(*) AS rows
FROM batch WHERE organization_id = '00000000-0000-0000-0000-000000000001'
             AND cz_status IS NOT NULL
UNION ALL
SELECT 'cz_scan_log', COUNT(*) FROM cz_scan_log
UNION ALL
SELECT 'enable_cz_integration', COUNT(*) FROM organization_settings
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
  AND setting_key = 'enable_cz_integration'
  AND setting_value = 'true'::jsonb
UNION ALL
SELECT 'cz_completion_threshold', COUNT(*) FROM organization_settings
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
  AND setting_key = 'cz_completion_threshold';

-- Ожидаемо:
--   batch (cz_status):            28
--   cz_scan_log:                   0
--   enable_cz_integration:         1
--   cz_completion_threshold:       1