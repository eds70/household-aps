// frontend/src/utils/ganttRenderItems.ts
/**
 * Построение items и groups для vis-timeline (Итерация 13.17 + 13.18).
 *
 * Вынесено из GanttPage.tsx. Чистая функция без побочных эффектов:
 *  - принимает отфильтрованные задачи и оборудование;
 *  - возвращает items для основного Timeline и миникарты,
 *    groups для основного Timeline и миникарты.
 *
 * Итерация 13.18: улучшена визуализация is_pinned (📌 иконка,
 * светлый фон, плотная синяя рамка).
 */
import type {TaskData} from '../types';
import type {GanttGroup, GanttItem} from '../components/gantt/types';
import {PROBLEM_COLORS, ROLE_COLORS, ROLE_COLORS_DEFAULT,} from '../components/gantt/constants';
import {generateSetups} from './ganttSetups';
import {type BackgroundItem, generateWeekendBackgrounds,} from './ganttDowntimes';

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

    const itemsArray: GanttItem[] = taskItems.map((task) => {
        return buildSingleTaskItem(task, {
            showDependencies,
            showAllDependencies,
        });
    });

    // ==========================================
    // 3. Groups для основного Timeline
    // ==========================================
    const groupsArray: GanttGroup[] = equipment.map((eq) => ({
        id: eq,
        content: `<b>${eq}</b>`,
    }));

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

    const minimapGroups: GanttGroup[] = equipment.map((eq) => ({
        id: eq,
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
// ВНУТРЕННИЕ
// ==========================================

interface BuildSingleTaskOptions {
    showDependencies: boolean;
    showAllDependencies: boolean;
}

const buildSingleTaskItem = (
    task: TaskData,
    opts: BuildSingleTaskOptions,
): GanttItem => {
    const itemType = task.item_type || 'task';
    let style = '';
    let title = '';
    let className = '';

    if (itemType === 'task') {
        const {style: s, title: t, className: c} = buildTaskStyle(task, opts);
        style = s;
        title = t;
        className = c;
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

    // Итерация 13.18: pin-иконка идёт первой (важнее всего)
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

    // Приоритет цвета текста: pinned → blocked → slow cooling → обычный
    const contentColor = task.is_pinned
        ? '#1976d2'
        : task.is_lab_blocked
            ? '#e74c3c'
            : task.cooling_mode === 'slow'
                ? '#e67e22'
                : '#2c3e50';

    return {
        id: task.id,
        group: task.equipment_id,
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
    // Итерация 13.18: приоритет стилей
    //   1. is_pinned  — самая заметная рамка (синяя, плотная)
    //   2. isBlocked  — красная рамка
    //   3. isSlowCooling — оранжевая пунктирная
    //   4. isCzIncomplete — синяя пунктирная
    //   5. обычный — цвет по роли
    // ==========================================
    if (isPinned) {
        // Светлый синий фон + плотная синяя рамка слева
        style =
            `background-color: #e3f2fd; ` +
            `border: 2px solid #1976d2; ` +
            `border-left: 6px solid #1976d2; ` +
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
        const roleColor =
            ROLE_COLORS[task.task_role || ''] || ROLE_COLORS_DEFAULT;
        style = `background-color: ${roleColor}25; border-left: 4px solid ${roleColor}; border-radius: 4px;`;
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

    const title = `
            <div style="padding: 8px; min-width: 280px;">
              <b style="font-size: 14px; color: ${titleColor};">${titlePrefix}${task.operation_name}</b><br>
              <hr style="margin: 8px 0; border: none; border-top: 1px solid #ecf0f1;">
              <div style="font-size: 12px; line-height: 1.6;">
                <b>Партия:</b> ${task.batch_id}<br>
                <b>Продукт:</b> ${task.product_id}<br>
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