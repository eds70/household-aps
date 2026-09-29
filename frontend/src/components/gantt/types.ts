// frontend/src/components/gantt/types.ts
/**
 * Реэкспорт типов для компонентов диаграммы Ганта.
 *
 * Итерация 13.17: типы вынесены в глобальный types/index.ts,
 * чтобы их могли использовать хуки (hooks/useTaskResize.ts,
 * hooks/useCascadeMove.ts) без зависимости от components/.
 *
 * Плюс локальные типы для vis-timeline (GanttItem, GanttGroup,
 * ViewportState), которые не являются доменными и нужны только
 * на фронте.
 */

export type {
    TaskData,
    CoolingMode,
    CzStatus,
} from '../../types';

// ==========================================
// Итерация 13.17: типы для vis-timeline
// ==========================================

/** Item для vis-timeline. */
export interface GanttItem {
    id: string;
    group: string;
    start: string;
    end: string;
    content?: string;
    title?: string;
    style?: string;
    className?: string;
}

/** Group для vis-timeline. */
export interface GanttGroup {
    id: string;
    content: string;
    className?: string;
}

/** Viewport (сохранённый диапазон). */
export interface ViewportState {
    start: string;
    end: string;
}