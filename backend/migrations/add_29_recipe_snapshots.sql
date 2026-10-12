-- ============================================================================
-- add_29_recipe_snapshots.sql
--
-- Снапшоты рецептов и их компонентов для версионирования плана.
-- Паттерн: как product_snapshot (составной PK (id, version_id),
-- FK version_id → schedule_version(id) ON DELETE CASCADE).
--
-- Отличия от "живых" таблиц:
--   - Убраны FK на product/material/organization — снапшот имутабелен,
--     а ссылочные записи могут быть удалены в живой БД.
--   - Добавлена колонка version_id.
-- ============================================================================

-- ---------- recipe_snapshot ----------
CREATE TABLE IF NOT EXISTS recipe_snapshot (
                                               id              UUID           NOT NULL,
                                               organization_id UUID,
                                               product_id      UUID           NOT NULL,
                                               base_volume_kg  NUMERIC(10,2)  NOT NULL,
    comment         TEXT,
    version_id      UUID           NOT NULL
    REFERENCES schedule_version(id) ON DELETE CASCADE,
    PRIMARY KEY (id, version_id)
    );

CREATE INDEX IF NOT EXISTS idx_recipe_snap_ver
    ON recipe_snapshot(version_id);

CREATE INDEX IF NOT EXISTS idx_recipe_snap_org_ver
    ON recipe_snapshot(organization_id, version_id);

-- ---------- recipe_item_snapshot ----------
CREATE TABLE IF NOT EXISTS recipe_item_snapshot (
                                                    id           UUID           NOT NULL,
                                                    recipe_id    UUID           NOT NULL,
                                                    material_id  UUID           NOT NULL,
                                                    qty_per_base NUMERIC(10,3)  NOT NULL,
    version_id   UUID           NOT NULL
    REFERENCES schedule_version(id) ON DELETE CASCADE,
    PRIMARY KEY (id, version_id)
    );

CREATE INDEX IF NOT EXISTS idx_recipe_item_snap_ver
    ON recipe_item_snapshot(version_id);

CREATE INDEX IF NOT EXISTS idx_recipe_item_snap_recipe_ver
    ON recipe_item_snapshot(recipe_id, version_id);

-- ============================================================================
-- Готово.
-- Проверка после применения:
--   \d recipe_snapshot
--   \d recipe_item_snapshot
-- ============================================================================