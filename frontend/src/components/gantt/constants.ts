// frontend/src/components/gantt/constants.ts
/**
 * Константы для диаграммы Ганта (Итерация 13.17).
 *
 * Вынесено из GanttPage.tsx, чтобы переиспользовать в утилитах
 * и компонентах (GanttToolbar, GanttFiltersBar, TaskContextMenu).
 *
 * Итерация 14.1: добавлены константы для режимов группировки
 * (GroupByMode) и цветов скобок партий.
 *
 * Итерация 14.1 (fix): скобки партий теперь рисуются БЕЗ заливки —
 * только пунктирный контур + ярлык-плашка.
 *
 * Итерация 14.1 (fix #2): переход на Вариант D —
 *   - по умолчанию только ярлыки над первыми задачами;
 *   - контур рисуется только для выбранной партии;
 *   - остальные задачи затемняются (opacity 0.4);
 *   - SVG монтируется в .vis-panel.vis-center
 *     (без оси времени и левой колонки).
 *   Добавлены новые константы: GANTT_AXIS_HEIGHT_PX,
 *   DIMMED_TASK_OPACITY, BATCH_LABEL_MAX_LENGTH.
 *
 * Итерация 14.1 (fix #3): при выборе партии ярлыки остальных
 *   партий тоже затемняются (opacity 0.25 + saturate 0.4).
 *   Исключение — заблокированные партии (их ярлыки всегда яркие).
 *   Добавлена константа DIMMED_LABEL_CLASS.
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

/**
 * Итерация 14.1: цвет связи МЕЖДУ партиями (в режиме «По партиям»).
 */
export const INTER_BATCH_LINK_COLOR = '#e74c3c';

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
    pinned: {
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
    groupByMode: 'aps_gantt_group_by_mode',
    showBatchBrackets: 'aps_gantt_show_batch_brackets',
};

export const getViewportStorageKey = (versionId: string | null): string =>
    `${STORAGE_KEYS.viewportPrefix}${versionId || 'draft'}`;

// ==========================================
// ИТЕРАЦИЯ 14.1: РЕЖИМЫ ГРУППИРОВКИ
// ==========================================

/**
 * Значение по умолчанию для режима группировки.
 */
export const DEFAULT_GROUP_BY_MODE = 'equipment' as const;

/**
 * Значение по умолчанию для показа скобок партий.
 */
export const DEFAULT_SHOW_BATCH_BRACKETS = true;

/**
 * Палитра цветов для скобок партий.
 */
export const BATCH_COLOR_PALETTE: string[] = [
    '#e74c3c',
    '#3498db',
    '#27ae60',
    '#9b59b6',
    '#e67e22',
    '#16a085',
    '#c0392b',
    '#2980b9',
    '#8e44ad',
    '#d35400',
    '#27ae60',
    '#7f8c8d',
];

// ==========================================
// ИТЕРАЦИЯ 14.1 (fix #2): СКОВКИ ПАРТИЙ — ВАРИАНТ D
// ==========================================
// Дизайн:
//   - По умолчанию: только ярлыки над первыми задачами.
//   - Контур рисуется только для ВЫБРАННОЙ партии.
//   - Остальные задачи затемняются при выборе.
// ==========================================

/**
 * Толщина линии контура скобки (в пикселях).
 */
export const BATCH_BRACKET_STROKE_WIDTH = 2;

/**
 * Толщина линии контура при подсветке.
 */
export const BATCH_BRACKET_STROKE_WIDTH_HIGHLIGHTED = 3;

/**
 * Прозрачность контура скобки.
 */
export const BATCH_BRACKET_STROKE_OPACITY = 0.7;

/**
 * Прозрачность контура при подсветке.
 */
export const BATCH_BRACKET_STROKE_OPACITY_HIGHLIGHTED = 1.0;

/**
 * Штриховой паттерн для контура (при выборе партии).
 * Пустая строка = сплошная линия.
 */
export const BATCH_BRACKET_DASH_ARRAY = '';
export const BATCH_BRACKET_DASH_ARRAY_HIGHLIGHTED = '';

/**
 * Отступ контура от задач (в пикселях).
 */
export const BATCH_BRACKET_PADDING_PX = 4;

/**
 * Высота ярлыка-плашки (полоса с названием партии), в пикселях.
 */
export const BATCH_BRACKET_LABEL_HEIGHT = 18;

/**
 * Горизонтальный padding внутри ярлыка, в пикселях.
 */
export const BATCH_BRACKET_LABEL_PADDING_X = 6;

/**
 * Вертикальный отступ ярлыка от верхней границы задачи, в пикселях.
 */
export const BATCH_BRACKET_LABEL_OFFSET_Y = 3;

/**
 * Шрифт ярлыка (CSS font-family).
 */
export const BATCH_BRACKET_LABEL_FONT_FAMILY =
    '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';

/**
 * Размер шрифта ярлыка (в пикселях).
 */
export const BATCH_BRACKET_LABEL_FONT_SIZE = 11;

/**
 * Цвет текста ярлыка.
 */
export const BATCH_BRACKET_LABEL_TEXT_COLOR = '#ffffff';

/**
 * Цвет контура для партий с заблокированными задачами.
 */
export const BATCH_BRACKET_BLOCKED_COLOR = '#e74c3c';

/**
 * Максимальная длина текста ярлыка (в символах).
 */
export const BATCH_LABEL_MAX_LENGTH = 28;

/**
 * Z-index для SVG-слоя со скобками партий.
 */
export const BATCH_BRACKETS_Z_INDEX = 2;

/**
 * Максимальное количество ярлыков партий, отображаемых одновременно.
 */
export const MAX_VISIBLE_BATCH_BRACKETS = 30;

/**
 * Высота верхней панели (оси времени) в vis-timeline, в пикселях.
 * (Не используется в текущей версии — оставлено на будущее.)
 */
export const GANTT_AXIS_HEIGHT_PX = 50;

/**
 * Прозрачность задач, НЕ принадлежащих выбранной партии.
 */
export const DIMMED_TASK_OPACITY = 0.4;

/**
 * CSS-класс для затемнённых задач.
 */
export const DIMMED_TASK_CLASS = 'task-dimmed';

/**
 * CSS-класс для задач выбранной партии.
 */
export const HIGHLIGHTED_TASK_CLASS = 'task-batch-highlighted';

/**
 * Итерация 14.1 (fix #3): CSS-класс для затемнённых ярлыков партий.
 *
 * При выборе партии (highlightedBatchId) ярлыки всех остальных
 * партий получают этот класс. Исключение — ярлыки заблокированных
 * партий (у них hasBlockedTasks === true): они всегда яркие.
 *
 * Визуально: opacity 0.25 + filter saturate(0.4).
 */
export const DIMMED_LABEL_CLASS = 'gantt-batch-label-dimmed';