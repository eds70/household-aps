// frontend/src/utils/ganttBatchColors.ts
/**
 * Детерминированная генерация цвета для партии (Итерация 14.1).
 *
 * Задача: каждой партии (batch_id) должен соответствовать
 * стабильный цвет, который:
 *   - не меняется между рендерами;
 *   - не меняется между сессиями (сохраняется в localStorage);
 *   - не меняется между разными диаграммами (если batch_id один и тот же);
 *   - визуально различим с другими партиями.
 *
 * Решение: используем хеш от batch_id → индекс в палитре
 * BATCH_COLOR_PALETTE. При коллизии (две партии получили один цвет) —
 * это допустимо, так как:
 *   1. Скобки партий не пересекаются по времени (обычно).
 *   2. Даже если пересекаются, их подписи (label) различимы.
 *   3. Пользователь может кликнуть на скобку — она подсветится.
 *
 * Используется в:
 *   - ganttBrackets.ts (для генерации BatchBracket.color);
 *   - ganttRenderItems.ts (для окраски операций в режиме 'batch');
 *   - GanttToolbar.tsx (для легенды партий).
 */

import {BATCH_COLOR_PALETTE} from '../components/gantt/constants';

// ==========================================
// ХЕШ-ФУНКЦИЯ
// ==========================================

/**
 * Простой строковый хеш (djb2).
 *
 * Почему djb2:
 *   - быстрый (O(n) по длине строки);
 *   - хорошо распределяет UUID-подобные строки;
 *   - детерминированный (одинаковый вход → одинаковый выход).
 *
 * Альтернативы (FNV-1a, MurmurHash) — избыточны для нашей задачи
 * (нам нужен просто индекс в палитре из 12 цветов).
 */
const hashString = (str: string): number => {
    let hash = 5381;
    for (let i = 0; i < str.length; i++) {
        hash = ((hash << 5) + hash) + str.charCodeAt(i); // hash * 33 + c
    }
    // Ограничиваем положительным числом
    return Math.abs(hash);
};

// ==========================================
// ПУБЛИЧНЫЕ ФУНКЦИИ
// ==========================================

/**
 * Возвращает детерминированный цвет для партии.
 *
 * @param batchId — ID партии (UUID-строка) или любой уникальный
 *                  идентификатор. Если пусто — возвращает серый.
 * @returns HEX-цвет из BATCH_COLOR_PALETTE.
 *
 * Примеры:
 *   getBatchColor('a1b2c3d4-...') → '#e74c3c'
 *   getBatchColor('a1b2c3d4-...') → '#e74c3c' (тот же самый)
 *   getBatchColor('f9e8d7c6-...') → '#27ae60'
 *   getBatchColor('')             → '#95a5a6'
 */
export const getBatchColor = (batchId: string | null | undefined): string => {
    if (!batchId) return '#95a5a6'; // серый для «пустых» значений
    const idx = hashString(batchId) % BATCH_COLOR_PALETTE.length;
    return BATCH_COLOR_PALETTE[idx];
};

/**
 * Возвращает цвет с прозрачностью (для фона скобки).
 *
 * @param batchId — ID партии.
 * @param opacity — прозрачность (0.0 – 1.0). По умолчанию 0.08.
 * @returns строка вида 'rgba(231, 76, 60, 0.08)'.
 *
 * Используется для заливки прямоугольника скобки.
 */
export const getBatchColorWithOpacity = (
    batchId: string | null | undefined,
    opacity: number = 0.08,
): string => {
    const hex = getBatchColor(batchId);
    return hexToRgba(hex, opacity);
};

/**
 * Утилита: HEX → rgba-строка.
 *
 * @param hex — цвет в формате '#rrggbb' или '#rgb'.
 * @param alpha — прозрачность (0.0 – 1.0).
 * @returns 'rgba(r, g, b, alpha)'.
 */
export const hexToRgba = (hex: string, alpha: number): string => {
    // Убираем '#'
    let h = hex.replace('#', '');

    // Поддержка короткого формата (#abc → #aabbcc)
    if (h.length === 3) {
        h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
    }

    const r = parseInt(h.substring(0, 2), 16);
    const g = parseInt(h.substring(2, 4), 16);
    const b = parseInt(h.substring(4, 6), 16);

    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
};

/**
 * Возвращает читаемый ярлык партии.
 *
 * @param batchId — ID партии (UUID).
 * @param productName — опциональное название продукта.
 * @returns короткий ярлык для отображения в скобке.
 *
 * Примеры:
 *   getBatchLabel('a1b2c3d4-...', 'Крем-мыло 1л') → 'Крем-мыло 1л · a1b2c3d4'
 *   getBatchLabel('a1b2c3d4-...', null)           → 'Партия a1b2c3d4'
 *   getBatchLabel(null, null)                     → 'Партия ?'
 */
export const getBatchLabel = (
    batchId: string | null | undefined,
    productName?: string | null,
): string => {
    if (!batchId) return 'Партия ?';
    const shortId = batchId.substring(0, 8);
    if (productName) {
        // Обрезаем длинное название продукта
        const shortProduct =
            productName.length > 24
                ? productName.substring(0, 22) + '…'
                : productName;
        return `${shortProduct} · ${shortId}`;
    }
    return `Партия ${shortId}`;
};

/**
 * Возвращает контрастный цвет текста для заданного фона.
 *
 * Используется, чтобы подпись на скобке (в цвете партии)
 * всегда была читаемой.
 *
 * @param hex — цвет фона.
 * @returns '#000000' (тёмный) или '#ffffff' (светлый).
 *
 * Логика: считаем относительную яркость по WCAG 2.0.
 * Если яркость > 0.5 — возвращаем тёмный текст, иначе светлый.
 */
export const getContrastTextColor = (hex: string): string => {
    let h = hex.replace('#', '');
    if (h.length === 3) {
        h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
    }
    const r = parseInt(h.substring(0, 2), 16) / 255;
    const g = parseInt(h.substring(2, 4), 16) / 255;
    const b = parseInt(h.substring(4, 6), 16) / 255;

    // Относительная яркость (WCAG 2.0)
    const toLinear = (c: number): number =>
        c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);

    const luminance =
        0.2126 * toLinear(r) +
        0.7152 * toLinear(g) +
        0.0722 * toLinear(b);

    return luminance > 0.5 ? '#000000' : '#ffffff';
};