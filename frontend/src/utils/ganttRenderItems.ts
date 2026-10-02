// frontend/src/utils/ganttRenderItems.ts
/**
 * Построение items и groups для vis-timeline (Итерация 13.17 + 13.18 + 14.1).
 *
 * Вынесено из GanttPage.tsx. Чистая функция без побочных эффектов:
 *  - принимает отфильтрованные задачи и оборудование;
 *  - возвращает items для основного Timeline и миникарты,
 *    groups для основного Timeline и миникарты.
 *
 * Итерация 13.18: улучшена визуализация is_pinned (📌 иконка,
 * светлый фон, плотная синяя рамка).
 *
 * Итерация 14.1: добавлен режим группировки groupByMode:
 *   - 'equipment' — groups = оборудование (как было).
 *   - 'batch' — groups = партии (batch_id), внутри каждой группы
 *     все операции партии. Окраска задач — по equipment_id.
 */

import type {GroupByMode, TaskData} from '../types';
import type {GanttGroup, GanttItem} from '../components/gantt/types';
import {NON_BATCH_VALUES, PROBLEM_COLORS, ROLE_COLORS, ROLE_COLORS_DEFAULT,} from '../components/gantt/constants';
import {generateSetups} from './ganttSetups';
import {type BackgroundItem, generateWeekendBackgrounds,} from './ganttDowntimes';
import {getBatchColor, getBatchLabel} from './ganttBatchColors';

export interface BuildGanttItemsOptions {
    /** Задачи после фильтрации (только реальные task, без setup/downtime). */
    filteredTasks: TaskData[];
    /** Список оборудования (из GanttResponse.equipment_list). */
    equipment: string[];
    /** Показывать ли связи (для hover-подсказки в tooltip). */
    showDependencies: boolean;
    /** Показывать ли все связи (для hover-подсказки в tooltip). */
    showAllDependencies: boolean;
    /** Показывать ли setup-задачи. */
    showSetups: boolean;
    /** Показывать ли фоновые полосы выходных. */
    showDowntimes: boolean;
    /**
     * Итерация 14.1: режим группировки.
     *   - 'equipment' — groups = оборудование.
     *   - 'batch' — groups = партии (batch_id).
     */
    groupByMode: GroupByMode;
}

export interface BuildGanttItemsResult {
    /** Items для основного Timeline (задачи + setup + weekend backgrounds). */
    items: any[];
    /** Groups для основного Timeline. */
    groups: GanttGroup[];
    /** Items для миникарты (только задачи, без setup/downtime). */
    minimapItems: GanttItem[];
    /** Groups для миникарты (пустые content). */
    minimapGroups: GanttGroup[];
    /** Setup-задачи (для отладки / подсчёта). */
    setups: TaskData[];
    /** Weekend backgrounds (для отладки / подсчёта). */
    weekendBackgrounds: BackgroundItem[];
}

/**
 * Строит items/groups для основного Timeline и миникарты.
 *
 * @returns Объект со всеми данными для рендера.
 */
export const buildGanttItems = (
    options: BuildGanttItemsOptions,
): BuildGanttItemsResult => {
    const {
        filteredTasks,
        equipment,
        showDependencies,
        showAllDependencies,
        showSetups,
        showDowntimes,
        groupByMode,
    } = options;

    // ==========================================
    // 1. Setup и weekend backgrounds
    // ==========================================
    const setups = showSetups ? generateSetups(filteredTasks) : [];
    const weekendBackgrounds = showDowntimes
        ? generateWeekendBackgrounds(filteredTasks)
        : [];

    // ==========================================
    // 2. Task items
    // ==========================================
    const taskItems: TaskData[] = [...filteredTasks, ...setups];

    // Пересчитываем equipment_id для каждой задачи в зависимости от режима
    const itemsArray: GanttItem[] = taskItems.map((task) => {
        const groupId = resolveGroupId(task, groupByMode);
        return buildSingleTaskItem(task, groupId, groupByMode, {
            showDependencies,
            showAllDependencies,
        });
    });

    // ==========================================
    // 3. Groups для основного Timeline
    // ==========================================
    const groupsArray: GanttGroup[] = buildGroups(
        filteredTasks,
        equipment,
        groupByMode,
    );

    // ==========================================
    // 4. Items и groups для миникарты
    // ==========================================
    const minimapItems: GanttItem[] = itemsArray.map((item) => ({
        id: item.id,
        group: item.group,
        start: item.start,
        end: item.end,
        style: item.style,
        className: item.className,
    }));

    const minimapGroups: GanttGroup[] = groupsArray.map((g) => ({
        id: g.id,
        content: '',
    }));

    // ==========================================
    // 5. Итоговый items для основного Timeline
    // ==========================================
    const items: any[] = [...itemsArray, ...weekendBackgrounds];

    return {
        items,
        groups: groupsArray,
        minimapItems,
        minimapGroups,
        setups,
        weekendBackgrounds,
    };
};

// ==========================================
// ОПРЕДЕЛЕНИЕ ГРУППЫ ЗАДАЧИ
// ==========================================

/**
 * Возвращает ID группы (строки) для задачи в зависимости от режима.
 *
 * В режиме 'equipment' — это equipment_id (как было).
 * В режиме 'batch' — это batch_id, с fallback на equipment_id
 * для setup/downtime (у них нет batch_id).
 */
const resolveGroupId = (
    task: TaskData,
    mode: GroupByMode,
): string => {
    if (mode === 'equipment') {
        return task.equipment_id;
    }

    // mode === 'batch'
    // Для setup / downtime — своя группа (по equipment_id)
    if (task.item_type === 'setup') {
        return `__setup__${task.equipment_id}`;
    }
    if (task.item_type === 'downtime') {
        return `__downtime__${task.equipment_id}`;
    }

    // Для реальных задач — batch_id
    if (task.batch_id && !NON_BATCH_VALUES.has(task.batch_id)) {
        return task.batch_id;
    }

    // Fallback: партия не определена — используем equipment_id
    return task.equipment_id;
};

// ==========================================
// ПОСТРОЕНИЕ GROUPS
// ==========================================

/**
 * Строит список groups для vis-timeline в зависимости от режима.
 *
 * В режиме 'equipment' — группы = список оборудования.
 * В режиме 'batch' — группы = список партий (уникальные batch_id),
 * отсортированные по времени первой операции.
 */
const buildGroups = (
    filteredTasks: TaskData[],
    equipment: string[],
    mode: GroupByMode,
): GanttGroup[] => {
    if (mode === 'equipment') {
        // Классический режим: группы = оборудование
        return equipment.map((eq) => ({
            id: eq,
            content: `<b>${eq}</b>`,
        }));
    }

    // mode === 'batch'
    // Собираем уникальные batch_id и их время начала
    const batchInfo = new Map<
        string,
        {startMs: number; productName: string | null}
    >();

    for (const task of filteredTasks) {
        if (!task.batch_id || NON_BATCH_VALUES.has(task.batch_id)) continue;
        if (task.item_type && task.item_type !== 'task') continue;

        const startMs = new Date(task.start).getTime();
        const existing = batchInfo.get(task.batch_id);

        if (!existing) {
            batchInfo.set(task.batch_id, {
                startMs,
                productName:
                    task.product_id && task.product_id !== '—'
                        ? task.product_id
                        : null,
            });
        } else if (startMs < existing.startMs) {
            existing.startMs = startMs;
            if (!existing.productName && task.product_id && task.product_id !== '—') {
                existing.productName = task.product_id;
            }
        }
    }

    // Сортируем партии по времени начала
    const sortedBatches = Array.from(batchInfo.entries()).sort(
        (a, b) => a[1].startMs - b[1].startMs,
    );

    const batchGroups: GanttGroup[] = sortedBatches.map(
        ([batchId, info]) => {
            const color = getBatchColor(batchId);
            const label = getBatchLabel(batchId, info.productName);
            return {
                id: batchId,
                content: `
                    <div style="display: flex; align-items: center; gap: 6px;">
                        <span style="display: inline-block; width: 10px; height: 10px; border-radius: 2px; background-color: ${color}; flex-shrink: 0;"></span>
                        <b style="font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${label}</b>
                    </div>
                `,
            };
        },
    );

    return batchGroups;
};

// ==========================================
// ВНУТРЕННИЕ: одна задача → item
// ==========================================

interface BuildSingleTaskOptions {
    showDependencies: boolean;
    showAllDependencies: boolean;
}

const buildSingleTaskItem = (
    task: TaskData,
    groupId: string,
    groupByMode: GroupByMode,
    opts: BuildSingleTaskOptions,
): GanttItem => {
    const itemType = task.item_type || 'task';
    let style = '';
    let title = '';
    let className = '';

    if (itemType === 'task') {
        const result = buildTaskStyle(task, groupByMode, opts);
        style = result.style;
        title = result.title;
        className = result.className;
    } else if (itemType === 'setup') {
        const setupColor =
            task.setup_type === 'same_pf' ? '#95a5a6' : '#e67e22';
        style = `background-color: ${setupColor}25; border: 2px dashed ${setupColor}; border-radius: 4px;`;
        className = 'item-setup';
        title = `<div style="padding: 8px; min-width: 280px;"><b>🧼 Замывка</b><br>${task.duration_minutes} мин</div>`;
    } else if (itemType === 'downtime') {
        style = `background-color: #9b59b620; border: 1px solid #9b59b6; border-radius: 4px;`;
        className = 'item-downtime';
        title = `<div style="padding: 8px; min-width: 280px;"><b>📅 ${task.operation_name}</b><br>${task.duration_minutes} мин</div>`;
    }

    // Иконки в содержимом item
    const pinIcon = task.is_pinned ? '📌 ' : '';
    const blockedIcon = task.is_lab_blocked ? '🔒 ' : '';
    const slowCoolingIcon = task.cooling_mode === 'slow' ? '⏳ ' : '';
    const czIcon =
        task.task_role === 'LINE_FILL' &&
        task.cz_status &&
        task.cz_status !== 'COMPLETED'
            ? '📷 '
            : '';

    const shortName =
        task.operation_name.length > 24
            ? task.operation_name.substring(0, 22) + '…'
            : task.operation_name;

    // Приоритет цвета текста
    const contentColor = task.is_pinned
        ? '#1976d2'
        : task.is_lab_blocked
            ? '#e74c3c'
            : task.cooling_mode === 'slow'
                ? '#e67e22'
                : '#2c3e50';

    return {
        id: task.id,
        group: groupId,
        content: `
            <div style="padding: 4px; font-size: 11px;">
              <div style="font-weight: bold; color: ${contentColor}; margin-bottom: 2px;">
                ${pinIcon}${blockedIcon}${slowCoolingIcon}${czIcon}${shortName}
              </div>
              <div style="font-size: 10px; color: #555;">${task.duration_minutes} мин</div>
            </div>
          `,
        start: task.start,
        end: task.end,
        style,
        title,
        className,
    };
};

// ==========================================
// СТИЛЬ И TOOLTIP ДЛЯ "TASK"
// ==========================================

interface TaskStyleResult {
    style: string;
    title: string;
    className: string;
}

const buildTaskStyle = (
    task: TaskData,
    groupByMode: GroupByMode,
    opts: BuildSingleTaskOptions,
): TaskStyleResult => {
    const isBlocked = task.is_lab_blocked === true;
    const isSlowCooling = task.cooling_mode === 'slow';
    const isCzIncomplete =
        task.task_role === 'LINE_FILL' &&
        !!task.cz_status &&
        task.cz_status !== 'COMPLETED';
    const isPinned = task.is_pinned === true;

    let style = '';
    let className = '';

    // ==========================================
    // Приоритет стилей:
    //   1. is_pinned
    //   2. isBlocked
    //   3. isSlowCooling
    //   4. isCzIncomplete
    //   5. обычный (цвет по роли или по оборудованию)
    // ==========================================
    if (isPinned) {
        style =
            `background-color: ${PROBLEM_COLORS.pinned.bg}; ` +
            `border: 2px solid ${PROBLEM_COLORS.pinned.border}; ` +
            `border-left: 6px solid ${PROBLEM_COLORS.pinned.border}; ` +
            `border-radius: 4px; ` +
            `box-shadow: 0 0 4px rgba(25, 118, 210, 0.35);`;
        className = 'item-pinned';
    } else if (isBlocked) {
        style = `background-color: ${PROBLEM_COLORS.blocked.bg}; border: 2px solid ${PROBLEM_COLORS.blocked.border}; border-radius: 4px;`;
        className = 'item-blocked';
    } else if (isSlowCooling) {
        style = `background-color: ${PROBLEM_COLORS.coolingSlow.bg}; border: 2px dashed ${PROBLEM_COLORS.coolingSlow.border}; border-radius: 4px;`;
        className = 'item-cooling-slow';
    } else if (isCzIncomplete) {
        style = `background-color: ${PROBLEM_COLORS.czIncomplete.bg}; border: 2px dotted ${PROBLEM_COLORS.czIncomplete.border}; border-radius: 4px;`;
        className = 'item-cz-incomplete';
    } else {
        // Обычный стиль — зависит от режима
        if (groupByMode === 'batch') {
            // В режиме «По партиям» — цвет задачи по оборудованию
            const eqColor = getEquipmentColor(task.equipment_id);
            style = `background-color: ${eqColor}25; border-left: 4px solid ${eqColor}; border-radius: 4px;`;
        } else {
            // В режиме «По оборудованию» — цвет по роли (как было)
            const roleColor =
                ROLE_COLORS[task.task_role || ''] || ROLE_COLORS_DEFAULT;
            style = `background-color: ${roleColor}25; border-left: 4px solid ${roleColor}; border-radius: 4px;`;
        }
    }

    // ==========================================
    // Бейджи для tooltip
    // ==========================================

    const pinnedBadge = isPinned
        ? `<div style="color: #1976d2; font-weight: bold; margin-top: 4px;">📌 ЗАДАЧА ЗАКРЕПЛЕНА</div>` +
        `<div style="color: #1976d2; font-size: 11px; margin-top: 2px;">Перемещение запрещено. Изменение длительности разрешено.</div>`
        : '';

    const blockedBadge = isBlocked
        ? `<div style="color: #e74c3c; font-weight: bold; margin-top: 4px;">🔒 ЗАБЛОКИРОВАНО ЛАБОРАТОРИЕЙ</div>${
            task.lab_block_reason
                ? `<div style="color: #e74c3c; font-size: 11px; margin-top: 2px;">Причина: ${task.lab_block_reason}</div>`
                : ''
        }`
        : '';

    let coolingBadge = '';
    if (task.cooling_mode === 'slow') {
        coolingBadge = `<div style="color: #e67e22; font-weight: bold; margin-top: 4px;">⏳ ОХЛАЖДЕНИЕ ЗАМЕДЛЕНО (×1.3)</div>`;
    } else if (task.cooling_mode === 'fast') {
        coolingBadge = `<div style="color: #3498db; font-size: 11px; margin-top: 4px;">❄️ Охлаждение в обычном режиме</div>`;
    }

    let czBadge = '';
    if (task.task_role === 'LINE_FILL' && task.cz_status) {
        const czLabel =
            task.cz_status === 'COMPLETED'
                ? '🟢 ЧЗ завершено'
                : task.cz_status === 'IN_PROGRESS'
                    ? '🔵 ЧЗ в работе'
                    : task.cz_status === 'PENDING'
                        ? '🟡 ЧЗ ожидает'
                        : '⚪ ЧЗ не требуется';
        czBadge = `<div style="margin-top: 4px; font-size: 11px;"><b>${czLabel}</b>${
            task.cz_marked_qty != null
                ? `<br>Промаркировано: ${task.cz_marked_qty}`
                : ''
        }</div>`;
    }

    const hoverHint =
        opts.showDependencies && !opts.showAllDependencies
            ? `<div style="margin-top: 6px; padding-top: 6px; border-top: 1px solid #ecf0f1; color: #e67e22; font-size: 11px;">💡 Наведите — появятся связи</div>`
            : '';

    // ==========================================
    // Заголовок tooltip
    // ==========================================
    const titleColor = isPinned
        ? '#1976d2'
        : isBlocked
            ? '#e74c3c'
            : '#2c3e50';

    const titlePrefix =
        (isPinned ? '📌 ' : '') +
        (isBlocked ? '🔒 ' : '') +
        (isSlowCooling ? '⏳ ' : '');

    // В режиме 'batch' — показываем партию как первую строку
    const batchLine =
        groupByMode === 'batch' && task.batch_id && !NON_BATCH_VALUES.has(task.batch_id)
            ? `<b>Партия:</b> ${getBatchLabel(task.batch_id, task.product_id)}<br>`
            : '';

    const title = `
            <div style="padding: 8px; min-width: 280px;">
              <b style="font-size: 14px; color: ${titleColor};">${titlePrefix}${task.operation_name}</b><br>
              <hr style="margin: 8px 0; border: none; border-top: 1px solid #ecf0f1;">
              <div style="font-size: 12px; line-height: 1.6;">
                ${batchLine}
                <b>Оборудование:</b> ${task.equipment_id}<br>
                <b>Роль:</b> ${task.task_role || '—'}<br>
                <b>Длительность:</b> ${task.duration_minutes} мин<br>
                <b>Начало:</b> ${new Date(task.start).toLocaleString('ru-RU')}<br>
                <b>Конец:</b> ${new Date(task.end).toLocaleString('ru-RU')}
                ${pinnedBadge}
                ${blockedBadge}
                ${coolingBadge}
                ${czBadge}
                ${hoverHint}
              </div>
            </div>
          `;

    return {style, title, className};
};

// ==========================================
// ЦВЕТ ОБОРУДОВАНИЯ (для режима 'batch')
// ==========================================

/**
 * Возвращает детерминированный цвет для оборудования.
 *
 * В режиме «По партиям» все задачи партии в одной строке,
 * поэтому нужно визуально различать на каком оборудовании
 * идёт каждая операция.
 *
 * Используем ту же палитру, что и для партий, но с другим
 * хешем (чтобы цвета не совпадали с цветами партий случайно).
 */
const EQUIPMENT_COLOR_PALETTE: Record<string, string> = {
    // Реакторы — синяя гамма
    REACTOR_1: '#3498db',
    REACTOR_2: '#2980b9',
    REACTOR_3: '#1f618d',
    REACTOR_4: '#1a5276',
    // Линии — зелёная гамма
    LINE_1: '#27ae60',
    LINE_2: '#229954',
    LINE_3: '#1e8449',
    // Танки — оранжевая гамма
    TANK_1: '#e67e22',
    TANK_2: '#d35400',
    // Бойлер — красный
    BOILER: '#e74c3c',
    // Fallback
    __default__: '#95a5a6',
};

/**
 * Возвращает цвет для оборудования по его имени (id).
 *
 * Используется в режиме 'batch', чтобы видеть, на каком
 * оборудовании идёт каждая операция.
 */
const getEquipmentColor = (equipmentId: string): string => {
    if (!equipmentId) return EQUIPMENT_COLOR_PALETTE.__default__;
    return (
        EQUIPMENT_COLOR_PALETTE[equipmentId] ||
        EQUIPMENT_COLOR_PALETTE.__default__
    );
};