// frontend/src/utils/ganttHelpers.ts
/**
 * Общие helper-функции для Ганта (Итерация 13.17).
 *
 * Чистые функции без побочных эффектов.
 */

// ==========================================
// ПЕРЕСЕЧЕНИЯ ИНТЕРВАЛОВ
// ==========================================

/**
 * Проверяет пересечение двух полуоткрытых интервалов [s1, e1) и [s2, e2).
 * Задачи на стыке (e1 === s2) не считаются пересекающимися.
 */
export const overlaps = (
    s1: Date | number,
    e1: Date | number,
    s2: Date | number,
    e2: Date | number,
): boolean => {
    const s1n = s1 instanceof Date ? s1.getTime() : s1;
    const e1n = e1 instanceof Date ? e1.getTime() : e1;
    const s2n = s2 instanceof Date ? s2.getTime() : s2;
    const e2n = e2 instanceof Date ? e2.getTime() : e2;
    return s1n < e2n && s2n < e1n;
};

// ==========================================
// ВЫХОДНЫЕ
// ==========================================

/**
 * Проверяет, является ли дата субботой или воскресеньем.
 */
export const isWeekendDate = (d: Date): boolean => {
    const dow = d.getDay();
    return dow === 0 || dow === 6;
};

/**
 * Проверяет, попадает ли интервал [start, end] на выходной день.
 * Возвращает true, если хотя бы одна из границ — выходной.
 */
export const isWeekendInterval = (start: Date, end: Date): boolean => {
    return isWeekendDate(start) || isWeekendDate(end);
};

// ==========================================
// ФОРМАТИРОВАНИЕ ДАТ
// ==========================================

/**
 * Форматирует datetime-local в ISO-строку с локальной TZ.
 * Пример: '2026-09-01T14:30'
 */
export const toLocalInputValue = (d: Date): string => {
    const pad = (n: number) => n.toString().padStart(2, '0');
    return (
        `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
        `T${pad(d.getHours())}:${pad(d.getMinutes())}`
    );
};

/**
 * Форматирует ISO-строку для input[type=datetime-local].
 */
export const formatDateForInput = (isoString: string): string => {
    return toLocalInputValue(new Date(isoString));
};

/**
 * Форматирует интервал «HH:MM — HH:MM».
 */
export const formatTimeRange = (
    start: string | Date,
    end: string | Date,
): string => {
    const s = start instanceof Date ? start : new Date(start);
    const e = end instanceof Date ? end : new Date(end);
    const opts: Intl.DateTimeFormatOptions = {
        hour: '2-digit',
        minute: '2-digit',
    };
    return `${s.toLocaleTimeString('ru-RU', opts)} — ${e.toLocaleTimeString('ru-RU', opts)}`;
};

/**
 * Считает длительность между двумя датами в минутах.
 */
export const durationMinutes = (
    start: string | Date,
    end: string | Date,
): number => {
    const s = start instanceof Date ? start : new Date(start);
    const e = end instanceof Date ? end : new Date(end);
    return Math.round((e.getTime() - s.getTime()) / 60000);
};

/**
 * Прибавляет минуты к ISO-строке и возвращает ISO.
 */
export const addMinutesIso = (
    iso: string,
    minutes: number,
): string => {
    const d = new Date(iso);
    d.setMinutes(d.getMinutes() + minutes);
    return d.toISOString();
};

// ==========================================
// SNAP
// ==========================================

/**
 * Округляет дату до ближайшего шага (в мс).
 */
export const snapDate = (date: Date, stepMs: number): Date => {
    return new Date(Math.round(date.getTime() / stepMs) * stepMs);
};

// ==========================================
// ИНДЕКСАЦИЯ
// ==========================================

/**
 * Группирует массив по ключу-функции.
 */
export const groupBy = <T, K extends string | number>(
    items: T[],
    getKey: (item: T) => K,
): Record<K, T[]> => {
    const result = {} as Record<K, T[]>;
    for (const item of items) {
        const key = getKey(item);
        if (!result[key]) result[key] = [];
        result[key].push(item);
    }
    return result;
};

/**
 * Возвращает уникальные значения из массива (сохраняя порядок).
 */
export const uniqueBy = <T>(
    items: T[],
    getKey: (item: T) => string,
): T[] => {
    const seen = new Set<string>();
    const result: T[] = [];
    for (const item of items) {
        const key = getKey(item);
        if (!seen.has(key)) {
            seen.add(key);
            result.push(item);
        }
    }
    return result;
};

// ==========================================
// ПОИСК БЛИЖАЙШИХ
// ==========================================

/**
 * Возвращает задачу с максимальным end среди переданных ID.
 * Используется для вычисления earliest_start.
 */
export const maxEndOfTasks = <T extends {id: string; end: string}>(
    tasks: T[],
    ids: string[],
): number => {
    let maxMs = 0;
    for (const id of ids) {
        const t = tasks.find((x) => x.id === id);
        if (t) {
            const endMs = new Date(t.end).getTime();
            if (endMs > maxMs) maxMs = endMs;
        }
    }
    return maxMs;
};

/**
 * Возвращает true, если задача с таким ID есть в списке.
 */
export const taskExists = <T extends {id: string}>(
    tasks: T[],
    id: string,
): boolean => {
    return tasks.some((t) => t.id === id);
};