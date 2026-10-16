// frontend/src/utils/ganttGroups.ts
/**
 * Группировка подзадач LINE_FILL для отображения на Ганте
 * (Итерация 13.17 + 14.1 + 22).
 *
 * Проблема: длинные LINE_FILL разбиваются на N частей
 * (fill_X_part1, fill_X_part2, ...). На Ганте это создаёт
 * визуальный шум из множества мелких блоков.
 *
 * Решение (Вариант D): сворачиваем N частей в одну задачу
 * с суммой длительностей. Пользователь может раскрыть группу
 * (кликом с Alt или через контекстное меню).
 *
 * Итерация 14.1:
 *   - Добавлена функция groupByBatch — для режима «По партиям».
 *     Она НЕ сворачивает LINE_FILL, а оставляет все части как есть,
 *     но добавляет поле `_batch_group_id` (используется только
 *     для внутренних нужд рендера).
 *   - Функция groupFillParts осталась без изменений и работает
 *     независимо от режима группировки.
 *
 * Итерация 22 (fix #line-fill-pauses):
 *   - Группировка учитывает ПАУЗЫ между частями одной партии.
 *   - Если между соседними частями пауза > MAX_GAP_FOR_GROUPING_MS
 *     (24 часа), партия разбивается на несколько групп-сегментов.
 *   - Каждая группа-сегмент получает уникальный id и в имени
 *     содержит диапазон частей (например, «· 2-4/4 частей»).
 *   - Причина: до этого фикса группа охватывала все части партии,
 *     от первой до последней, включая длинные паузы (выходные,
 *     ожидание) — и «широкая» виртуальная полоса накладывалась
 *     на другие группы в те же календарные даты.
 *   - Открытие любой группы-сегмента показывает ВСЕ части партии
 *     (см. expandedGroups) — это осознанное UX-решение.
 */

import type {TaskData} from '../types';

const PART_REGEX = / \(часть (\d+)\/(\d+)\)$/;

/**
 * Итерация 22: максимальная пауза между соседними частями
 * одной партии, при которой они ещё считаются «одной группой».
 *
 * 24 часа = ночной перерыв между сменами не разрывает группу,
 * а выходные (2+ суток) — разрывают.
 */
const MAX_GAP_FOR_GROUPING_MS = 20 * 60 * 60 * 1000;

/**
 * Проверяет, является ли задача частью серии LINE_FILL.
 */
export const isFillPart = (task: TaskData): boolean => {
    return PART_REGEX.test(task.operation_name);
};

/**
 * Извлекает базовое имя (без суффикса «(часть N/M)»).
 */
export const getBaseFillName = (task: TaskData): string => {
    return task.operation_name.replace(PART_REGEX, '');
};

/**
 * Извлекает номер и общее количество частей из имени задачи.
 * Возвращает [N, M] или null, если имя не соответствует формату.
 */
const extractPartNumbers = (task: TaskData): [number, number] | null => {
    const m = task.operation_name.match(PART_REGEX);
    if (!m) return null;
    return [parseInt(m[1], 10), parseInt(m[2], 10)];
};

/**
 * Ключ группы: batch_id + базовое имя.
 *
 * Используется как БАЗОВЫЙ ключ — сегменты добавляют
 * к нему суффикс `__seg<N>` (см. groupFillParts).
 */
export const getGroupKey = (task: TaskData): string => {
    return `${task.batch_id}__${getBaseFillName(task)}`;
};

/**
 * Итерация 13.17 (9f): проверка, что задача — свёрнутая группа.
 */
export const isGroupTask = (task: TaskData): boolean => {
    return task.id.startsWith('__group__');
};

/**
 * Итерация 13.17 (9f): извлечение ключа группы из item.id.
 *
 * `__group__<key>` → `<key>`.
 *
 * Итерация 22: ключ может содержать суффикс `__seg<N>`.
 * Возвращаем весь ключ как есть — вызывающий код использует
 * его для сопоставления с expandedGroups.
 */
export const getGroupKeyFromId = (itemId: string): string | null => {
    const prefix = '__group__';
    if (!itemId.startsWith(prefix)) return null;
    return itemId.substring(prefix.length);
};

/**
 * Внутренняя структура: сегмент группы (непрерывная серия частей).
 */
interface GroupSegment {
    parts: TaskData[];
    startMs: number;
    endMs: number;
}

/**
 * Итерация 22: разбивает отсортированный массив частей
 * на сегменты по паузам > MAX_GAP_FOR_GROUPING_MS.
 */
const splitPartsIntoSegments = (
    sortedParts: TaskData[],
): GroupSegment[] => {
    if (sortedParts.length === 0) return [];

    const segments: GroupSegment[] = [];
    let current: GroupSegment = {
        parts: [],
        startMs: new Date(sortedParts[0].start).getTime(),
        endMs: new Date(sortedParts[0].end).getTime(),
    };

    for (const part of sortedParts) {
        const partStart = new Date(part.start).getTime();
        const partEnd = new Date(part.end).getTime();

        if (current.parts.length === 0) {
            current.parts.push(part);
            current.startMs = partStart;
            current.endMs = partEnd;
            continue;
        }

        const gapMs = partStart - current.endMs;

        if (gapMs > MAX_GAP_FOR_GROUPING_MS) {
            // Закрываем текущий сегмент и начинаем новый
            segments.push(current);
            current = {
                parts: [part],
                startMs: partStart,
                endMs: partEnd,
            };
        } else {
            // Продолжаем текущий сегмент
            current.parts.push(part);
            current.endMs = Math.max(current.endMs, partEnd);
        }
    }

    if (current.parts.length > 0) {
        segments.push(current);
    }

    return segments;
};

/**
 * Строит виртуальную задачу-группу из одного сегмента.
 *
 * Итерация 22: имя содержит диапазон частей, если сегмент
 * не охватывает всю партию. Например:
 *   - один сегмент на всю партию: «Слив на линию розлива · 4 частей»
 *   - сегмент 2-4 из 4: «Слив на линию розлива · 2-4/4 частей»
 */
const buildGroupTask = (
    segment: GroupSegment,
    allPartsCount: number,
    baseName: string,
    groupId: string,
): TaskData => {
    const first = segment.parts[0];
    const totalDuration = segment.parts.reduce(
        (s, t) => s + t.duration_minutes,
        0,
    );

    // Диапазон номеров частей в этом сегменте
    const partNumbers = segment.parts
        .map((p) => extractPartNumbers(p)?.[0] ?? 0)
        .filter((n) => n > 0);
    const minPart = partNumbers.length > 0 ? Math.min(...partNumbers) : 1;
    const maxPart = partNumbers.length > 0 ? Math.max(...partNumbers) : 1;

    const isWholeBatch = segment.parts.length === allPartsCount;
    const label = isWholeBatch
        ? `${baseName} · ${segment.parts.length} частей`
        : `${baseName} · ${minPart}-${maxPart}/${allPartsCount} частей`;

    return {
        ...first,
        id: groupId,
        operation_name: label,
        start: first.start,
        end: segment.parts[segment.parts.length - 1].end,
        duration_minutes: totalDuration,
        item_type: 'task',
        // Запоминаем ID частей этого сегмента — по клику раскрываем.
        // При раскрытии показываются ВСЕ части партии (см. ниже).
        depends_on_task_ids: segment.parts.map((p) => p.id),
    };
};

/**
 * Группирует подзадачи LINE_FILL.
 *
 * Args:
 *   tasks: исходный список задач.
 *   expandedGroups: Set ключей раскрытых групп.
 *     Если группа (или любой её сегмент) в этом Set —
 *     показываются все части партии, иначе — свёрнутые сегменты.
 *
 * Returns:
 *   Новый список задач, где подзадачи заменены на свёрнутые
 *   задачи-сегменты (если группа не раскрыта).
 *
 * Итерация 22: группы разбиваются по паузам > 24 ч.
 * ВАЖНО: эта функция НЕ зависит от groupByMode.
 */
export const groupFillParts = (
    tasks: TaskData[],
    expandedGroups: Set<string>,
): TaskData[] => {
    const result: TaskData[] = [];
    const groups = new Map<string, TaskData[]>();

    // 1. Разложить части по группам (baseKey → parts)
    for (const task of tasks) {
        if (isFillPart(task)) {
            const key = getGroupKey(task);
            if (!groups.has(key)) groups.set(key, []);
            groups.get(key)!.push(task);
        } else {
            result.push(task);
        }
    }

    // 2. Обработать каждую группу
    for (const [baseKey, parts] of groups.entries()) {
        // Сортируем части по времени
        const sorted = [...parts].sort(
            (a, b) =>
                new Date(a.start).getTime() - new Date(b.start).getTime(),
        );

        // Если партия раскрыта (ключ базовый ИЛИ любой сегмент) —
        // показываем ВСЕ части партии без свёртки.
        const isExpanded =
            expandedGroups.has(baseKey) ||
            Array.from(expandedGroups).some((k) =>
                k.startsWith(`${baseKey}__seg`),
            );

        if (isExpanded) {
            result.push(...sorted);
            continue;
        }

        // Одна часть — не группируем
        if (sorted.length === 1) {
            result.push(sorted[0]);
            continue;
        }

        // Разбиваем на сегменты по паузам
        const segments = splitPartsIntoSegments(sorted);

        if (segments.length === 1) {
            // Вся партия — один сегмент. Классическая группа.
            const groupId = `__group__${baseKey}`;
            result.push(
                buildGroupTask(
                    segments[0],
                    sorted.length,
                    getBaseFillName(sorted[0]),
                    groupId,
                ),
            );
        } else {
            // Несколько сегментов — каждый отдельная группа.
            // Базовый ключ + суффикс __segN — уникальный id.
            segments.forEach((seg, idx) => {
                const segKey = `${baseKey}__seg${idx}`;
                const groupId = `__group__${segKey}`;
                result.push(
                    buildGroupTask(
                        seg,
                        sorted.length,
                        getBaseFillName(sorted[0]),
                        groupId,
                    ),
                );
            });
        }
    }

    // 3. Сортируем результат по времени начала
    result.sort(
        (a, b) => new Date(a.start).getTime() - new Date(b.start).getTime(),
    );

    return result;
};

/**
 * Возвращает количество частей в группе по ключу.
 */
export const countPartsInGroup = (
    tasks: TaskData[],
    groupKey: string,
): number => {
    // Поддерживаем и базовый ключ, и суффиксы __segN
    const baseKey = groupKey.replace(/__seg\d+$/, '');
    return tasks.filter(
        (t) => isFillPart(t) && getGroupKey(t) === baseKey,
    ).length;
};

// ==========================================
// ИТЕРАЦИЯ 14.1: ГРУППИРОВКА ПО ПАРТИЯМ
// ==========================================

/**
 * Обёртка над groupFillParts для использования в режиме
 * «По партиям».
 *
 * Отличия от groupFillParts:
 *   - Применяется к УЖЕ отфильтрованным задачам.
 *   - НЕ добавляет поле _batch_group_id — оно не нужно,
 *     так как группировка уже задана в buildGroups
 *     (см. ganttRenderItems.ts).
 *   - Сохраняет все части LINE_FILL, если группа не раскрыта —
 *     это визуально понятнее в режиме «По партиям».
 *
 * Фактически, эта функция — просто псевдоним groupFillParts,
 * оставленный для семантической ясности в GanttPage.
 *
 * Использование в GanttPage:
 *   const groupedTasks = groupByBatch(filteredTasks, expandedGroups);
 */
export const groupByBatch = (
    tasks: TaskData[],
    expandedGroups: Set<string>,
): TaskData[] => {
    return groupFillParts(tasks, expandedGroups);
};

/**
 * Возвращает уникальные batch_id из списка задач.
 * Используется для подсчёта групп в режиме «По партиям».
 *
 * Setup, downtime и «Замывка» игнорируются.
 */
export const collectBatchIds = (tasks: TaskData[]): string[] => {
    const set = new Set<string>();
    for (const t of tasks) {
        if (t.item_type && t.item_type !== 'task') continue;
        if (!t.batch_id) continue;
        if (t.batch_id === 'Замывка' || t.batch_id === 'Выходной') continue;
        set.add(t.batch_id);
    }
    return Array.from(set);
};

/**
 * Возвращает количество задач в партии.
 */
export const countTasksInBatch = (
    tasks: TaskData[],
    batchId: string,
): number => {
    return tasks.filter(
        (t) =>
            t.batch_id === batchId &&
            (!t.item_type || t.item_type === 'task'),
    ).length;
};