// frontend/src/utils/ganttSetups.ts
/**
 * Генерация setup-задач (🧼 Замывка) между операциями
 * на одном оборудовании (Итерация 13.17).
 *
 * Вынесено из GanttPage.tsx без изменения логики.
 */
import type {TaskData} from '../types';
import {MAX_SETUP_GAP_MINUTES, SETUP_DURATION_DIFF_PF, SETUP_DURATION_SAME_PF,} from '../components/gantt/constants';
import {isWeekendDate} from './ganttHelpers';

/**
 * Генерирует setup-задачи между последовательными задачами
 * на одном оборудовании.
 *
 * Логика:
 *  - Смотрим пары последовательных задач на одном equipment_id.
 *  - Если gap между end первой и start второй:
 *      - > 0 и <= MAX_SETUP_GAP_MINUTES,
 *      - партии разные,
 *      - не выходной,
 *    то создаём setup-задачу.
 *  - Длительность setup: 30 мин (same PF) или 90 мин (diff PF),
 *    но не больше, чем gap.
 *
 * Setup-задачи НЕ сохраняются в БД — они вычисляются на лету.
 */
export const generateSetups = (tasksData: TaskData[]): TaskData[] => {
    const setups: TaskData[] = [];
    const byEquipment: Record<string, TaskData[]> = {};

    tasksData.forEach((task) => {
        if (!byEquipment[task.equipment_id]) {
            byEquipment[task.equipment_id] = [];
        }
        byEquipment[task.equipment_id].push(task);
    });

    Object.entries(byEquipment).forEach(([eqId, eqTasks]) => {
        eqTasks.sort(
            (a, b) =>
                new Date(a.start).getTime() - new Date(b.start).getTime(),
        );

        for (let i = 0; i < eqTasks.length - 1; i++) {
            const curr = eqTasks[i];
            const next = eqTasks[i + 1];

            // Одна и та же партия — не считаем как setup
            if (curr.batch_id === next.batch_id) continue;

            const gapMinutes = Math.round(
                (new Date(next.start).getTime() -
                    new Date(curr.end).getTime()) / 60000,
            );

            if (gapMinutes <= 0 || gapMinutes > MAX_SETUP_GAP_MINUTES) continue;

            const setupType =
                curr.product_id === next.product_id ? 'same_pf' : 'diff_pf';
            const nominalDuration =
                setupType === 'same_pf'
                    ? SETUP_DURATION_SAME_PF
                    : SETUP_DURATION_DIFF_PF;
            const actualDuration = Math.min(nominalDuration, gapMinutes);

            const setupEnd = new Date(next.start);
            const setupStart = new Date(
                setupEnd.getTime() - actualDuration * 60000,
            );

            // Пропускаем setup, если он попадает на выходной
            if (isWeekendDate(setupStart) || isWeekendDate(setupEnd)) continue;

            setups.push({
                id: `setup_${curr.id}_${next.id}`,
                batch_id: 'Замывка',
                operation_name: '🧼 Замывка',
                equipment_id: eqId,
                product_id: '—',
                start: setupStart.toISOString(),
                end: setupEnd.toISOString(),
                duration_minutes: actualDuration,
                item_type: 'setup',
                setup_type: setupType,
            });
        }
    });

    return setups;
};