// frontend/src/config.ts
//
// Конфигурация frontend. Значения вшиваются в бандл на этапе сборки (Vite).
//
// Vite встраивает переменные с префиксом VITE_* в код через
// import.meta.env.VITE_*.
//
// Для production: VITE_API_URL передаётся как build-arg в Dockerfile:
//   docker build --build-arg VITE_API_URL=https://your-domain.com ...
//   (или автоматически через docker-compose.prod.yml из .env)
//
// ⚠️  После изменения VITE_API_URL нужно ПЕРЕСОБРАТЬ frontend:
//     docker compose -f docker-compose.prod.yml build frontend
//     docker compose -f docker-compose.prod.yml up -d frontend

/**
 * Плейсхолдеры из .env.example, которые НЕ являются реальными URL.
 * Если пользователь забыл заменить VITE_API_URL в .env, используем fallback.
 */
const PLACEHOLDER_VALUES = [
    'http://your-server-ip',
    'https://your-domain.com',
    'your-server-ip',
    'your-domain.com',
];

/**
 * Проверяет, является ли значение "настоящим" URL API.
 * Возвращает false для пустого значения и для плейсхолдеров.
 */
function isValidApiUrl(value: string | undefined): value is string {
    if (!value || value.trim() === '') return false;
    const normalized = value.trim().replace(/\/+$/, ''); // убрать слеши в конце
    if (PLACEHOLDER_VALUES.includes(normalized)) return false;
    // Должен начинаться с http:// или https://
    if (!/^https?:\/\//i.test(normalized)) return false;
    return true;
}

/**
 * Базовый URL API.
 *
 * Логика выбора:
 *   1. Если VITE_API_URL задан и не является плейсхолдером — используем его.
 *   2. Иначе — fallback на http://localhost:8080 (для локального теста).
 *   3. Если Vite не смог прочитать env (SSR/тесты) — тот же fallback.
 *
 * Примеры:
 *   VITE_API_URL=http://localhost:8080   → http://localhost:8080
 *   VITE_API_URL=https://aps.example.com → https://aps.example.com
 *   VITE_API_URL=http://your-server-ip   → http://localhost:8080   (placeholder)
 *   VITE_API_URL=(не задан)              → http://localhost:8080   (fallback)
 *
 * ⚠️  Значение вшивается в бандл при сборке — не меняется в runtime.
 */
export const API_BASE_URL: string = (() => {
    const envUrl = import.meta.env.VITE_API_URL as string | undefined;

    if (isValidApiUrl(envUrl)) {
        return envUrl.trim().replace(/\/+$/, ''); // нормализация: без слеша в конце
    }

    // Fallback — работает для локального развёртывания в VM/VirtualBox.
    return 'http://localhost:8080';
})();

/**
 * Таймаут по умолчанию для API-запросов (мс).
 * Для solver-запросов (build, whatif) axios переопределяет до 300_000 в api.ts.
 */
export const API_TIMEOUT_MS = 30_000;

/**
 * Размер страницы по умолчанию в таблицах (AG Grid).
 */
export const PAGINATION_PAGE_SIZE = 20;

/**
 * Название приложения. Используется в document.title (App.tsx).
 */
export const APP_NAME = 'APS Production Scheduler';

// ==========================================
// DEV-предупреждение
// ==========================================
// Если в dev-режиме VITE_API_URL — плейсхолдер или не задан,
// выводим предупреждение в консоль (только для разработчика).
if (import.meta.env.DEV) {
    const envUrl = import.meta.env.VITE_API_URL as string | undefined;
    if (!isValidApiUrl(envUrl)) {
        // eslint-disable-next-line no-console
        console.warn(
            '[config] VITE_API_URL не задан или содержит плейсхолдер. ' +
            `Используется fallback: ${API_BASE_URL}. ` +
            'Задайте VITE_API_URL в .env или через --build-arg.',
        );
    }
}