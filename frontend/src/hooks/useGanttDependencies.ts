// frontend/src/hooks/useGanttDependencies.ts
import type {RefObject} from 'react';
/**
 * Хук для отрисовки связей между задачами на Ганте
 * (Итерация 13.17 + 14.1).
 *
 * Вынесено из GanttPage.tsx.
 *
 * Логика:
 *  - Рисует SVG-overlay с ортогональными проводами между задачами
 *    (по depends_on_task_ids).
 *  - При hover на задаче — показывает её связи.
 *  - При showAllDependencies — показывает все связи.
 *  - При pan/zoom — throttled перерисовка.
 *
 * Итерация 14.1: добавлен режим группировки groupByMode:
 *   - 'equipment' — показываем ВСЕ связи (внутри- и межпартийные),
 *     как было.
 *   - 'batch' — показываем ТОЛЬКО межпартийные связи (те, что идут
 *     от задачи одной партии к задаче другой партии). Внутрипартийные
 *     связи скрыты, так как партия уже визуально сгруппирована в
 *     одну строку.
 *
 * Возвращает:
 *  - drawDependencies — полная перерисовка (для ручного вызова).
 *  - scheduleRedraw — throttled через requestAnimationFrame.
 *  - handleItemOver / handleItemOut — колбэки для Timeline.on('itemover'/'itemout').
 *  - resetHover — сбросить hover (при смене версии).
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
    /** Ссылка на контейнер с Timeline (для поиска DOM-элементов задач). */
    containerRef: RefObject<HTMLElement | null>;
    /** Ссылка на SVG-overlay (создаётся в JSX). */
    svgRef: RefObject<SVGSVGElement | null>;
    /** Ссылка на Timeline (для проверки, что он есть). */
    timelineRef: RefObject<Timeline | null>;
    /** Список всех задач (включая группы, setup, downtime). */
    tasks: TaskData[];
    /** Показывать ли связи вообще. */
    showDependencies: boolean;
    /** Показывать ли все связи (true) или только при hover (false). */
    showAllDependencies: boolean;
    /**
     * Итерация 14.1: режим группировки.
     * В режиме 'batch' показываем только межпартийные связи.
     */
    groupByMode: GroupByMode;
    /**
     * Колбэк при изменении hovered-партии.
     * Используется, если снаружи нужно реагировать на hover.
     */
    onHoverBatch?: (batchId: string | null) => void;
}

export interface UseGanttDependenciesResult {
    /** Полная перерисовка связей. */
    drawDependencies: (tasks: TaskData[]) => void;
    /** Throttled перерисовка (через requestAnimationFrame). */
    scheduleRedraw: () => void;
    /** Обработчик Timeline.on('itemover'). */
    handleItemOver: (props: any) => void;
    /** Обработчик Timeline.on('itemout'). */
    handleItemOut: (props: any) => void;
    /** Текущий hovered task id (для отладки/логики). */
    getHoveredTaskId: () => string | null;
    /** Сбросить hover. */
    resetHover: () => void;
}

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

    // --- Refs ---
    const hoveredTaskIdRef = useRef<string | null>(null);
    const hoveredBatchIdRef = useRef<string | null>(null);
    const redrawRafRef = useRef<number | null>(null);

    // ==========================================
    // Определение цвета провода
    // ==========================================
    const getLinkColor = useCallback(
        (fromTask: TaskData, toTask: TaskData): LinkColorKey => {
            if (toTask.task_role === 'WASH') {
                return 'to_wash';
            }
            if (
                fromTask.task_role === 'REACTOR_OP' &&
                toTask.task_role === 'TANK_TRANSFER'
            ) {
                return 'to_tank';
            }
            if (
                fromTask.task_role === 'TANK_TRANSFER' &&
                toTask.task_role === 'LINE_FILL'
            ) {
                return 'to_line';
            }
            if (
                fromTask.task_role === 'REACTOR_OP' &&
                toTask.task_role === 'LINE_FILL'
            ) {
                return 'direct';
            }
            return 'same_row';
        },
        [],
    );

    /**
     * Итерация 14.1: является ли связь межпартийной?
     *
     * Межпартийная = задачи принадлежат РАЗНЫМ партиям
     * (batch_id различаются). Внутрипартийные связи
     * (batch_id совпадают) считаются «скрытыми» в режиме 'batch'.
     *
     * Setup и downtime не имеют batch_id — они считаются
     * «внепартийными» и всегда отображаются, если есть связи.
     */
    const isInterBatchLink = useCallback(
        (fromTask: TaskData, toTask: TaskData): boolean => {
            const fromBatch = fromTask.batch_id;
            const toBatch = toTask.batch_id;

            // Setup / downtime / не-партия → всегда показываем
            const fromIsNonBatch =
                !fromBatch ||
                NON_BATCH_VALUES.has(fromBatch) ||
                (fromTask.item_type && fromTask.item_type !== 'task');
            const toIsNonBatch =
                !toBatch ||
                NON_BATCH_VALUES.has(toBatch) ||
                (toTask.item_type && toTask.item_type !== 'task');

            if (fromIsNonBatch || toIsNonBatch) {
                return true;
            }

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

            // Очищаем SVG
            while (svg.firstChild) {
                svg.removeChild(svg.firstChild);
            }

            if (!showDependencies) {
                svg.style.display = 'none';
                return;
            }

            const hoveredId = hoveredTaskIdRef.current;

            // ==========================================
            // Итерация 14.1: в режиме 'batch' рисуем только
            // связи при hover (даже если showAllDependencies = true).
            // Иначе диаграмма превратится в «спагетти» из связей
            // между всеми партиями.
            // ==========================================
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

            // Карта координат задач в контейнере
            const boxMap = new Map<
                string,
                {left: number; right: number; top: number; bottom: number}
            >();

            const itemEls = containerEl.querySelectorAll<HTMLElement>(
                '.vis-item.vis-range',
            );

            itemEls.forEach((el) => {
                const visItem = (el as any)['vis-item'];
                if (!visItem || !visItem.id) return;

                const itemId = String(visItem.id);
                const domEl: HTMLElement =
                    (visItem.dom && visItem.dom.box) || el;
                const rect = domEl.getBoundingClientRect();
                if (rect.width === 0 || rect.height === 0) return;

                boxMap.set(itemId, {
                    left: rect.left - containerRect.left,
                    right: rect.right - containerRect.left,
                    top: rect.top - containerRect.top,
                    bottom: rect.bottom - containerRect.top,
                });
            });

            if (boxMap.size === 0) return;

            // Карта задач по id (только "настоящие" task, без setup/downtime)
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

                // ==========================================
                // Итерация 14.1: в режиме 'batch' — фильтруем
                // внутрипартийные связи.
                // ==========================================
                if (groupByMode === 'batch' && !isInterBatch) {
                    return;
                }

                const colorKey = getLinkColor(fromTask, toTask);

                if (
                    groupByMode === 'equipment' &&
                    drawAll &&
                    colorKey === 'same_row' &&
                    !showAllDependencies
                ) {
                    return;
                }

                // Цвет: подсвеченный — оранжевый.
                // Межпартийная связь в режиме 'batch' — красный
                // (чтобы отличать от внутрипартийных).
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

            if (hoveredId) {
                const hoveredTask = taskMap.get(hoveredId);
                if (hoveredTask) {
                    // Исходящие — predecessors
                    (hoveredTask.depends_on_task_ids || []).forEach((fromId) => {
                        const fromTask = taskMap.get(fromId);
                        if (fromTask) {
                            addLink(fromTask, hoveredTask, true);
                        }
                    });

                    // Входящие — successors
                    allTasks.forEach((toTask) => {
                        if (!toTask.depends_on_task_ids) return;
                        if (toTask.depends_on_task_ids.includes(hoveredTask.id)) {
                            addLink(hoveredTask, toTask, true);
                        }
                    });
                }
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

            // Отрисовка каждой связи
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
                        if (gap > 20) {
                            midX = x1 + 10;
                        } else {
                            midX = x1 + Math.max(4, gap / 2);
                        }

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
            if (timelineRef.current) {
                drawDependencies(tasks);
            }
        });
    }, [drawDependencies, tasks, timelineRef]);

    // ==========================================
    // Hover
    // ==========================================
    const handleItemOver = useCallback(
        (props: any) => {
            if (!props.item) return;
            const itemId = String(props.item);
            const task = tasks.find((t) => t.id === itemId);
            if (
                !task ||
                task.item_type === 'downtime' ||
                task.item_type === 'setup'
            ) {
                return;
            }

            hoveredTaskIdRef.current = itemId;

            if (task.batch_id && !NON_BATCH_VALUES.has(task.batch_id)) {
                if (hoveredBatchIdRef.current !== task.batch_id) {
                    hoveredBatchIdRef.current = task.batch_id;
                    if (onHoverBatch) onHoverBatch(task.batch_id);
                }
            }

            if (timelineRef.current) {
                drawDependencies(tasks);
            }
        },
        [tasks, drawDependencies, onHoverBatch, timelineRef],
    );

    const handleItemOut = useCallback(
        (props: any) => {
            if (!props.item) return;
            const itemId = String(props.item);
            const task = tasks.find((t) => t.id === itemId);
            if (!task) return;

            hoveredTaskIdRef.current = null;

            if (hoveredBatchIdRef.current === task.batch_id) {
                hoveredBatchIdRef.current = null;
                if (onHoverBatch) onHoverBatch(null);
            }

            if (timelineRef.current) {
                drawDependencies(tasks);
            }
        },
        [tasks, drawDependencies, onHoverBatch, timelineRef],
    );

    // ==========================================
    // Утилиты
    // ==========================================
    const getHoveredTaskId = useCallback(() => {
        return hoveredTaskIdRef.current;
    }, []);

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