// frontend/src/utils/ganttDowntimes.ts
/**
 * Генерация фоновых полос выходных дней на Ганте
 * (Итерация 13.10, вынесено в отдельный модуль в 13.17).
 *
 * Фоновые полосы — это элементы vis-timeline типа 'background',
 * которые рисуются под задачами в виде вертикальных полос.
 */
import type {TaskData} from '../types';

export interface BackgroundItem {
    id: string;
    type: 'background';
    start: string;
    end: string;
    className?: string;
    style?: string;
    content?: string;
}

/**
 * Генерирует фоновые полосы для выходных дней (сб, вс),
 * попадающих в диапазон задач.
 *
 * Логика:
 *  - Определяем min(start) и max(end) среди задач.
 *  - Идём по дням, для каждого сб/вс создаём background-полосу
 *    от начала до конца дня.
 */
export const generateWeekendBackgrounds = (
    tasksData: TaskData[],
): BackgroundItem[] => {
    if (tasksData.length === 0) return [];

    const weekends: BackgroundItem[] = [];
    const startDate = new Date(
        Math.min(...tasksData.map((t) => new Date(t.start).getTime())),
    );
    const endDate = new Date(
        Math.max(...tasksData.map((t) => new Date(t.end).getTime())),
    );
    startDate.setHours(0, 0, 0, 0);
    endDate.setHours(23, 59, 59, 999);

    const current = new Date(startDate);
    while (current <= endDate) {
        const dayOfWeek = current.getDay();
        if (dayOfWeek === 0 || dayOfWeek === 6) {
            const weekendStart = new Date(current);
            const weekendEnd = new Date(current);
            weekendEnd.setHours(23, 59, 59, 999);

            weekends.push({
                id: `weekend_bg_${current.toISOString().split('T')[0]}`,
                type: 'background',
                start: weekendStart.toISOString(),
                end: weekendEnd.toISOString(),
                className: 'weekend-background',
                style:
                    'background-color: rgba(155, 89, 182, 0.10); ' +
                    'border-left: 1px dashed rgba(155, 89, 182, 0.4); ' +
                    'border-right: 1px dashed rgba(155, 89, 182, 0.4);',
            });
        }
        current.setDate(current.getDate() + 1);
    }
    return weekends;
};