// frontend/src/hooks/useGanttDependencies.ts
import type {RefObject} from 'react';
/**
 * Хук для отрисовки связей между задачами на Ганте
 * (Итерация 13.17 + 14.1 + 23).
 *
 * Логика:
 *  - Рисует SVG-overlay с ортогональными проводами между задачами
 *    (по depends_on_task_ids).
 *  - При hover на задаче — показывает ИСХОДЯЩИЕ (кто предки) и
 *    ВХОДЯЩИЕ (кто зависит от неё) связи.
 *  - При hover на виртуальной группе LINE_FILL — собирает
 *    depends_on_task_ids со ВСЕХ частей группы (объединение) и
 *    рисует связи от предков К группе, а также от группы К
 *    успессорам частей.
 *  - При showAllDependencies — показывает все связи.
 *  - При pan/zoom — throttled перерисовка.
 *
 * Итерация 14.1: добавлен режим группировки groupByMode.
 *
 * Итерация 23 (fix #group-deps):
 *   - boxMap регистрирует реальные ID частей виртуальных групп.
 *   - Hover на группе даёт связи в ОБА направления (раньше —
 *     только входящие).
 */
import {useCallback, useRef} from 'react';
import type {Timeline} from 'vis-timeline/standalone';
import {
    HOVER_COLOR,
    INTER_BATCH_LINK_COLOR,
    LINK_COLORS,
    type LinkColorKey,
    NON_BATCH_VALUES,
} from '../components/gantt/constants';
import type {GroupByMode, TaskData} from '../types';

export interface UseGanttDependenciesOptions {
    containerRef: RefObject<HTMLElement | null>;
    svgRef: RefObject<SVGSVGElement | null>;
    timelineRef: RefObject<Timeline | null>;
    tasks: TaskData[];
    showDependencies: boolean;
    showAllDependencies: boolean;
    groupByMode: GroupByMode;
    onHoverBatch?: (batchId: string | null) => void;
}

export interface UseGanttDependenciesResult {
    drawDependencies: (tasks: TaskData[]) => void;
    scheduleRedraw: () => void;
    handleItemOver: (props: any) => void;
    handleItemOut: (props: any) => void;
    getHoveredTaskId: () => string | null;
    resetHover: () => void;
}

// ==========================================
// ИТЕРАЦИЯ 23: утилиты для разворота групп
// ==========================================

const GROUP_PREFIX = '__group__';
const SEGMENT_SUFFIX_REGEX = /__seg\d+$/;
const PART_SUFFIX_REGEX = / \(часть \d+\/\d+\)$/;

const getBaseFillName = (operationName: string): string =>
    operationName.replace(PART_SUFFIX_REGEX, '');

const getGroupKeyForTask = (task: TaskData): string | null => {
    if (!task.batch_id || !task.operation_name) return null;
    if (!PART_SUFFIX_REGEX.test(task.operation_name)) return null;
    return `${task.batch_id}__${getBaseFillName(task.operation_name)}`;
};

const getBaseGroupKey = (groupKeyFromId: string): string =>
    groupKeyFromId.replace(SEGMENT_SUFFIX_REGEX, '');

export const useGanttDependencies = (
    options: UseGanttDependenciesOptions,
): UseGanttDependenciesResult => {
    const {
        containerRef,
        svgRef,
        timelineRef,
        tasks,
        showDependencies,
        showAllDependencies,
        groupByMode,
        onHoverBatch,
    } = options;

    const hoveredTaskIdRef = useRef<string | null>(null);
    const hoveredBatchIdRef = useRef<string | null>(null);
    const redrawRafRef = useRef<number | null>(null);

    // ==========================================
    // Цвет провода
    // ==========================================
    const getLinkColor = useCallback(
        (fromTask: TaskData, toTask: TaskData): LinkColorKey => {
            if (toTask.task_role === 'WASH') return 'to_wash';
            if (
                fromTask.task_role === 'REACTOR_OP' &&
                toTask.task_role === 'TANK_TRANSFER'
            ) return 'to_tank';
            if (
                fromTask.task_role === 'TANK_TRANSFER' &&
                toTask.task_role === 'LINE_FILL'
            ) return 'to_line';
            if (
                fromTask.task_role === 'REACTOR_OP' &&
                toTask.task_role === 'LINE_FILL'
            ) return 'direct';
            return 'same_row';
        },
        [],
    );

    const isInterBatchLink = useCallback(
        (fromTask: TaskData, toTask: TaskData): boolean => {
            const fromBatch = fromTask.batch_id;
            const toBatch = toTask.batch_id;
            const fromIsNonBatch =
                !fromBatch ||
                NON_BATCH_VALUES.has(fromBatch) ||
                (fromTask.item_type && fromTask.item_type !== 'task');
            const toIsNonBatch =
                !toBatch ||
                NON_BATCH_VALUES.has(toBatch) ||
                (toTask.item_type && toTask.item_type !== 'task');
            if (fromIsNonBatch || toIsNonBatch) return true;
            return fromBatch !== toBatch;
        },
        [],
    );

    // ==========================================
    // Полная перерисовка связей
    // ==========================================
    const drawDependencies = useCallback(
        (allTasks: TaskData[]) => {
            const svg = svgRef.current;
            const containerEl = containerRef.current;
            if (!svg || !containerEl) return;

            while (svg.firstChild) svg.removeChild(svg.firstChild);

            if (!showDependencies) {
                svg.style.display = 'none';
                return;
            }

            const hoveredId = hoveredTaskIdRef.current;

            const drawAll =
                groupByMode === 'equipment'
                    ? showAllDependencies && !hoveredId
                    : false;

            if (!hoveredId && !drawAll) {
                svg.style.display = 'none';
                return;
            }
            svg.style.display = 'block';

            const ganttContainer = containerEl.parentElement;
            if (!ganttContainer) return;
            if (svg.parentElement !== ganttContainer) {
                ganttContainer.appendChild(svg);
            }

            const containerRect = ganttContainer.getBoundingClientRect();
            if (containerRect.width === 0 || containerRect.height === 0) return;

            svg.style.position = 'absolute';
            svg.style.left = '0';
            svg.style.top = '0';
            svg.style.width = `${containerRect.width}px`;
            svg.style.height = `${containerRect.height}px`;
            svg.style.pointerEvents = 'none';
            svg.style.overflow = 'hidden';
            svg.style.zIndex = '6';
            svg.setAttribute(
                'viewBox',
                `0 0 ${containerRect.width} ${containerRect.height}`,
            );

            // ==========================================
            // boxMap (с разворотом групп)
            // ==========================================
            const boxMap = new Map<
                string,
                {left: number; right: number; top: number; bottom: number}
            >();

            const itemEls = containerEl.querySelectorAll<HTMLElement>(
                '.vis-item.vis-range',
            );

            // Индексируем все реальные части по базовому ключу группы.
            const partsByGroupKey = new Map<string, TaskData[]>();
            allTasks.forEach((t) => {
                const key = getGroupKeyForTask(t);
                if (!key) return;
                if (!partsByGroupKey.has(key)) {
                    partsByGroupKey.set(key, []);
                }
                partsByGroupKey.get(key)!.push(t);
            });

            itemEls.forEach((el) => {
                const visItem = (el as any)['vis-item'];
                if (!visItem || !visItem.id) return;

                const itemId = String(visItem.id);
                const domEl: HTMLElement =
                    (visItem.dom && visItem.dom.box) || el;
                const rect = domEl.getBoundingClientRect();
                if (rect.width === 0 || rect.height === 0) return;

                const box = {
                    left: rect.left - containerRect.left,
                    right: rect.right - containerRect.left,
                    top: rect.top - containerRect.top,
                    bottom: rect.bottom - containerRect.top,
                };

                boxMap.set(itemId, box);

                if (itemId.startsWith(GROUP_PREFIX)) {
                    const groupKeyFromId = itemId.substring(GROUP_PREFIX.length);
                    const baseKey = getBaseGroupKey(groupKeyFromId);
                    const parts = partsByGroupKey.get(baseKey);
                    if (parts) {
                        for (const part of parts) {
                            boxMap.set(part.id, box);
                        }
                    }
                }
            });

            if (boxMap.size === 0) return;

            const taskMap = new Map<string, TaskData>();
            allTasks.forEach((t) => {
                if (!t.item_type || t.item_type === 'task') {
                    taskMap.set(t.id, t);
                }
            });

            type LinkToDraw = {
                fromId: string;
                toId: string;
                color: string;
                isHighlighted: boolean;
                isInterBatch: boolean;
            };
            const linksToDraw: LinkToDraw[] = [];

            const addLink = (
                fromTask: TaskData,
                toTask: TaskData,
                isHighlighted: boolean,
            ) => {
                const isInterBatch = isInterBatchLink(fromTask, toTask);

                if (groupByMode === 'batch' && !isInterBatch) return;

                const colorKey = getLinkColor(fromTask, toTask);

                if (
                    groupByMode === 'equipment' &&
                    drawAll &&
                    colorKey === 'same_row' &&
                    !showAllDependencies
                ) {
                    return;
                }

                let color: string;
                if (isHighlighted) {
                    color = HOVER_COLOR;
                } else if (groupByMode === 'batch' && isInterBatch) {
                    color = INTER_BATCH_LINK_COLOR;
                } else {
                    color = LINK_COLORS[colorKey];
                }

                linksToDraw.push({
                    fromId: fromTask.id,
                    toId: toTask.id,
                    color,
                    isHighlighted,
                    isInterBatch,
                });
            };

            // ==========================================
            // Hover-режим
            // ==========================================
            if (hoveredId) {
                const isHoveredGroup = hoveredId.startsWith(GROUP_PREFIX);
                const hoveredTask = taskMap.get(hoveredId);

                // Реальные ID частей, если hovered — группа.
                // Иначе — [id самой задачи].
                let hoveredRealIds: string[] = [];
                if (isHoveredGroup) {
                    const groupKeyFromId = hoveredId.substring(
                        GROUP_PREFIX.length,
                    );
                    const baseKey = getBaseGroupKey(groupKeyFromId);
                    const parts = partsByGroupKey.get(baseKey) || [];
                    hoveredRealIds = parts.map((p) => p.id);
                } else if (hoveredTask) {
                    hoveredRealIds = [hoveredTask.id];
                }
                const hoveredRealIdsSet = new Set(hoveredRealIds);

                // ------------------------------------------
                // 1. ИСХОДЯЩИЕ (predecessors): от кого зависит hovered.
                //    Для группы — объединение depends_on_task_ids
                //    всех её частей.
                // ------------------------------------------
                const predecessorIds = new Set<string>();
                if (isHoveredGroup) {
                    for (const id of hoveredRealIds) {
                        const part = taskMap.get(id);
                        if (!part) continue;
                        for (const predId of part.depends_on_task_ids || []) {
                            predecessorIds.add(predId);
                        }
                    }
                } else if (hoveredTask) {
                    for (const predId of hoveredTask.depends_on_task_ids || []) {
                        predecessorIds.add(predId);
                    }
                }

                // «Виртуальный» объект, представляющий hovered
                // (реальная задача или группа) для addLink.
                const hoveredAsTask: TaskData = hoveredTask
                    ? hoveredTask
                    : ({
                        id: hoveredId,
                        batch_id: '',
                        operation_name: '',
                        equipment_id: '',
                        product_id: '',
                        start: '',
                        end: '',
                        duration_minutes: 0,
                        task_role: 'LINE_FILL',
                        item_type: 'task',
                        depends_on_task_ids: [],
                    } as unknown as TaskData);

                predecessorIds.forEach((predId) => {
                    const predTask = taskMap.get(predId);
                    if (predTask) {
                        // from=предок → to=hovered
                        addLink(predTask, hoveredAsTask, true);
                    }
                });

                // ------------------------------------------
                // 2. ВХОДЯЩИЕ (successors): кто зависит от hovered.
                //    Для группы — ищем задачи, которые зависят
                //    от ЛЮБОЙ из её частей.
                // ------------------------------------------
                allTasks.forEach((candidateTask) => {
                    if (!candidateTask.depends_on_task_ids) return;
                    if (candidateTask.depends_on_task_ids.length === 0) return;

                    const hasMatch = candidateTask.depends_on_task_ids.some(
                        (id) => hoveredRealIdsSet.has(id),
                    );
                    if (!hasMatch) return;

                    // from=hovered → to=candidateTask
                    addLink(hoveredAsTask, candidateTask, true);
                });
            } else if (drawAll) {
                allTasks.forEach((toTask) => {
                    if (
                        !toTask.depends_on_task_ids ||
                        toTask.depends_on_task_ids.length === 0
                    ) {
                        return;
                    }
                    toTask.depends_on_task_ids.forEach((fromId) => {
                        const fromTask = taskMap.get(fromId);
                        if (fromTask) {
                            addLink(fromTask, toTask, false);
                        }
                    });
                });
            }

            // ==========================================
            // Отрисовка
            // ==========================================
            linksToDraw.forEach(
                ({fromId, toId, color, isHighlighted, isInterBatch}) => {
                    const fromBox = boxMap.get(fromId);
                    const toBox = boxMap.get(toId);
                    if (!fromBox || !toBox) return;

                    const x1 = fromBox.right;
                    const y1 = (fromBox.top + fromBox.bottom) / 2;
                    const x2 = toBox.left;
                    const y2 = (toBox.top + toBox.bottom) / 2;

                    if (x1 === x2 && y1 === y2) return;

                    let pathD: string;
                    const isSameVisualRow = Math.abs(y1 - y2) < 2;

                    if (isSameVisualRow) {
                        pathD = `M ${x1},${y1} H ${x2}`;
                    } else {
                        const gap = x2 - x1;
                        let midX: number;
                        if (gap > 20) midX = x1 + 10;
                        else midX = x1 + Math.max(4, gap / 2);

                        if (midX > x2 - 2) {
                            const backMidX = x2 - 10;
                            pathD = `M ${x1},${y1} H ${Math.max(
                                x1 + 4,
                                backMidX,
                            )} V ${y2} H ${x2}`;
                        } else {
                            pathD = `M ${x1},${y1} H ${midX} V ${y2} H ${x2}`;
                        }
                    }

                    const path = document.createElementNS(
                        'http://www.w3.org/2000/svg',
                        'path',
                    );
                    path.setAttribute('d', pathD);
                    path.setAttribute(
                        'class',
                        'gantt-dependency-line' +
                        (isHighlighted ? ' highlighted' : '') +
                        (isInterBatch ? ' inter-batch' : ''),
                    );
                    path.setAttribute('stroke', color);
                    path.setAttribute('fill', 'none');
                    if (isHighlighted) {
                        path.setAttribute('stroke-width', '2.5');
                        path.setAttribute('stroke-opacity', '1');
                    } else if (isInterBatch) {
                        path.setAttribute('stroke-width', '2');
                        path.setAttribute('stroke-opacity', '0.85');
                        path.setAttribute('stroke-dasharray', '6,3');
                    } else {
                        path.setAttribute('stroke-width', '1.5');
                        path.setAttribute('stroke-opacity', '0.55');
                    }
                    svg.appendChild(path);

                    const arrowSize = isHighlighted ? 6 : 5;
                    const arrow = document.createElementNS(
                        'http://www.w3.org/2000/svg',
                        'polygon',
                    );
                    arrow.setAttribute(
                        'points',
                        `${x2},${y2} ` +
                        `${x2 - arrowSize},${y2 - arrowSize / 1.5} ` +
                        `${x2 - arrowSize},${y2 + arrowSize / 1.5}`,
                    );
                    arrow.setAttribute(
                        'class',
                        'gantt-dependency-arrowhead' +
                        (isHighlighted ? ' highlighted' : '') +
                        (isInterBatch ? ' inter-batch' : ''),
                    );
                    arrow.setAttribute('fill', color);
                    arrow.setAttribute(
                        'fill-opacity',
                        isHighlighted ? '1' : '0.75',
                    );
                    svg.appendChild(arrow);
                },
            );
        },
        [
            showDependencies,
            showAllDependencies,
            groupByMode,
            getLinkColor,
            isInterBatchLink,
            svgRef,
            containerRef,
        ],
    );

    // ==========================================
    // Throttled перерисовка
    // ==========================================
    const scheduleRedraw = useCallback(() => {
        if (redrawRafRef.current !== null) {
            cancelAnimationFrame(redrawRafRef.current);
        }
        redrawRafRef.current = requestAnimationFrame(() => {
            redrawRafRef.current = null;
            if (timelineRef.current) drawDependencies(tasks);
        });
    }, [drawDependencies, tasks, timelineRef]);

    // ==========================================
    // Hover
    // ==========================================
    const handleItemOver = useCallback(
        (props: any) => {
            if (!props.item) return;
            const itemId = String(props.item);

            const isGroup = itemId.startsWith(GROUP_PREFIX);
            const task = tasks.find((t) => t.id === itemId);

            if (
                !isGroup &&
                (!task ||
                    task.item_type === 'downtime' ||
                    task.item_type === 'setup')
            ) {
                return;
            }

            hoveredTaskIdRef.current = itemId;

            if (task?.batch_id && !NON_BATCH_VALUES.has(task.batch_id)) {
                if (hoveredBatchIdRef.current !== task.batch_id) {
                    hoveredBatchIdRef.current = task.batch_id;
                    if (onHoverBatch) onHoverBatch(task.batch_id);
                }
            }

            if (timelineRef.current) drawDependencies(tasks);
        },
        [tasks, drawDependencies, onHoverBatch, timelineRef],
    );

    const handleItemOut = useCallback(
        (props: any) => {
            if (!props.item) return;
            const itemId = String(props.item);
            const task = tasks.find((t) => t.id === itemId);

            hoveredTaskIdRef.current = null;

            if (task?.batch_id && hoveredBatchIdRef.current === task.batch_id) {
                hoveredBatchIdRef.current = null;
                if (onHoverBatch) onHoverBatch(null);
            }

            if (timelineRef.current) drawDependencies(tasks);
        },
        [tasks, drawDependencies, onHoverBatch, timelineRef],
    );

    // ==========================================
    // Утилиты
    // ==========================================
    const getHoveredTaskId = useCallback(() => hoveredTaskIdRef.current, []);

    const resetHover = useCallback(() => {
        hoveredTaskIdRef.current = null;
        hoveredBatchIdRef.current = null;
        if (onHoverBatch) onHoverBatch(null);
    }, [onHoverBatch]);

    return {
        drawDependencies,
        scheduleRedraw,
        handleItemOver,
        handleItemOut,
        getHoveredTaskId,
        resetHover,
    };
};