// frontend/src/utils/ganttGroups.ts
/**
 * Группировка подзадач LINE_FILL для отображения на Ганте
 * (Итерация 13.17).
 *
 * Проблема: длинные LINE_FILL разбиваются на N частей
 * (fill_X_part1, fill_X_part2, ...). На Ганте это создаёт
 * визуальный шум из множества мелких блоков.
 *
 * Решение (Вариант D): сворачиваем N частей в одну задачу
 * с суммой длительностей. Пользователь может раскрыть группу
 * (кликом с Alt или через контекстное меню).
 */
import type {TaskData} from '../types';

const PART_REGEX = / \(часть \d+\/\d+\)$/;

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
 * Ключ группы: batch_id + базовое имя.
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
 */
export const getGroupKeyFromId = (itemId: string): string | null => {
    const prefix = '__group__';
    if (!itemId.startsWith(prefix)) return null;
    return itemId.substring(prefix.length);
};

/**
 * Группирует подзадачи LINE_FILL.
 *
 * Args:
 *   tasks: исходный список задач.
 *   expandedGroups: Set ключей раскрытых групп.
 *     Если группа в этом Set — показываются все части,
 *     иначе — одна свёрнутая задача.
 *
 * Returns:
 *   Новый список задач, где подзадачи заменены на одну
 *   свёрнутую задачу (если группа не раскрыта).
 */
export const groupFillParts = (
    tasks: TaskData[],
    expandedGroups: Set<string>,
): TaskData[] => {
    const result: TaskData[] = [];
    const groups = new Map<string, TaskData[]>();

    for (const task of tasks) {
        if (isFillPart(task)) {
            const key = getGroupKey(task);
            if (!groups.has(key)) groups.set(key, []);
            groups.get(key)!.push(task);
        } else {
            result.push(task);
        }
    }

    for (const [key, parts] of groups.entries()) {
        if (expandedGroups.has(key)) {
            // Группа раскрыта — показываем все части
            result.push(...parts);
        } else if (parts.length === 1) {
            // Всего одна часть — не группируем
            result.push(parts[0]);
        } else {
            // Сворачиваем в одну задачу
            const sorted = parts.sort(
                (a, b) =>
                    new Date(a.start).getTime() - new Date(b.start).getTime(),
            );
            const first = sorted[0];
            const last = sorted[sorted.length - 1];
            const totalDuration = sorted.reduce(
                (s, t) => s + t.duration_minutes,
                0,
            );

            result.push({
                ...first,
                // Уникальный ID группы — чтобы не путать с реальной задачей
                id: `__group__${key}`,
                operation_name: `${getBaseFillName(first)} · ${parts.length} частей`,
                start: first.start,
                end: last.end,
                duration_minutes: totalDuration,
                // Спец-маркер для рендера
                item_type: 'task',
                // Запоминаем ID частей, чтобы по клику раскрыть
                depends_on_task_ids: parts.map((p) => p.id),
            });
        }
    }

    // Сортируем результат по времени начала
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
    return tasks.filter(
        (t) => isFillPart(t) && getGroupKey(t) === groupKey,
    ).length;
};