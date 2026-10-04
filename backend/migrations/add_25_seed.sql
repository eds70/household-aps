-- ==========================================
-- SEED 25: КОНТЕКСТНЫЕ ПОДСКАЗКИ (Итерация 15.2)
-- ==========================================
-- 8 стартовых подсказок для ключевых элементов UI.
-- Все — глобальные (organization_id = NULL).
--
-- Связь со статьями справки (add_24_seed_*):
--   planning.recalc       → planning-recalculate
--   planning.advisor      → planning-advisor
--   planning.plan_dirty   → planning-recalculate
--   gantt.edit_mode       → gantt-editing
--   gantt.brackets        → gantt-grouping
--   shift.lab_block       → lab-blocks
--   whatif.json           → whatif-overview
--   settings.system       → settings-app-vs-plan
--
-- Идемпотентна: ON CONFLICT (hint_key) DO NOTHING.
-- ==========================================

BEGIN;

INSERT INTO help_hint
(organization_id, hint_key, title, body_md, article_slug, display_order, is_published)
VALUES

-- ==========================================
-- 1. planning.recalc
-- ==========================================
(NULL,
 'planning.recalc',
 'Пересчёт плана',
 $md$Кнопка **«Пересчитать»** активна только при наличии несохранённых изменений. Solver работает 30–120 секунд.$md$,
 'planning-recalculate',
 10, TRUE),

-- ==========================================
-- 2. planning.advisor
-- ==========================================
(NULL,
 'planning.advisor',
 'Подсказки Advisor',
 $md$**Advisor** автоматически проверяет план на дефицит сырья, недогрузку реакторов и проблемы маршрутов. 🔴 критично, 🟡 риск, 🔵 инфо.$md$,
 'planning-advisor',
 20, TRUE),

-- ==========================================
-- 3. planning.plan_dirty
-- ==========================================
(NULL,
 'planning.plan_dirty',
 'Флаг «план изменён»',
 $md$Изменения справочников, заказов или задач помечают план **грязным**. Только тогда активна кнопка «Пересчитать».$md$,
 'planning-recalculate',
 30, TRUE),

-- ==========================================
-- 4. gantt.edit_mode
-- ==========================================
(NULL,
 'gantt.edit_mode',
 'Режим редактирования',
 $md$По умолчанию план открывается в режиме **🔒 Просмотр**. Кликните **✏️** в тулбаре, чтобы перетаскивать задачи и менять длительность.$md$,
 'gantt-editing',
 10, TRUE),

-- ==========================================
-- 5. gantt.brackets
-- ==========================================
(NULL,
 'gantt.brackets',
 'Скобки партий',
 $md$Цветные **скобки** охватывают все операции одной партии. Клик по скобке — подсветить партию. Работает только в режиме «По оборудованию».$md$,
 'gantt-grouping',
 20, TRUE),

-- ==========================================
-- 6. shift.lab_block
-- ==========================================
(NULL,
 'shift.lab_block',
 'Лабораторная блокировка',
 $md$Кликните **🔒**, чтобы заблокировать партию. Партия исключается из расписания до разблокировки. Доступно ролям LAB, MASTER, ADMIN.$md$,
 'lab-blocks',
 10, TRUE),

-- ==========================================
-- 7. whatif.json
-- ==========================================
(NULL,
 'whatif.json',
 'JSON изменений',
 $md$Опишите изменения в JSON: заказы, режим смен, capacity, календарь. Нажмите **шаблон** для быстрого старта.$md$,
 'whatif-overview',
 10, TRUE),

-- ==========================================
-- 8. settings.system
-- ==========================================
(NULL,
 'settings.system',
 'Системные настройки',
 $md$Настройки с иконкой **🔒** управляются программно (например, `shift_intervals`). Меняются через смену режима смен.$md$,
 'settings-app-vs-plan',
 10, TRUE)

    ON CONFLICT (hint_key) DO NOTHING;

COMMIT;

-- ==========================================
-- ПРОВЕРКА
-- ==========================================
SELECT
    COUNT(*) AS total_hints,
    COUNT(*) FILTER (WHERE article_slug IS NOT NULL) AS with_article
FROM help_hint
WHERE is_published = TRUE;

-- Ожидаемо: total_hints = 8, with_article = 8.