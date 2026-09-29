// frontend/src/components/gantt/constants.ts
/**
 * Константы для диаграммы Ганта (Итерация 13.17).
 *
 * Вынесено из GanttPage.tsx, чтобы переиспользовать в утилитах
 * и компонентах (GanttToolbar, GanttFiltersBar, TaskContextMenu).
 */

// ==========================================
// ЦВЕТА ЗАДАЧ ПО РОЛИ
// ==========================================

export const ROLE_COLORS: Record<string, string> = {
    REACTOR_OP: '#3498db',
    TANK_TRANSFER: '#e67e22',
    LINE_FILL: '#27ae60',
    WASH: '#9b59b6',
    SETUP: '#95a5a6',
    LAB_BLOCK: '#f1c40f',
};

export const ROLE_COLORS_DEFAULT = '#95a5a6';

// ==========================================
// ЦВЕТА СВЯЗЕЙ (Итерация 13.6)
// ==========================================

export type LinkColorKey =
    | 'same_row'
    | 'to_tank'
    | 'to_line'
    | 'to_wash'
    | 'direct';

export const LINK_COLORS: Record<LinkColorKey, string> = {
    same_row: '#7f8c8d',
    to_tank: '#e74c3c',
    to_line: '#3498db',
    to_wash: '#9b59b6',
    direct: '#27ae60',
};

export const HOVER_COLOR = '#e67e22';

// ==========================================
// ЦВЕТА ПРОБЛЕМНЫХ ЗАДАЧ
// ==========================================

export const PROBLEM_COLORS = {
    blocked: {
        bg: '#ffebee',
        border: '#e74c3c',
    },
    coolingSlow: {
        bg: '#fff3e0',
        border: '#e67e22',
    },
    czIncomplete: {
        bg: '#e3f2fd',
        border: '#1976d2',
    },
};

// ==========================================
// НАСТРОЙКИ SETUP (ЗАМЫВКА)
// ==========================================

export const MAX_SETUP_GAP_MINUTES = 4 * 60;   // 4 часа
export const SETUP_DURATION_SAME_PF = 30;       // 30 мин между одинаковыми ПФ
export const SETUP_DURATION_DIFF_PF = 90;       // 90 мин между разными ПФ

// ==========================================
// НАСТРОЙКИ ZOOM / ВРЕМЕНИ
// ==========================================

export const ZOOM_MIN_MS = 1000 * 60 * 60 * 2;      // 2 часа
export const ZOOM_MAX_MS = 1000 * 60 * 60 * 24 * 90; // 90 дней

export const PAN_FACTOR = 0.5;
export const ZOOM_IN_FACTOR = 0.7;
export const ZOOM_OUT_FACTOR = 1.4;

// ==========================================
// СНАП ПРИ ПЕРЕТАСКИВАНИИ
// ==========================================

/** Шаг сетки при snap (15 минут). */
export const SNAP_MS = 1000 * 60 * 15;

// ==========================================
// ЛИМИТЫ
// ==========================================

/** Минимальная длительность задачи (мин). */
export const MIN_TASK_DURATION_MINUTES = 5;

/** Максимальная длительность задачи (мин). */
export const MAX_TASK_DURATION_MINUTES = 24 * 60;

// ==========================================
// СПЕЦИАЛЬНЫЕ batch_id, КОТОРЫЕ НЕ ЯВЛЯЮТСЯ ПАРТИЯМИ
// ==========================================

export const NON_BATCH_VALUES = new Set<string>(['Замывка', 'Выходной']);

// ==========================================
// localStorage КЛЮЧИ
// ==========================================

export const STORAGE_KEYS = {
    minimap: 'aps_gantt_minimap',
    showDependencies: 'aps_gantt_show_dependencies',
    showAllDependencies: 'aps_gantt_show_all_dependencies',
    viewportPrefix: 'aps_gantt_viewport_',
    expandedGroupsPrefix: 'aps_gantt_expanded_groups_',
};

export const getViewportStorageKey = (versionId: string | null): string =>
    `${STORAGE_KEYS.viewportPrefix}${versionId || 'draft'}`;