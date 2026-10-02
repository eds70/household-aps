// frontend/src/utils/ganttBrackets.ts
/**
 * Расчёт «скобок партий» для диаграммы Ганта (Итерация 14.1).
 *
 * Задача: показать партию как единое целое, НЕ ломая группировку
 * по оборудованию. Партия — это логическая сущность, размазанная
 * по времени и оборудованию. Её операции пересекаются во времени
 * с операциями других партий. Поэтому нельзя просто «упаковать»
 * партию в одну строку.
 *
 * Решение: фантомные скобки (SVG-прямоугольники), которые
 * охватывают все операции одной партии.
 *
 *   ┌─────────── Партия А ────────────┐
 *   │  [Варка А]      [Слив А]        │
 *   └─────────────────────────────────┘
 *
 * Скобки рисуются поверх диаграммы в отдельном SVG-слое
 * (см. useGanttTimeline → drawBatchBrackets).
 *
 * Используется в:
 *   - useGanttTimeline.ts (рендер SVG);
 *   - GanttToolbar.tsx (количество скобок в тулбаре).
 */

import type {BatchBracket, TaskData} from '../types';
import {getBatchColor, getBatchLabel} from './ganttBatchColors';
import {NON_BATCH_VALUES} from '../components/gantt/constants';

// ==========================================
// ОСНОВНАЯ ФУНКЦИЯ
// ==========================================

/**
 * Группирует задачи по batch_id и возвращает список скобок партий.
 *
 * Логика:
 *   1. Фильтруем задачи: только item_type === 'task' (без setup/downtime).
 *   2. Пропускаем задачи с batch_id из NON_BATCH_VALUES
 *      («Замывка», «Выходной», null).
 *   3. Группируем по batch_id.
 *   4. Для каждой группы считаем:
 *      - min(start) — начало партии;
 *      - max(end) — конец партии;
 *      - taskIds — список ID задач;
 *      - equipmentIds — список уникальных equipment_id;
 *      - hasBlockedTasks — есть ли заблокированные задачи;
 *      - hasSlowCooling — есть ли задачи с замедленным охлаждением.
 *   5. Возвращаем массив BatchBracket, отсортированный по start.
 *
 * @param tasks — все задачи плана (включая setup/downtime — они
 *                будут отфильтрованы внутри).
 * @returns массив скобок партий.
 *
 * Пример:
 *   const brackets = buildBatchBrackets(tasks);
 *   // [
 *   //   { batchId: 'a1b2...', start: '...', end: '...', ... },
 *   //   { batchId: 'f9e8...', start: '...', end: '...', ... },
 *   // ]
 */
export const buildBatchBrackets = (tasks: TaskData[]): BatchBracket[] => {
    // 1. Фильтруем только реальные задачи
    const realTasks = tasks.filter((t) => {
        if (t.item_type && t.item_type !== 'task') return false;
        if (!t.batch_id) return false;
        if (NON_BATCH_VALUES.has(t.batch_id)) return false;
        return true;
    });

    if (realTasks.length === 0) return [];

    // 2. Группируем по batch_id
    const byBatch = new Map<string, TaskData[]>();
    for (const task of realTasks) {
        const list = byBatch.get(task.batch_id) || [];
        list.push(task);
        byBatch.set(task.batch_id, list);
    }

    // 3. Строим скобки
    const brackets: BatchBracket[] = [];
    for (const [batchId, batchTasks] of byBatch.entries()) {
        brackets.push(buildSingleBracket(batchId, batchTasks));
    }

    // 4. Сортируем по времени начала (стабильный порядок)
    brackets.sort((a, b) => {
        const at = new Date(a.start).getTime();
        const bt = new Date(b.start).getTime();
        return at - bt;
    });

    return brackets;
};

// ==========================================
// ВНУТРЕННИЕ ФУНКЦИИ
// ==========================================

/**
 * Строит одну скобку для группы задач одной партии.
 */
const buildSingleBracket = (
    batchId: string,
    tasks: TaskData[],
): BatchBracket => {
    // Находим min(start) и max(end)
    let minStartMs = Infinity;
    let maxEndMs = -Infinity;
    let minStartIso = '';
    let maxEndIso = '';

    const equipmentSet = new Set<string>();
    const taskIds: string[] = [];
    let hasBlockedTasks = false;
    let hasSlowCooling = false;
    let productName: string | null = null;

    for (const t of tasks) {
        const startMs = new Date(t.start).getTime();
        const endMs = new Date(t.end).getTime();

        if (startMs < minStartMs) {
            minStartMs = startMs;
            minStartIso = t.start;
        }
        if (endMs > maxEndMs) {
            maxEndMs = endMs;
            maxEndIso = t.end;
        }

        equipmentSet.add(t.equipment_id);
        taskIds.push(t.id);

        if (t.is_lab_blocked) hasBlockedTasks = true;
        if (t.cooling_mode === 'slow') hasSlowCooling = true;

        // Первое непустое название продукта — используем как подпись
        if (!productName && t.product_id && t.product_id !== '—') {
            productName = t.product_id;
        }
    }

    const color = getBatchColor(batchId);
    const label = getBatchLabel(batchId, productName);
    const durationMinutes = Math.round((maxEndMs - minStartMs) / 60000);

    return {
        batchId,
        label,
        start: minStartIso,
        end: maxEndIso,
        color,
        taskIds,
        equipmentIds: Array.from(equipmentSet),
        durationMinutes,
        hasBlockedTasks,
        hasSlowCooling,
    };
};

// ==========================================
// ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ (для UI)
// ==========================================

/**
 * Возвращает Set ID задач, которые принадлежат партиям,
 * содержащим хотя бы одну заблокированную задачу.
 *
 * Используется в GanttFiltersPopover для фильтра
 * «Только партии с блокировкой».
 */
export const getTaskIdsInBlockedBatches = (
    brackets: BatchBracket[],
): Set<string> => {
    const result = new Set<string>();
    for (const b of brackets) {
        if (b.hasBlockedTasks) {
            for (const id of b.taskIds) {
                result.add(id);
            }
        }
    }
    return result;
};

/**
 * Возвращает Set ID задач, которые принадлежат партиям,
 * содержащим хотя бы одну задачу с замедленным охлаждением.
 */
export const getTaskIdsInSlowCoolingBatches = (
    brackets: BatchBracket[],
): Set<string> => {
    const result = new Set<string>();
    for (const b of brackets) {
        if (b.hasSlowCooling) {
            for (const id of b.taskIds) {
                result.add(id);
            }
        }
    }
    return result;
};

/**
 * Находит скобку, к которой относится задача.
 * Возвращает null, если задача не принадлежит ни одной партии
 * (setup, downtime, «Замывка», «Выходной»).
 */
export const findBracketForTask = (
    task: TaskData,
    brackets: BatchBracket[],
): BatchBracket | null => {
    if (!task.batch_id) return null;
    return brackets.find((b) => b.batchId === task.batch_id) || null;
};

/**
 * Находит скобку по ID партии.
 */
export const findBracketByBatchId = (
    batchId: string,
    brackets: BatchBracket[],
): BatchBracket | null => {
    return brackets.find((b) => b.batchId === batchId) || null;
};

/**
 * Возвращает Set ID задач, которые НЕ принадлежат ни одной партии
 * (setup, downtime, «Замывка», «Выходной»).
 *
 * Используется, чтобы понять, какие задачи не нужно охватывать
 * скобками и не нужно затемнять при подсветке партии.
 */
export const getNonBatchTaskIds = (tasks: TaskData[]): Set<string> => {
    const result = new Set<string>();
    for (const t of tasks) {
        if (t.item_type && t.item_type !== 'task') {
            result.add(t.id);
            continue;
        }
        if (!t.batch_id || NON_BATCH_VALUES.has(t.batch_id)) {
            result.add(t.id);
        }
    }
    return result;
};