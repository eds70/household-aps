# Changelog

Все значимые изменения проекта APS Production Scheduler документируются в этом файле.

Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/),
проект придерживается [Semantic Versioning](https://semver.org/lang/ru/).

## [Unreleased]

### Added
- Заготовка для Итерации 15.3: интерактивный туториал.

---

## [4.6.0] — 2026-10-04

Итерация 15.4 — FAQ и расширение базы знаний.

### Added

#### Итерация 15.4 — FAQ и расширение базы знаний

**Проблема:**
Встроенная справка (Итерация 15.1) содержит 15 статей, покрывающих
базовые сценарии. Но пользователи часто сталкиваются с **типовыми
проблемами** (Advisor-подсказки, зависший What-if, «сироты» ЧЗ,
задача не двигается), и не всегда понимают, что делать. Техническая
`TROUBLESHOOTING.md` — для разработчиков.

**Решение:**
Новая категория **FAQ** в справке с 15 статьями, построенными по
принципу **Симптом → Причина → Что делать**.

**1. Категория FAQ (Backend):**
- ✅ В `help.py`:
  - `CATEGORY_LABELS["faq"] = "FAQ"`.
  - `CATEGORY_ORDER` — `faq` добавлена последней.
- ✅ Frontend не меняется — `HelpPage` подхватывает новую категорию
  автоматически.

**2. Seed-миграции (15 статей в 3 файлах):**

**`add_26_seed_1.sql` — Планирование (5 статей):**
- ✅ `faq-plan-feasible-not-optimal` — План FEASIBLE vs OPTIMAL.
- ✅ `faq-task-not-movable` — Задача не двигается на Ганте.
- ✅ `faq-plan-is-empty` — План пуст (⚠).
- ✅ `faq-plan-settings-empty` — «Настройки плана не заполнены».
- ✅ `faq-material-shortage` — Не хватает сырья.

**`add_26_seed_2.sql` — Гант, смены, what-if, ЧЗ (5 статей):**
- ✅ `faq-move-pinned-task` — Закреплённая задача не двигается.
- ✅ `faq-old-version-not-archived` — Старая версия не архивируется.
- ✅ `faq-shift-mode-change` — После смены режима смен задачи
  потеряли привязку.
- ✅ `faq-whatif-running` — What-if завис в RUNNING.
- ✅ `faq-cz-orphan-scan` — Скан ЧЗ попал в «сироты».

**`add_26_seed_3.sql` — Лаборатория и Advisor (5 статей):**
- ✅ `faq-lab-blocked-batch` — Партия заблокирована лабораторией.
- ✅ `faq-route-mismatch` — Advisor: ROUTE_MISMATCH.
- ✅ `faq-cooling-degradation` — Advisor: COOLING_DEGRADATION.
- ✅ `faq-cz-incomplete` — Advisor: CZ_INCOMPLETE.
- ✅ `faq-underload` — Advisor: UNDERLOAD.

**3. Единый формат статьи:**
- ✅ **Категория** — FAQ.
- ✅ **Симптом** — что видит пользователь.
- ✅ **Причина** — почему так происходит.
- ✅ **Что делать** — варианты решения (по приоритету).
- ✅ **Проверка** — SQL-запросы для диагностики.
- ✅ **Связанные статьи** — ссылки на 2-3 других статьи.

**4. Тесты (+24, всего 678):**
- ✅ `test_help_faq.py` (24):
  - Категория FAQ в `help.py` (5).
  - Файлы миграций (3).
  - Содержимое seed-файлов (4).
  - 15 FAQ-статей (5).
  - Ссылки на статьи (3).
  - API структурные (3).
  - Sanity (2).

**Ключевые гарантии:**
- ✅ **15 статей** покрывают топ-15 проблем пользователей.
- ✅ **Единый формат** — Симптом → Причина → Что делать.
- ✅ **SQL-запросы** для диагностики в каждой статье.
- ✅ **Ссылки на статьи** — перекрёстная навигация.
- ✅ **Идемпотентность** — `ON CONFLICT (slug) DO NOTHING`.
- ✅ **Обратная совместимость** — API `/categories` возвращает `faq`
  как обычную категорию.

### Changed

- Версия проекта: `4.5.0` → `4.6.0`.
- `help.py` — `CATEGORY_LABELS` + `CATEGORY_ORDER` содержат `faq`.
- Total категорий справки: **8 → 9**.
- Total статей справки: **15 → 30**.

---

## [4.5.0] — 2026-10-02

Итерация 15.2 — контекстные подсказки.

### Added

#### Итерация 15.2 — Контекстные подсказки

**Проблема:**
Даже с встроенной справкой (Итерация 15.1) пользователь не всегда знает,
что делает конкретная кнопка или флаг. Приходится уходить в раздел «Помощь»,
искать статью, читать её — теряя контекст.

**Решение:**

**1. База данных (миграция `add_25.sql`):**
- ✅ Таблица `help_hint`:
  - `hint_key` (UNIQUE) — идентификатор вида `planning.recalc`.
  - `title`, `body_md` (TEXT) — заголовок и короткое markdown-тело.
  - `article_slug` (nullable) — ссылка на полную статью справки.
  - `display_order`, `is_published`.
  - `organization_id` (nullable — глобальные подсказки).
- ✅ Триггер `help_hint_set_updated_at`.
- ✅ Индексы: `idx_help_hint_published`, `idx_help_hint_org`.

**2. Seed-миграция (`add_25_seed.sql`):**
- ✅ 8 стартовых подсказок:
  - `planning.recalc`, `planning.advisor`, `planning.plan_dirty`
  - `gantt.edit_mode`, `gantt.brackets`
  - `shift.lab_block`
  - `whatif.json`
  - `settings.system`
- ✅ Все привязаны к статьям справки из `add_24_seed_*`.
- ✅ Идемпотентна (`ON CONFLICT (hint_key) DO NOTHING`).

**3. Backend:**
- ✅ Модуль `help_models.py` — новые Pydantic-модели:
  - `HelpHint`, `HelpHintsResponse`.
- ✅ Модуль `help.py` — новый эндпоинт:
  - `GET /api/v1/help/hints` — возвращает словарь `{hint_key: HelpHint}`.

**4. Frontend:**
- ✅ `HelpHintsContext.tsx` — глобальный кэш подсказок:
  - Загрузка один раз при монтировании приложения.
  - Методы `getHint()`, `useHint()`.
  - Тихий fail: если запрос упал — подсказки не блокируют UI.
- ✅ `Hint.tsx` — компонент иконки `?` с Popover:
  - Иконка `HelpOutlineIcon` 14/18px.
  - Markdown-рендер (react-markdown + remark-gfm).
  - Кнопка «Читать подробнее» — переход на `/help/{slug}`.
  - Возвращает `null`, если подсказки нет.
- ✅ `App.tsx` — провайдер `HelpHintsProvider` обёрнут вокруг `BrowserRouter`.
- ✅ `types/index.ts` — типы `HelpHint`, `HelpHintsResponse`.
- ✅ `api.ts` — `helpApi.getHints()`.
- ✅ Интеграция в 5 страниц (8 подсказок):
  - `SchedulePage.tsx`: planning.recalc, planning.advisor, planning.plan_dirty.
  - `GanttPage.tsx`: gantt.edit_mode, gantt.brackets.
  - `ShiftPage.tsx`: shift.lab_block.
  - `WhatIfPage.tsx`: whatif.json.
  - `PlanSettingsWizard.tsx`: settings.system.

**5. Тесты (+27, всего 654):**
- ✅ `test_help_hints.py` (27):
  - Pydantic-модели (8).
  - Эндпоинт `/hints` (5).
  - Миграция `add_25.sql` (7).
  - Seed-файл (3).
  - Sanity (4).

**Ключевые гарантии:**
- ✅ **Не уходя со страницы** — подсказка открывается в Popover.
- ✅ **Короткий текст** — 2-3 предложения, чтобы не отвлекать.
- ✅ **Ссылка на статью** — для тех, кому нужно подробнее.
- ✅ **Обратная совместимость** — если подсказки нет в БД, `<Hint/>` рендерит null.
- ✅ **Кэширование** — 1 запрос при загрузке приложения на все подсказки.
- ✅ **Не критично** — ошибка загрузки подсказок не ломает UI.

### Fixed

- **Итерация 15.2 (fix):** контекстные подсказки не отображались в нескольких
  местах UI.
  - `frontend/src/pages/SchedulePage.tsx` — добавлены 3 подсказки:
    `planning.recalc`, `planning.advisor`, `planning.plan_dirty`.
  - `frontend/src/components/gantt/GanttToolbar.tsx` — добавлена подсказка
    `planning.recalc` рядом с кнопкой «Пересчитать» (🔄).

### Changed

- Версия проекта: `4.4.0` → `4.5.0`.
- `help_models.py` — добавлены модели `HelpHint`, `HelpHintsResponse`.
- `help.py` — добавлен эндпоинт `GET /hints`.
- `App.tsx` — обёрнут в `HelpHintsProvider`.
- `types/index.ts` — типы для подсказок.
- `api.ts` — метод `helpApi.getHints()`.
- 5 страниц получили встроенные `<Hint/>`.

---

## [4.4.0] — 2026-10-02

Итерация 15.1 — встроенная справка пользователя.

### Added

#### Итерация 15.1 — Встроенная справка пользователя

**Проблема:**
Пользователь, впервые открывший систему, не понимает, что делать.
Документация — в `docs/*.md`, но она для разработчиков. Нужна
встроенная справка прямо в UI.

**Решение:**

**1. База данных (миграция `add_24.sql`):**
- ✅ Таблица `help_article`:
  - `slug` (UNIQUE) — идентификатор для URL.
  - `title`, `category`, `content_md` (TEXT).
  - `tags` (JSONB-массив).
  - `display_order`, `is_published`.
  - `organization_id` (nullable — глобальные статьи).
- ✅ Триггер `help_article_set_updated_at`.
- ✅ Индексы: `idx_help_article_category`, `idx_help_article_tags` (GIN).

**2. Seed-миграции (`add_24_seed_1/2/3.sql`):**
- ✅ 15 стартовых статей в 8 категориях.
- ✅ Категории: `getting-started` (2), `planning` (4), `gantt` (4),
  `shift` (1), `lab` (1), `cz` (1), `whatif` (1), `settings` (1).
- ✅ Идемпотентны (`ON CONFLICT (slug) DO NOTHING`).
- ✅ Markdown в dollar-quoted strings (`$md$...$md$`).

**3. Backend:**
- ✅ Модуль `help_models.py` — Pydantic-модели:
  - `HelpArticleListItem`, `HelpArticleResponse`.
  - `HelpCategoriesResponse`, `HelpCategoryResponse`.
  - `HelpArticlesListResponse`.
  - `HelpSearchHit`, `HelpSearchResponse`.
- ✅ Модуль `help.py` — 4 эндпоинта:
  - `GET /api/v1/help/articles` — список статей (с фильтром по категории).
  - `GET /api/v1/help/articles/{slug}` — одна статья.
  - `GET /api/v1/help/categories` — список категорий с количеством.
  - `GET /api/v1/help/search?q=...` — поиск по title / content / tags.
- ✅ Модуль `help_docs.py` — отдача `docs/*.md`:
  - `GET /api/v1/help/docs/{filename}`.
  - Защита от path traversal (`/`, `\`, `..`).
  - Ограничение размера 1 МБ.
  - Только `.md`.
- ✅ Подключение в `main.py`:
  - `from app.api.v1.help import router as help_router`
  - `from app.api.v1.help_docs import router as help_docs_router`
  - `{"name": "Справка"}` в `tags_metadata`.
  - `app.include_router(help_router)`
  - `app.include_router(help_docs_router)`

**4. Frontend:**
- ✅ `npm install react-markdown@^9.0.1 remark-gfm@^4.0.0`.
- ✅ `helpApi` в `api.ts` — 5 методов:
  - `listArticles(category?)`, `getArticle(slug)`, `listCategories()`,
    `search(q, limit)`, `getDocFile(filename)`.
- ✅ Типы `HelpArticle`, `HelpArticleListItem`, `HelpCategory`,
  `HelpCategoriesResponse`, `HelpArticlesListResponse`,
  `HelpSearchHit`, `HelpSearchResponse`, `HelpDocFileResponse`.
- ✅ `HelpSidebar.tsx` — левая панель:
  - Поиск с debounce 300 мс.
  - Категории в аккордеонах.
  - При активном поиске — список найденных статей с сниппетами.
- ✅ `HelpArticleView.tsx` — markdown-рендер:
  - `react-markdown` + `remark-gfm`.
  - Кастомные компоненты для таблиц, кода, цитат.
  - Внутренние ссылки `/help/slug` перехватываются и открывают
    статьи внутри приложения.
- ✅ `HelpPage.tsx` — страница:
  - Двухпанельный layout через `Allotment`.
  - Роуты `/help` (редирект на `/help/intro-overview`) и `/help/:slug`.
- ✅ `MainLayout.tsx` — пункт меню «Помощь» с иконкой `HelpOutlined`.
- ✅ `App.tsx` — 2 роута для `/help` и `/help/:slug`.

**5. Тесты (+36, всего 601 → 627 после 15.2):**
- ✅ `test_help.py` (36):
  - Pydantic-модели (7).
  - Константы категорий (3).
  - Хелперы `_parse_tags`, `_make_snippet` (8).
  - Структура модулей (4).
  - Безопасность `help_docs` (3).
  - Миграция `add_24.sql` (6).
  - Seed-файлы (3).
  - Регистрация в `main.py` (2).

**6. ADR:**
- ✅ `docs/adr/0005-help-system.md` — обоснование выбора
  markdown-статей в PostgreSQL.

**Ключевые гарантии:**
- ✅ **15 статей** покрывают 80% сценариев.
- ✅ **Поиск** работает по title, content, tags.
- ✅ **Markdown-рендер** с таблицами и кодом.
- ✅ **Внутренние ссылки** — переход между статьями.
- ✅ **Отдача `docs/*.md`** — техническая документация.
- ✅ **Обратная совместимость** — read-only эндпоинты.

### Changed

- Версия проекта: `4.3.0` → `4.4.0`.
- `main.py` — подключены `help_router`, `help_docs_router`.
- `MainLayout.tsx` — пункт меню «Помощь».
- `App.tsx` — роуты `/help`, `/help/:slug`.
- `api.ts` — модуль `helpApi` (5 методов).
- `types/index.ts` — 8 новых типов для справки.

---

## [4.3.0] — 2026-10-02

Итерация 14.2 — редактирование плана прямо на Ганте.

### Added

#### Итерация 14.2 — Редактирование плана прямо на Ганте

**Проблема:**
Если план был **открыт** (через кнопку 👁️ на странице «Планирование»),
диаграмма Ганта переходила в режим **readonly** (`🔒 Просмотр`).
Задачи **не перетаскивались**, длительность **не менялась**. Чтобы
что-то поправить — приходилось закрывать план, терять контекст и
пересчитывать заново.

**Решение:**

**1. Глобальный режим редактирования:**
- ✅ Новый стейт `localEditMode` в `PlanContext`:
  - `false` — readonly.
  - `true` — редактирование разрешено.
- ✅ Синхронизация с `currentVersionId`.
- ✅ `isReadOnly = !localEditMode` в `GanttPage`.

**2. Переключатель режима в тулбаре Ганта:**
- ✅ Компактный `ToggleButtonGroup` `🔒 / ✏️`.
- ✅ Активная кнопка — синяя (`#3498db`).

**3. Синхронизация иконки в шапке приложения:**
- ✅ `MainLayout` берёт `localEditMode` из `usePlan()`.
- ✅ Условный рендер чипа (🔒/✏️).

**4. Кнопка «Пересчитать» — доступна всегда:**
- ✅ Рендерится, если передан `onRecalculate`.
- ✅ Активна только при `planDirty === true`.

**5. Удалён дублирующий Chip с названием плана.**

**6. Фикс рендера скобок партий** — защита от отрицательной ширины.

**7. `useGanttTimeline` учитывает `localEditMode`.**

**8. `GanttPage` — ре-рендер Timeline при смене режима.**

### Changed

- Версия проекта: `4.2.0` → `4.3.0`.

### Fixed

- **Проблема:** при открытии плана задачи не перетаскивались.
- **Решение:** глобальный `localEditMode` + переключатель в тулбаре.
- **Проблема:** `<rect> attribute width: A negative value is not valid`.
- **Решение:** защита от отрицательной ширины в `drawBatchBrackets`.

---

## [4.2.0] — 2026-09-29

Итерация 13.21 — архивация версий планов.

### Added

- Поле `schedule_version.is_archived`.
- Partial-индекс `idx_schedule_version_archived`.
- Настройка `auto_archive_on_recalc`.
- `ScheduleSaver._archive_version`, `_check_version_usage`.
- `RescheduleRequest.replace_version_id`.
- `PUT /api/v1/schedule/versions/{id}/unarchive`.
- UI: Tree Data в «Истории планов», чекбокс «Показать архивные».
- Снекбар после пересчёта в `GanttPage`.

**Тесты (+28, всего 563):** `test_schedule_versions_archive.py`.

---

## [4.1.2] — 2026-09-29

Итерация 13.20 — `RecalcProgressDialog`.

---

## [4.1.1] — 2026-09-25

Итерация 13.15 — снапшоты при создании плана.

### Added

- Модуль `snapshot.py` — `snapshot_all_catalogs`.
- `POST /versions` заполняет снапшоты.
- `has_snapshot` в ответах API.
- Индикация ⚠ в UI для планов без снапшотов.

**Тесты (+43, всего 535).**

---

## [4.1.0] — 2026-09-25

Итерации 13.14 и 13.14.1 — `plan_settings`.

### Added

- Таблица `plan_settings` (миграция `add_21.sql`).
- Триггер `copy_app_settings_to_plan`.
- `DataLoader(version_id=...)`, `ProductionScheduler(version_id=...)`.
- `settings_reader.py` — 3 функции с `version_id`.
- API `/api/v1/plan-settings` — 3 эндпоинта.
- `PlanSettingsWizard.tsx` — 9 шагов.

**Тесты (+171, всего 492).**

---

## [4.0.0] — 2026-09-24

Итерации 12 и 13.3.

### Added

- **Multi-objective** — модуль `optimization.py`, 5 компонентов.
- **What-if сценарии** — `whatif.py`, таблица `whatif_scenario`.
- **Аудит** — `/api/v1/audit`, `AuditPage.tsx`.

---

## [3.0.0]

Итерации 5–11.

### Added

- Лаборатория, люди как ресурс, охлаждение, ЧЗ, рефакторинг,
  календарная постобработка, режимы смен, `app_settings`.

---

## [2.0.0]

Итерации 2–4.

### Added

- Материальные ограничения и Advisor, сменное планирование,
  перепланирование.

---

## [1.0.0]

Итерации 0–1.

### Added

- Фундамент, цепочки рабочих центров.

---

## Типы изменений

- **Added** — новая функциональность.
- **Changed** — изменения в существующей функциональности.
- **Deprecated** — функциональность, которая будет удалена.
- **Removed** — удалённая функциональность.
- **Fixed** — исправления багов.
- **Security** — исправления уязвимостей.

---

## Ссылки

- [README.md](README.md) — основная документация.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — архитектура.
- [docs/ROADMAP.md](docs/ROADMAP.md) — план развития.
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) — руководство разработчика.
- [CONTRIBUTING.md](CONTRIBUTING.md) — как внести вклад.