# Frontend — APS Production Scheduler

React-приложение для системы оптимального планирования производства **APS Production Scheduler**.

---

## 📋 Содержание

- [Стек технологий](#стек-технологий)
- [Структура проекта](#структура-проекта)
- [Быстрый старт](#быстрый-старт)
- [Скрипты npm](#скрипты-npm)
- [Архитектура](#архитектура)
- [Соглашения](#соглашения)
- [Ссылки](#ссылки)

---

## Стек технологий

| Компонент | Версия | Назначение |
|-----------|--------|------------|
| **React** | 19.x | UI-фреймворк |
| **TypeScript** | ~6.0 | Типизация |
| **Vite** | 8.x | Сборщик и dev-сервер |
| **MUI (Material-UI)** | 9.4 | Компоненты интерфейса |
| **AG Grid Community** | 36.1 | Таблицы с inline-редактированием |
| **vis-timeline** | 8.5 | Интерактивная диаграмма Ганта |
| **vis-data** | 8.0 | DataSet для vis-timeline |
| **axios** | 1.20 | HTTP-клиент с интерсепторами |
| **react-router-dom** | 7.18 | Маршрутизация |
| **allotment** | 1.20 | Разделяемые панели (split view) |
| **date-fns** | 4.4 | Работа с датами |

---

## Структура проекта

```
frontend/
├── index.html                     # HTML-точка входа
├── package.json                   # Зависимости и скрипты
├── vite.config.ts                 # Конфигурация Vite
├── tsconfig.json                  # Базовый TS-конфиг
├── tsconfig.app.json              # TS-конфиг приложения
├── tsconfig.node.json             # TS-конфиг для Vite
├── eslint.config.js               # Конфигурация ESLint
│
├── public/                        # Статические файлы
│   └── favicon.svg
│
└── src/
    ├── main.tsx                   # Точка входа React
    ├── App.tsx                    # Корневой компонент с маршрутами
    ├── config.ts                  # Конфигурация (API_BASE_URL, константы)
    ├── index.css                  # Глобальные стили
    │
    ├── components/
    │   ├── common/
    │   │   └── DraggableDialog.tsx    # Перетаскиваемый диалог с ресайзом
    │   └── layout/
    │       └── MainLayout.tsx          # Основной layout с сайдбаром
    │
    ├── context/
    │   ├── AuthContext.tsx        # Авторизация (JWT, пользователь)
    │   └── PlainContext.tsx       # Активный план (версия)
    │
    ├── hooks/
    │   └── useDoubleClick.ts      # Хук для обработки двойного клика
    │
    ├── pages/
    │   ├── LoginPage.tsx              # Вход в систему
    │   ├── EquipmentPage.tsx          # Оборудование + ремонты
    │   ├── ProductsPage.tsx           # Продукты (ПФ/ГП)
    │   ├── MaterialsPage.tsx          # Материалы + журнал остатков + Excel
    │   ├── RecipesPage.tsx            # Рецептуры
    │   ├── OperationsPage.tsx         # Техкарты
    │   ├── OrdersPage.tsx             # Заказы и партии
    │   ├── SchedulePage.tsx           # Планирование + Advisor + история планов
    │   ├── GanttPage.tsx              # Диаграмма Ганта
    │   ├── ShiftPage.tsx              # Рабочее место мастера смены
    │   ├── PersonnelPage.tsx          # Пулы операторов
    │   ├── CzPage.tsx                 # Честный Знак
    │   ├── WhatIfPage.tsx             # What-if сценарии
    │   ├── AuditPage.tsx              # Аудит
    │   ├── SettingsPage.tsx           # Глобальные настройки
    │   └── PlanSettingsWizard.tsx     # Мастер настроек плана (9 шагов)
    │
    ├── services/
    │   └── api.ts                 # Все HTTP-обёртки над API
    │
    └── types/
        └── index.ts               # TypeScript-типы домена
```

---

## Быстрый старт

### Предварительные требования

- **Node.js** 18+
- **npm** 9+
- Запущенный **backend** на `http://localhost:8000` (см. `../backend/README.md`)

### Установка и запуск

```bash
cd frontend
npm install
npm run dev
```

Приложение откроется на **http://localhost:5173**.

**Демо-доступ:** `admin@household.ru` / `admin123`

### Переменные окружения

Vite читает переменные из `.env` (опционально):

```env
VITE_API_URL=http://localhost:8000
```

Если не задано — используется `http://localhost:8000` из `src/config.ts`.

---

## Скрипты npm

| Команда | Что делает |
|---------|------------|
| `npm run dev` | Запуск dev-сервера с HMR (порт 5173) |
| `npm run build` | Production-сборка (`tsc -b && vite build`) |
| `npm run preview` | Просмотр production-сборки |
| `npm run lint` | Проверка ESLint |

---

## Архитектура

### Маршрутизация

Все маршруты определены в `App.tsx`:

- **Публичные:** `/login`
- **Защищённые:** `/equipment`, `/products`, `/materials`, `/recipes`, `/operations`, `/orders`, `/schedule`, `/gantt`, `/shift`, `/personnel`, `/cz`, `/whatif`, `/audit`, `/settings`

Защита реализована через `ProtectedRoute` + `AuthContext`.

### Контексты

**`AuthContext.tsx`**
- JWT-токен в `localStorage` (`access_token`).
- Автоматическая подстановка `Authorization: Bearer <token>` в axios.
- При `401` — очистка токена и редирект на `/login`.
- Методы: `login`, `logout`, `refreshUser`.

**`PlainContext.tsx`** (PlanContext)
- Активный план (версия) в `localStorage` (`aps_current_plan`).
- Список всех версий планов.
- Методы: `setPlan`, `clearPlan`, `loadVersions`, `createPlan`, `deletePlan`.
- **Важно:** при активном плане страницы справочников переходят в **readonly** (режим просмотра).

### Работа с API

Все HTTP-запросы — через `src/services/api.ts`. Модули:

| Модуль | Назначение |
|--------|------------|
| `authApi` | Логин, профиль, смена пароля |
| `equipmentApi` | CRUD оборудования |
| `productsApi` | CRUD продуктов |
| `materialsApi` | CRUD материалов + остатки + журнал + Excel |
| `recipesApi` | CRUD рецептур |
| `operationsApi` | CRUD техкарт |
| `calendarApi` | CRUD событий календаря |
| `ordersApi` | CRUD заказов и партий |
| `scheduleApi` | Построение плана, версии |
| `ganttApi` | Данные Ганта, экспорт |
| `advisorApi` | Advisor-подсказки |
| `shiftApi` | Смены и задачи |
| `rescheduleApi` | Перепланирование, pin/move |
| `labApi` | Лабораторные блокировки |
| `personnelApi` | Пулы операторов |
| `czApi` | Честный Знак |
| `settingsApi` | Глобальные настройки |
| `planSettingsApi` | Настройки конкретного плана |
| `whatifApi` | What-if сценарии |
| `auditApi` | Аудит |

Все API-модули, зависящие от настроек плана, принимают опциональный `versionId?` (Итерация 13.14).

### Диаграмма Ганта

`GanttPage.tsx` использует **vis-timeline**:

- **Pan** — перетаскивание пустого места.
- **Zoom** — колёсико мыши.
- **Drag** — перетаскивание задач (только реальных, не setup/downtime).
- **Связи** — SVG-overlay поверх диаграммы, рисуются по hover.
- **Миникарта** — второй vis-timeline внизу для навигации.
- **Фильтры** — по оборудованию, продукту, партии, статусам (лаборатория, охлаждение, ЧЗ).

### Стили

- **MUI** — компоненты и тема (`createTheme` в `App.tsx`).
- **`index.css`** — глобальные стили (скроллбар, AgGrid, vis-timeline, курсоры для Ганта).
- **Allotment** — split-view панели (используется в EquipmentPage, SchedulePage).

---

## Соглашения

### Именование

- **Компоненты:** `PascalCase.tsx` (`EquipmentPage.tsx`).
- **Хуки:** `useXxx.ts` (`useDoubleClick.ts`).
- **Контексты:** `XxxContext.tsx` (`AuthContext.tsx`).
- **Сервисы:** `api.ts` (единый файл).
- **Типы:** `index.ts` в `types/`.

### Компоненты

- **Функциональные компоненты** + hooks.
- **Props** через `interface XxxProps`.
- **`React.FC<Props>`** — для всех страниц.
- **`useCallback`** — для функций, передаваемых в `useEffect`-зависимости.

### Стили

- **MUI `sx`** — inline-стили.
- **Глобальные стили** — только в `index.css`.
- **Тема** — `createTheme` в `App.tsx`.

### Типизация

- Строгая типизация всех props и API-ответов.
- Типы домена — в `types/index.ts`.
- `import type { ... }` — для type-only импортов.

### Работа с readonly-режимом

Если `currentVersionId !== null` (открыт план):

- Все страницы справочников переходят в режим просмотра.
- Кнопки «Добавить», «Удалить», inline-редактирование — отключены.
- Показывается `Alert severity="info"` с названием плана.

---

## Отладка

### React DevTools

Расширение браузера для инспекции компонентов и контекстов.

### Консоль

```tsx
console.log('Debug:', value);
console.warn('Warning:', value);
console.error('Error:', value);
```

### Очистка кэша Vite

Если изменения не применяются:

```bash
Remove-Item -Recurse -Force node_modules\.vite
npm run dev
```

### Ошибка `usePlan must be used within PlanProvider`

Возникает при кэше Vite или неправильной структуре провайдеров. Решение — очистить `.vite` и перезапустить.

---

## Ссылки

- [../README.md](../README.md) — основная документация проекта.
- [../docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) — архитектура.
- [../docs/API.md](../docs/API.md) — описание REST API.
- [../docs/DEVELOPMENT.md](../docs/DEVELOPMENT.md) — руководство разработчика.
- [../docs/TROUBLESHOOTING.md](../docs/TROUBLESHOOTING.md) — решение проблем.