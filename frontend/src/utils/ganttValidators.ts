// frontend/src/utils/ganttValidators.ts
/**
 * Клиентская валидация перемещения/изменения задач
 * на Ганте (Итерация 13.17).
 *
 * Используется для:
 *  - tooltip'а при перетаскивании (предупреждения);
 *  - мгновенной обратной связи (без ожидания API).
 *
 * ВАЖНО: серверная валидация (backend) — источник правды.
 * Эта функция лишь помогает UX. Если клиент говорит "ok",
 * а сервер вернёт 400 — покажем диалог с причиной.
 */
import type {TaskData} from '../types';
import {MAX_TASK_DURATION_MINUTES, MIN_TASK_DURATION_MINUTES,} from '../components/gantt/constants';
import {isWeekendInterval, maxEndOfTasks, overlaps,} from './ganttHelpers';

export interface ClientValidationResult {
    allowed: boolean;
    reason?: string;
    details?: string[];
    /** True, если это предупреждение, а не блокировка. */
    isWarning?: boolean;
}

// ==========================================
// ГЛАВНАЯ ФУНКЦИЯ
// ==========================================

/**
 * Валидирует перемещение задачи (для tooltip при перетаскивании).
 *
 * @param task            Изменяемая задача.
 * @param newStart        Новое время начала (ISO).
 * @param newEnd          Новое время окончания (ISO).
 * @param allTasks        Все задачи текущего плана.
 * @param planningStart   Начало плана (ISO) или null.
 * @param allowWeekend    Разрешена ли работа в выходные.
 */
export const validateTaskMove = (
    task: TaskData,
    newStart: string,
    newEnd: string,
    allTasks: TaskData[],
    planningStart: string | null,
    allowWeekend: boolean,
): ClientValidationResult => {
    const s = new Date(newStart);
    const e = new Date(newEnd);

    // 1. Проверка порядка времён
    if (e <= s) {
        return {
            allowed: false,
            reason: 'Конец должен быть позже начала',
        };
    }

    // 2. Длительность
    const durationMin = Math.round((e.getTime() - s.getTime()) / 60000);
    if (durationMin < MIN_TASK_DURATION_MINUTES) {
        return {
            allowed: false,
            reason: `Слишком короткая задача (${durationMin} мин)`,
            details: [
                `Минимум ${MIN_TASK_DURATION_MINUTES} мин.`,
            ],
        };
    }
    if (durationMin > MAX_TASK_DURATION_MINUTES) {
        return {
            allowed: false,
            reason: `Слишком длинная задача (${Math.round(durationMin / 60)} ч)`,
            details: [`Максимум ${MAX_TASK_DURATION_MINUTES / 60} ч.`],
        };
    }

    // 3. planning_start
    if (planningStart) {
        const ps = new Date(planningStart);
        if (s < ps) {
            return {
                allowed: false,
                reason: 'Задача раньше начала плана',
                details: [
                    `Начало плана: ${ps.toLocaleString('ru-RU')}`,
                    `Новое начало: ${s.toLocaleString('ru-RU')}`,
                ],
            };
        }
    }

    // 4. Выходные (предупреждение, если разрешены — иначе блокировка)
    if (!allowWeekend && isWeekendInterval(s, e)) {
        return {
            allowed: false,
            reason: 'Задача попадает на выходной день',
            details: [
                'В настройках плана запрещена работа в выходные.',
                'Параметр: allow_weekend_work.',
            ],
        };
    }
    if (allowWeekend && isWeekendInterval(s, e)) {
        // Разрешено, но предупреждаем
        // (возвращаем allowed: true, но с warning)
        // Можно использовать на UI для жёлтой подсветки.
    }

    // 5. Пересечение с другими задачами на том же оборудовании
    const conflicts = allTasks.filter(
        (t) =>
            t.id !== task.id &&
            t.equipment_id === task.equipment_id &&
            (!t.item_type || t.item_type === 'task') &&
            overlaps(s, e, new Date(t.start), new Date(t.end)),
    );
    if (conflicts.length > 0) {
        // Не блокируем — каскад раздвинет
        // Но возвращаем информацию для tooltip
        return {
            allowed: true,
            isWarning: true,
            reason: `Пересечение с ${conflicts.length} задачами — будут сдвинуты`,
            details: conflicts.slice(0, 3).map(
                (t) =>
                    `${t.operation_name}: ` +
                    `${new Date(t.start).toLocaleTimeString('ru-RU', {
                        hour: '2-digit',
                        minute: '2-digit',
                    })} — ` +
                    `${new Date(t.end).toLocaleTimeString('ru-RU', {
                        hour: '2-digit',
                        minute: '2-digit',
                    })}`,
            ),
        };
    }

    // 6. Зависимости (предшественники)
    if (
        task.depends_on_task_ids &&
        task.depends_on_task_ids.length > 0
    ) {
        const maxPredEndMs = maxEndOfTasks(allTasks, task.depends_on_task_ids);
        if (maxPredEndMs > 0 && s.getTime() < maxPredEndMs) {
            return {
                allowed: true,
                isWarning: true,
                reason: 'Задача начнётся раньше, чем закончатся предшественники',
                details: [
                    `Предшественники закончатся: ${new Date(
                        maxPredEndMs,
                    ).toLocaleString('ru-RU')}`,
                    `Новое начало: ${s.toLocaleString('ru-RU')}`,
                    'Зависимые задачи будут сдвинуты.',
                ],
            };
        }
    }

    return {allowed: true};
};

// ==========================================
// СВЯЗАННЫЕ ПРОВЕРКИ
// ==========================================

/**
 * Возвращает список задач, которые пересекаются с новой позицией.
 * Используется для подсветки конфликтов.
 */
export const findConflicts = (
    task: TaskData,
    newStart: string,
    newEnd: string,
    allTasks: TaskData[],
): TaskData[] => {
    const s = new Date(newStart);
    const e = new Date(newEnd);
    return allTasks.filter(
        (t) =>
            t.id !== task.id &&
            t.equipment_id === task.equipment_id &&
            (!t.item_type || t.item_type === 'task') &&
            overlaps(s, e, new Date(t.start), new Date(t.end)),
    );
};

/**
 * Считает, сколько задач будут сдвинуты каскадом.
 * Приблизительная оценка — для tooltip.
 */
export const estimateCascadeSize = (
    task: TaskData,
    newStart: string,
    newEnd: string,
    allTasks: TaskData[],
): number => {
    const direct = findConflicts(task, newStart, newEnd, allTasks);
    const visited = new Set<string>();
    const queue = direct.map((t) => t.id);

    while (queue.length > 0) {
        const id = queue.shift()!;
        if (visited.has(id)) continue;
        visited.add(id);

        // Последователи этой задачи
        const successors = allTasks.filter(
            (t) => t.depends_on_task_ids?.includes(id),
        );
        for (const s of successors) {
            if (!visited.has(s.id)) queue.push(s.id);
        }
    }

    return visited.size;
};