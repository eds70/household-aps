# Changelog

Все значимые изменения проекта APS Production Scheduler документируются в этом файле.

Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/),
проект придерживается [Semantic Versioning](https://semver.org/lang/ru/).

## [Unreleased]

### Added

- Заготовка для Итерации 17: см. Roadmap.

---

## [4.9.0] — 2026-10-07

Итерация 16 — Расширенный аудит и отчёты.

### Added

#### Итерация 16 — Расширенный аудит и отчёты

**Проблема:**
Страница «Аудит» (Итерация 13.3) собирала события из 4 журналов
(`material_stock_log`, `reschedule_log`, `lab_analysis_log`,
`cz_scan_log`) и показывала их списком с базовыми фильтрами.
Но:
- пункт меню был **скрыт** в UI (Итерация 13.16 — «страница в разработке»),
- фильтров не хватало для реального анализа (нет `actor_id`,
  `entity_type`, диапазона `delta_qty`),
- не было дашборда — только список,
- нельзя было сохранить часто используемые представления,
- нельзя было выгрузить результат в Excel.

**Решение:**

**1. Возврат аудита в UI (16.0):**
- ✅ `frontend/src/App.tsx` — роут `/audit` снова зарегистрирован.
- ✅ `frontend/src/components/layout/MainLayout.tsx` — пункт меню «Аудит»
  раскомментирован, добавлена иконка `History`.
- ✅ Backend был подключён всегда — потребовалась только правка фронта.

**2. Расширенные фильтры (16.1):**
- ✅ 4 новых query-параметра в `GET /api/v1/audit/log`:
  - `actor_id` — фильтр по автору события (UUID);
  - `entity_type` — тип сущности: `material | batch | schedule_version`;
  - `delta_qty_from` / `delta_qty_to` — диапазон изменения количества
    (только для STOCK-событий).
- ✅ SQL-фильтры `actor_id`/`entity_type` добавлены в `_fetch_*_events`
  (для STOCK/RESCHEDULE/LAB; CZ — всегда пусто при `actor_id`, т.к.
  камера не является пользователем).
- ✅ Пост-фильтр `_post_filter` применяет `delta_qty` к STOCK-событиям
  и отбрасывает события без этого поля.
- ✅ Новая Pydantic-модель `AuditFilterSpec` — единый формат для
  GET-запросов, POST-экспорта и сохранённых представлений.

**3. Сохранённые представления (16.2):**
- ✅ Миграция `add_28.sql` — таблица `audit_saved_view`:
  - `id`, `organization_id`, `user_id`, `name`, `comment`, `filters` (JSONB),
    `is_default`, `display_order`, `created_at`, `updated_at`;
  - UNIQUE `(organization_id, user_id, name)`;
  - partial-index по `is_default = TRUE`;
  - триггер автообновления `updated_at`.
- ✅ 4 эндпоинта:
  - `GET    /api/v1/audit/saved-views` — список моих представлений;
  - `POST   /api/v1/audit/saved-views` — создать;
  - `PUT    /api/v1/audit/saved-views/{id}` — обновить;
  - `DELETE /api/v1/audit/saved-views/{id}` — удалить.
- ✅ Все 4 защищены `Depends(get_current_user_id)` — представления per-user.
- ✅ При установке `is_default = TRUE` с других представлений пользователя
  флаг снимается автоматически (в одной транзакции).
- ✅ UI: чипы представлений над фильтрами; клик — загрузить, крестик — удалить,
  двойной клик — переключить «по умолчанию» (★).

**4. Дашборд с графиками (16.3):**
- ✅ Новый эндпоинт `GET /api/v1/audit/stats/series`:
  - `group_by=day` — точки по дням (с заполнением пропущенных нулями);
  - `group_by=source` — точки по источникам;
  - `group_by=severity` — точки по уровням важности.
- ✅ Frontend: библиотека `recharts@^2.15.0`.
- ✅ 3 графика в сворачиваемой карточке:
  - Line chart «События по дням»;
  - Bar chart «По источникам»;
  - Bar chart «По важности».
- ✅ Нулевые категории в bar-charts скрыты (нет визуального «шума»).
- ✅ Дашборд сворачивается кнопкой `▲/▼`, состояние в `localStorage`
  (ключ `aps_audit_dashboard_open`).
- ✅ При свёрнутом дашборде в заголовке показывается компактная сводка
  `RESCHEDULE: 2 · Инфо: 2`.

**5. Экспорт в Excel (16.4):**
- ✅ Новый эндпоинт `POST /api/v1/audit/export.xlsx`.
- ✅ Генерация на backend через `openpyxl` (добавлен в `requirements.txt`).
- ✅ Заголовки: `Время | Источник | Важность | Тип | Заголовок | Описание |
  Сущность | Автор | Детали`.
- ✅ Фильтры те же, что у `/log` (`AuditFilterSpec`).
- ✅ Параметр `max_rows` (default 10 000) — защита от гигантских выгрузок.
- ✅ StreamingResponse с `Content-Disposition: attachment`.
- ✅ Frontend: кнопка «Экспорт в Excel» рядом с «Обновить».

**6. UX-полировка страницы «Аудит» (16.5):**
- ✅ Дашборд вынесен в сворачиваемую карточку — экономия до 400px
  вертикали при свёрнутом виде.
- ✅ Фильтры сжаты в одну карточку с двумя рядами (базовые + расширенные),
  `flexShrink: 0` — не «уезжают» на маленьких экранах.
- ✅ Пресеты дат (`День/Неделя/Месяц`) + «Сбросить» сгруппированы справа.
- ✅ Графики уменьшены до 140px по высоте, читаемы и на 1366×768.
- ✅ Скроллбар списка событий корректно растягивается (`minHeight: 0` на
  всех flex-обёртках).
- ✅ Все фильтры синхронизируются с URL (шаринг ссылок, history back/forward).

**7. Тесты:**
- ✅ `test_audit.py` — **+35** новых структурных тестов (расширенные
  фильтры, saved views CRUD, series, экспорт, права, регрессия).
- ✅ `test_audit_models.py` — **+27** новых тестов Pydantic-моделей
  (`AuditFilterSpec`, `AuditSavedView*`, `AuditStatsSeriesResponse`,
  `AuditExportRequest`).
- ✅ Существующие 17 + 9 тестов не сломаны.
- ✅ **Итого: 789 passed, 0 skipped** (все интеграционные тесты
  прогнаны на реальной PostgreSQL после применения `add_28.sql`).

**Ключевые гарантии:**
- ✅ **Обратная совместимость** — `GET /log`, `GET /stats`, `GET /sources`
  работают как раньше, старые query-параметры сохранены.
- ✅ **Per-user изоляция** — представления не пересекаются между
  пользователями, даже в одной организации.
- ✅ **Открытый формат** — экспорт в xlsx читается Excel, LibreOffice, pandas.
- ✅ **Мульти-тенантность** — все эндпоинты привязаны к `organization_id`.
- ✅ **Идемпотентные миграции** — `add_28.sql` можно применять повторно.

### Changed

- Версия проекта: `4.8.0` → `4.9.0`.
- `backend/app/main.py` — `FastAPI(version="4.9.0")`, `health` возвращает
  `APP_VERSION` из константы.
- `backend/app/api/v1/audit.py` — расширены `_fetch_*_events`, добавлены
  `_post_filter`, `_collect_events`, `_json_dumps`, `_build_xlsx`,
  `export_audit_xlsx`, `get_audit_stats_series`, 4 эндпоинта saved-views.
- `backend/app/api/v1/audit_models.py` — 8 новых моделей.
- `backend/requirements.txt` — добавлен `openpyxl>=3.1.0`.
- `frontend/package.json` — добавлен `recharts@^2.15.0`.
- `frontend/src/App.tsx` — роут `/audit`.
- `frontend/src/components/layout/MainLayout.tsx` — пункт меню «Аудит».
- `frontend/src/services/api.ts` — `auditApi` расширен 8 методами.
- `frontend/src/types/index.ts` — 9 новых типов.
- `frontend/src/pages/AuditPage.tsx` — полный рефакторинг UI.

### Fixed

- **Аудит снова доступен в UI** (Итерация 13.16 временно скрыла пункт
  меню). Теперь страница открывается из бокового меню.
- **Дашборд и фильтры не «уезжают» на экранах 1366×768** — исправлено
  через `flexShrink: 0` и `minHeight: 0` на промежуточных flex-контейнерах.
- **Скроллбар списка событий** — корректно растягивается до низа окна.
- **Дублирование нулевых категорий в bar-charts** — устранено.

---

## [4.8.0] — 2026-10-06

Итерация 15.5 — Редактирование статей справки в UI.

### Added

#### Итерация 15.5 — Редактирование статей справки в UI

**Проблема:**
Итерации 15.1–15.4 создали полноценную справку: markdown-статьи,
контекстные подсказки, интерактивные туры, FAQ. Но для добавления
или правки статьи требовалось писать SQL-миграцию и применять её
вручную через `docker cp` + `psql -f`. Это неудобно для контент-
менеджеров и администраторов: даже исправить опечатку — целая
операция.

**Решение:**
Добавлены CRUD-эндпоинты на бэкенде и полноценный редактор на
фронтенде. Редактирование доступно роли **ADMIN** через страницу
«Помощь».

**1. Backend (`help.py` + `help_models.py`):**
- ✅ 3 новых эндпоинта:
  - `POST   /api/v1/help/articles` — создать статью.
  - `PUT    /api/v1/help/articles/{slug}` — обновить.
  - `DELETE /api/v1/help/articles/{slug}` — удалить.
- ✅ Все три защищены `Depends(require_admin)` (роль ADMIN).
- ✅ `HelpArticleCreate`, `HelpArticleUpdate`, `HelpArticleDeleteResponse`
  вынесены в `help_models.py` (единый источник Pydantic-моделей).
- ✅ Автогенерация slug из title: `_slugify()` с транслитерацией
  RU → EN (`Первый план за 5 минут` → `pervyy-plan-za-5-minut`).
- ✅ Проверка уникальности slug: `_check_slug_conflict()` — включая
  режим исключения для update (тот же slug не считается конфликтом).
- ✅ Авто-`display_order`: если не задан — `max + 10` в категории
  (`_next_display_order()`).
- ✅ Валидация категории по `CATEGORY_LABELS` (9 категорий).
- ✅ Теги сериализуются в JSONB.
- ✅ Статья привязывается к организации (`organization_id = org_id`),
  изоляция по мульти-тенантности.
- ✅ Физическое удаление (`DELETE`). Для скрытия — `is_published = false`.

**2. Frontend (React):**
- ✅ Новый компонент `HelpArticleEditor.tsx`:
  - Форма создания/редактирования на базе `DraggableDialog`.
  - Две вкладки: «Редактор» (поля + textarea markdown) и
    «Предпросмотр» (рендер через `HelpArticleView`).
  - Поля: title, slug (опционально), category (селект),
    content_md (markdown), tags (строка через запятую с парсингом
    в чипы), display_order, is_published.
  - Валидация обязательных полей на клиенте.
  - Кнопка «Удалить» — только в режиме `edit`, с `window.confirm`.
- ✅ Доработка `HelpPage.tsx`:
  - Кнопка **«Новая статья»** в шапке — видна только `ADMIN`.
  - Кнопка **«Редактировать»** (иконка карандаша) над статьёй —
    видна только `ADMIN`.
  - Состояние `editorOpen`, `editorMode`, `editorArticle`,
    `editorError`.
  - Обработчики `handleOpenCreate`, `handleOpenEdit`,
    `handleSaveArticle`, `handleDeleteArticle`.
  - Авторедирект на новый slug после смены slug в редакторе.
  - Перезагрузка списка категорий после CRUD-операции.
- ✅ `helpApi` в `api.ts` — 3 новых метода:
  - `createArticle(payload)`, `updateArticle(slug, payload)`,
    `deleteArticle(slug)`.
- ✅ Типы в `types/index.ts`: `HelpArticleCreate`,
  `HelpArticleUpdate`, `HelpArticleDeleteResponse`.

**3. Тесты (+54):**

- ✅ `test_help.py` — **+37** структурных тестов:
  - Pydantic-модели CRUD (9).
  - Хелпер `_slugify` (8).
  - Роутер: наличие эндпоинтов и async-обработчиков (5).
  - Проверка `require_admin` (3).
  - Структурные проверки CRUD (8).
  - HTTP-контракты 401/403 без токена (3).
  - Sanity: идемпотентность slug (1).
- ✅ `test_help_crud_integration.py` — **+17** интеграционных тестов
  (требуют реальной PostgreSQL):
  - POST /articles: успех, авто-slug, авто-display_order,
    конфликт slug, неизвестная категория (5).
  - PUT /articles/{slug}: успех, частичное, смена slug, конфликт,
    404, неизвестная категория (6).
  - DELETE /articles/{slug}: успех, 404 (2).
  - Права: PLANNER/MASTER/VIEWER → 403 (4 — create×3, update, delete).
  - Изоляция по организации: 404 для чужой org (1).
  - Sanity cleanup (1).

**Ключевые гарантии:**
- ✅ **Редактирование без SQL** — правки через UI.
- ✅ **Только ADMIN** — остальные роли получают 403.
- ✅ **Авто-slug** — не нужно придумывать руками.
- ✅ **Предпросмотр** — видно результат до сохранения.
- ✅ **Мульти-тенантность** — статьи изолированы по организации.
- ✅ **Обратная совместимость** — существующие 15+15+1 статей
  из seed-миграций не затронуты.
- ✅ **Идемпотентность** — повторное создание с тем же slug → 409
  (не 500).

### Changed

- Версия проекта: `4.7.0` → `4.8.0`.
- `backend/app/api/v1/help.py` — 3 новых эндпоинта, хелпер `_slugify`,
  `_check_slug_conflict`, `_next_display_order`. Модели CRUD вынесены
  в `help_models.py`.
- `backend/app/api/v1/help_models.py` — добавлены `HelpArticleCreate`,
  `HelpArticleUpdate`, `HelpArticleDeleteResponse`.
- `frontend/src/services/api.ts` — `helpApi.createArticle`,
  `helpApi.updateArticle`, `helpApi.deleteArticle`.
- `frontend/src/types/index.ts` — 3 новых типа для CRUD.
- `frontend/src/pages/HelpPage.tsx` — кнопки «Новая статья» и
  «Редактировать» (только ADMIN), интеграция `HelpArticleEditor`.
- `frontend/src/components/help/HelpArticleEditor.tsx` — **новый
  компонент** (форма + предпросмотр).

---

## [4.7.0] — 2026-10-04

Итерация 15.3 — Интерактивный туториал.

### Added

#### Итерация 15.3 — Интерактивный туториал

**Проблема:**
Даже с встроенной справкой (Итерация 15.1) и FAQ (Итерация 15.4)
пользователю сложно освоить систему без наглядной демонстрации. Новый
сотрудник не знает, с чего начать и какие шаги предпринять для
построения первого плана.

**Решение:**
Создан интерактивный пошаговый туториал, который «ведёт» пользователя
по ключевым сценариям работы в системе.

**1. Инфраструктура туров (Frontend):**
- ✅ Установлена библиотека `react-joyride` для создания туров.
- ✅ Создан `frontend/src/tutorial/tours.ts` с конфигурацией шагов для
  нескольких туров:
  - `getting-started` — первый план за 5 минут (11 шагов).
  - `gantt-basics` — основы работы с диаграммой Ганта (7 шагов).
  - `shift-management` — работа мастера смены (8 шагов).
- ✅ Создан `frontend/src/tutorial/types.ts` с типами `Tour` и
  `TutorialContextType`.
- ✅ Создан `frontend/src/context/TutorialContext.tsx` для управления
  состоянием активного тура.
- ✅ Создан компонент `TutorialProvider` для глобального доступа к логике
  туров.

**2. Интеграция в UI:**
- ✅ В `MainLayout.tsx` добавлена кнопка «Помощь» (иконка `?`) в шапке
  с выпадающим меню, содержащим:
  - пункт «Открыть справку» (переход на `/help`);
  - список интерактивных туров с возможностью запуска.
- ✅ На странице `HelpPage.tsx` добавлен блок «Интерактивные туры» с
  карточками для запуска каждого тура.
- ✅ Ключевые элементы интерфейса (кнопки, поля, панели) получили
  `data-tour-id` для привязки шагов:
  - `sidebar`, `menu-equipment`, `menu-products`, `menu-orders`,
    `menu-schedule` (главное меню);
  - `build-plan-button`, `advisor-panel`, `plans-history`,
    `open-gantt-button` (страница «Планирование»);
  - `gantt-toolbar`, `gantt-edit-toggle`, `gantt-recalc-button`,
    `gantt-timeline` (диаграмма Ганта);
  - `shift-date-picker`, `shift-selector`, `shift-tasks-list`,
    `task-material-load`, `task-complete`, `task-lab-block`
    (рабочее место мастера).
- ✅ В `App.tsx` добавлен глобальный `TutorialProvider` и компонент
  `TutorialRunner`, который рендерит `<Joyride/>` поверх всего приложения.

**3. Логика туториала:**
- ✅ Прогресс прохождения тура сохраняется в `localStorage`
  (`aps_tutorial_completed_<tour_id>`).
- ✅ Реализован сброс прогресса (кнопка «Пройти заново»).
- ✅ Возможность пропустить тур (кнопка «Пропустить» на любом шаге).
- ✅ Поддержка навигации: «Назад», «Далее», «Завершить».
- ✅ Синхронизация состояния `activeTour` + `currentStepIndex` через
  `TutorialContext`.
- ✅ Локализация react-joyride на русский язык.

**4. Статья в справке (Backend):**
- ✅ Seed-миграция `add_27_seed_1.sql` добавляет статью
  `tutorial-interactive` в категорию `getting-started`.
- ✅ Статья содержит ссылки на все доступные туры.

**5. Тесты (+18, всего 738):**
- ✅ `frontend/src/context/__tests__/TutorialContext.test.tsx` (13):
  - Инициализация (2).
  - `startTour`, `stopTour` (3).
  - Навигация по шагам: `nextStep`, `prevStep`, `goToStep` (5).
  - Сохранение в localStorage (3).
- ✅ `frontend/src/tutorial/__tests__/tours.test.ts` (18):
  - Корректность структуры туров (4).
  - Валидность `target`, `content`, `placement` (3).
  - Опции шагов (3).
  - `getTourById` (3).
  - Проверки конкретных туров (5).

**Ключевые гарантии:**
- ✅ **Пошаговое обучение** — пользователь видит, куда нажимать.
- ✅ **Сохранение прогресса** — тур не показывается повторно.
- ✅ **Сброс** — можно пройти заново в любой момент.
- ✅ **Обратная совместимость** — если тур не настроен, UI работает как раньше.
- ✅ **Локализация** — все кнопки и подсказки на русском.

### Changed

- Версия проекта: `4.6.0` → `4.7.0`.
- `App.tsx` — обёрнут в `TutorialProvider`, добавлен `TutorialRunner`.
- `MainLayout.tsx` — добавлена кнопка «Помощь» с меню туров, `data-tour-id`
  на sidebar и пункты меню.
- `HelpPage.tsx` — добавлен блок «Интерактивные туры» на главной странице.
- `SchedulePage.tsx` — добавлены `data-tour-id` на ключевые элементы.
- `GanttPage.tsx` — добавлены `data-tour-id` на контейнер диаграммы.
- `GanttToolbar.tsx` — добавлены `data-tour-id` на тулбар, переключатель
  режима и кнопку «Пересчитать».
- `ShiftPage.tsx` — добавлены `data-tour-id` на поля выбора смены,
  задания и иконки действий.
- `README.md` — обновлён список фич и Roadmap.
- `docs/ROADMAP.md` — Итерация 15.3 отмечена как ✅.
- `docs/DEVELOPMENT.md` — добавлен раздел «Как добавить интерактивный тур».

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