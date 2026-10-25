// frontend/src/hooks/useGanttDependencies.ts
import type {RefObject} from 'react';
import {useCallback, useRef, useState} from 'react';
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
    enableLinkHover: boolean;
    groupByMode: GroupByMode;
    onHoverBatch?: (batchId: string | null) => void;
    onLinkHover?: (fromTask: TaskData | null, toTask: TaskData | null, x: number, y: number) => void;
}

export interface UseGanttDependenciesResult {
    drawDependencies: (tasks: TaskData[]) => void;
    scheduleRedraw: () => void;
    handleItemOver: (props: any) => void;
    handleItemOut: (props: any) => void;
    getHoveredTaskId: () => string | null;
    resetHover: () => void;
    suppress: () => void;
    resume: () => void;
    hoveredLinkTaskIds: string[]; // <--- ВОЗВРАЩАЕМ
}

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
        containerRef, svgRef, timelineRef, tasks, showDependencies, showAllDependencies,
        enableLinkHover, groupByMode, onHoverBatch, onLinkHover,
    } = options;

    const hoveredTaskIdRef = useRef<string | null>(null);
    const hoveredBatchIdRef = useRef<string | null>(null);
    const redrawRafRef = useRef<number | null>(null);
    const suppressedRef = useRef<boolean>(false);
    const resumeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    // Возвращаем состояние для подсветки задач
    const [hoveredLinkTaskIds, setHoveredLinkTaskIds] = useState<string[]>([]);

    const getLinkColor = useCallback(
        (fromTask: TaskData, toTask: TaskData): LinkColorKey => {
            if (toTask.task_role === 'WASH') return 'to_wash';
            if (fromTask.task_role === 'REACTOR_OP' && toTask.task_role === 'TANK_TRANSFER') return 'to_tank';
            if (fromTask.task_role === 'TANK_TRANSFER' && toTask.task_role === 'LINE_FILL') return 'to_line';
            if (fromTask.task_role === 'REACTOR_OP' && toTask.task_role === 'LINE_FILL') return 'direct';
            return 'same_row';
        },
        [],
    );

    const isInterBatchLink = useCallback(
        (fromTask: TaskData, toTask: TaskData): boolean => {
            const fromBatch = fromTask.batch_id;
            const toBatch = toTask.batch_id;
            const fromIsNonBatch = !fromBatch || NON_BATCH_VALUES.has(fromBatch) || (fromTask.item_type && fromTask.item_type !== 'task');
            const toIsNonBatch = !toBatch || NON_BATCH_VALUES.has(toBatch) || (toTask.item_type && toTask.item_type !== 'task');
            if (fromIsNonBatch || toIsNonBatch) return true;
            return fromBatch !== toBatch;
        },
        [],
    );

    const drawDependencies = useCallback(
        (allTasks: TaskData[]) => {
            const svg = svgRef.current;
            const containerEl = containerRef.current;
            if (!svg || !containerEl) return;

            if (suppressedRef.current) {
                svg.style.display = 'none';
                return;
            }

            const oldMainGroup = svg.querySelector('#main-links-group');
            if (oldMainGroup) oldMainGroup.remove();

            if (!showDependencies) {
                svg.style.display = 'none';
                return;
            }

            const hoveredId = hoveredTaskIdRef.current;
            const drawAll = groupByMode === 'equipment' ? showAllDependencies && !hoveredId : false;

            if (!hoveredId && !drawAll) {
                svg.style.display = 'none';
                return;
            }
            svg.style.display = 'block';

            const centerPanel = containerEl.querySelector('.vis-panel.vis-center') as HTMLElement | null;
            const targetContainer = centerPanel || containerEl.parentElement;
            if (!targetContainer) return;

            if (svg.parentElement !== targetContainer) {
                targetContainer.appendChild(svg);
            }

            const containerRect = targetContainer.getBoundingClientRect();
            if (containerRect.width === 0 || containerRect.height === 0) return;

            svg.style.position = 'absolute';
            svg.style.left = '0';
            svg.style.top = '0';
            svg.style.width = `${containerRect.width}px`;
            svg.style.height = `${containerRect.height}px`;
            svg.style.pointerEvents = 'none';
            svg.style.overflow = 'visible';
            svg.style.zIndex = '6';
            svg.setAttribute('viewBox', `0 0 ${containerRect.width} ${containerRect.height}`);

            if (!svg.querySelector('defs')) {
                const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
                const clipPath = document.createElementNS('http://www.w3.org/2000/svg', 'clipPath');
                clipPath.setAttribute('id', 'gantt-deps-clip');
                clipPath.setAttribute('clipPathUnits', 'userSpaceOnUse');
                const SCROLLBAR_PADDING = 14;
                const clipRect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
                clipRect.setAttribute('x', String(SCROLLBAR_PADDING));
                clipRect.setAttribute('y', '0');
                clipRect.setAttribute('width', String(Math.max(0, containerRect.width - SCROLLBAR_PADDING)));
                clipRect.setAttribute('height', String(containerRect.height));
                clipPath.appendChild(clipRect);
                defs.appendChild(clipPath);
                svg.appendChild(defs);
            }

            const mainGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            mainGroup.setAttribute('id', 'main-links-group');
            mainGroup.setAttribute('clip-path', 'url(#gantt-deps-clip)');
            svg.appendChild(mainGroup);

            const boxMap = new Map<string, {left: number; right: number; top: number; bottom: number}>();
            const itemEls = containerEl.querySelectorAll<HTMLElement>('.vis-item.vis-range');
            const partsByGroupKey = new Map<string, TaskData[]>();

            allTasks.forEach((t) => {
                const key = getGroupKeyForTask(t);
                if (!key) return;
                if (!partsByGroupKey.has(key)) partsByGroupKey.set(key, []);
                partsByGroupKey.get(key)!.push(t);
            });

            itemEls.forEach((el) => {
                const visItem = (el as any)['vis-item'];
                if (!visItem || !visItem.id) return;

                const itemId = String(visItem.id);
                const domEl: HTMLElement = (visItem.dom && visItem.dom.box) || el;
                const rect = domEl.getBoundingClientRect();
                if (rect.width === 0 || rect.height === 0) return;

                const box = { left: rect.left - containerRect.left, right: rect.right - containerRect.left, top: rect.top - containerRect.top, bottom: rect.bottom - containerRect.top };
                boxMap.set(itemId, box);

                if (itemId.startsWith(GROUP_PREFIX)) {
                    const groupKeyFromId = itemId.substring(GROUP_PREFIX.length);
                    const baseKey = getBaseGroupKey(groupKeyFromId);
                    const parts = partsByGroupKey.get(baseKey);
                    if (parts) {
                        for (const part of parts) boxMap.set(part.id, box);
                    }
                }
            });

            const fullTaskMap = new Map<string, TaskData>();
            tasks.forEach((t) => { if (!t.item_type || t.item_type === 'task') fullTaskMap.set(t.id, t); });

            const equipmentOrder = new Map<string, number>();
            const groupsData = (timelineRef.current as any)?.groupsData;
            if (groupsData) {
                const ids = groupsData.getIds();
                ids.forEach((id: any, index: number) => { equipmentOrder.set(String(id), index); });
            }

            const computeInvisibleBox = (taskId: string) => {
                if (!timelineRef.current) return null;
                const task = fullTaskMap.get(taskId);
                if (!task) return null;

                try {
                    const start = new Date(task.start).getTime();
                    const end = new Date(task.end).getTime();
                    const range = timelineRef.current.getWindow();
                    const rangeStart = range.start.getTime();
                    const rangeEnd = range.end.getTime();
                    const totalMs = rangeEnd - rangeStart;

                    const left = ((start - rangeStart) / totalMs) * containerRect.width;
                    const right = ((end - rangeStart) / totalMs) * containerRect.width;

                    const centerEl = containerEl.querySelector('.vis-panel.vis-center');
                    if (!centerEl) return null;

                    let groupEl = centerEl.querySelector(`.vis-group[data-group-id="${task.equipment_id || ''}"]`);
                    let top = 0, bottom = 0;

                    if (groupEl) {
                        const groupRect = groupEl.getBoundingClientRect();
                        top = groupRect.top - containerRect.top + 2;
                        bottom = groupRect.bottom - containerRect.top - 2;
                    } else {
                        const eqId = task.equipment_id || '';
                        const index = equipmentOrder.get(eqId);
                        if (index === undefined) return null;
                        const ROW_HEIGHT = 37;
                        top = (index * ROW_HEIGHT) + 2;
                        bottom = ((index + 1) * ROW_HEIGHT) - 2;
                    }
                    return { left, right, top, bottom };
                } catch { return null; }
            };

            type LinkToDraw = { fromId: string; toId: string; color: string; isHighlighted: boolean; isInterBatch: boolean; fromTask: TaskData; toTask: TaskData; };
            const linksToDraw: LinkToDraw[] = [];

            const addLink = (fromTask: TaskData, toTask: TaskData, isHighlighted: boolean) => {
                const isInterBatch = isInterBatchLink(fromTask, toTask);
                if (groupByMode === 'batch' && !isInterBatch) return;

                const colorKey = getLinkColor(fromTask, toTask);
                if (groupByMode === 'equipment' && drawAll && colorKey === 'same_row' && !showAllDependencies) return;

                let color: string;
                if (isHighlighted) color = HOVER_COLOR;
                else if (groupByMode === 'batch' && isInterBatch) color = INTER_BATCH_LINK_COLOR;
                else color = LINK_COLORS[colorKey];

                linksToDraw.push({ fromId: fromTask.id, toId: toTask.id, color, isHighlighted, isInterBatch, fromTask, toTask });
            };

            if (hoveredId) {
                const isHoveredGroup = hoveredId.startsWith(GROUP_PREFIX);
                const hoveredTask = fullTaskMap.get(hoveredId);

                let hoveredRealIds: string[] = [];
                if (isHoveredGroup) {
                    const groupKeyFromId = hoveredId.substring(GROUP_PREFIX.length);
                    const baseKey = getBaseGroupKey(groupKeyFromId);
                    const parts = partsByGroupKey.get(baseKey) || [];
                    hoveredRealIds = parts.map((p) => p.id);
                } else if (hoveredTask) {
                    hoveredRealIds = [hoveredTask.id];
                }
                const hoveredRealIdsSet = new Set(hoveredRealIds);

                const predecessorIds = new Set<string>();
                if (isHoveredGroup) {
                    for (const id of hoveredRealIds) {
                        const part = fullTaskMap.get(id);
                        if (!part) continue;
                        for (const predId of part.depends_on_task_ids || []) predecessorIds.add(predId);
                    }
                } else if (hoveredTask) {
                    for (const predId of hoveredTask.depends_on_task_ids || []) predecessorIds.add(predId);
                }

                const hoveredAsTask: TaskData = hoveredTask ? hoveredTask : ({
                    id: hoveredId, batch_id: '', operation_name: '', equipment_id: '', product_id: '', start: '', end: '', duration_minutes: 0, task_role: 'LINE_FILL', item_type: 'task', depends_on_task_ids: [],
                } as unknown as TaskData);

                predecessorIds.forEach((predId) => {
                    const predTask = fullTaskMap.get(predId);
                    if (predTask) addLink(predTask, hoveredAsTask, true);
                });

                tasks.forEach((candidateTask) => {
                    if (!candidateTask.depends_on_task_ids || candidateTask.depends_on_task_ids.length === 0) return;
                    const hasMatch = candidateTask.depends_on_task_ids.some((id) => hoveredRealIdsSet.has(id));
                    if (!hasMatch) return;
                    addLink(hoveredAsTask, candidateTask, true);
                });
            } else if (drawAll) {
                tasks.forEach((toTask) => {
                    if (!toTask.depends_on_task_ids || toTask.depends_on_task_ids.length === 0) return;
                    toTask.depends_on_task_ids.forEach((fromId) => {
                        const fromTask = fullTaskMap.get(fromId);
                        if (fromTask) addLink(fromTask, toTask, false);
                    });
                });
            }

            linksToDraw.forEach(({fromId, toId, color, isHighlighted, isInterBatch, fromTask, toTask}) => {
                let fromBox: { left: number; right: number; top: number; bottom: number } | null | undefined = boxMap.get(fromId);
                let toBox: { left: number; right: number; top: number; bottom: number } | null | undefined = boxMap.get(toId);

                if (!fromBox) fromBox = computeInvisibleBox(fromId);
                if (!toBox) toBox = computeInvisibleBox(toId);

                if (!fromBox || !toBox) return;

                const SCROLLBAR_PADDING = 14;
                const x1 = Math.max(fromBox.right, SCROLLBAR_PADDING);
                const y1 = (fromBox.top + fromBox.bottom) / 2;
                const x2 = Math.max(toBox.left, SCROLLBAR_PADDING);
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
                        pathD = `M ${x1},${y1} H ${Math.max(x1 + 4, backMidX)} V ${y2} H ${x2}`;
                    } else {
                        pathD = `M ${x1},${y1} H ${midX} V ${y2} H ${x2}`;
                    }
                }

                const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
                path.setAttribute('d', pathD);
                path.setAttribute('stroke', color);
                path.setAttribute('fill', 'none');
                path.setAttribute('stroke-width', isHighlighted ? '3' : (isInterBatch ? '2.5' : '2'));
                path.setAttribute('stroke-opacity', isHighlighted ? '1' : '0.85');
                if (isInterBatch) path.setAttribute('stroke-dasharray', '6,3');
                path.style.pointerEvents = 'none';
                mainGroup.appendChild(path);

                const arrowSize = isHighlighted ? 7 : 6;
                const arrow = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
                arrow.setAttribute('points', `${x2},${y2} ${x2 - arrowSize},${y2 - arrowSize / 1.5} ${x2 - arrowSize},${y2 + arrowSize / 1.5}`);
                arrow.setAttribute('fill', color);
                arrow.setAttribute('fill-opacity', isHighlighted ? '1' : '0.9');
                arrow.style.pointerEvents = 'none';
                mainGroup.appendChild(arrow);

                if (enableLinkHover) {
                    const hitArea = document.createElementNS('http://www.w3.org/2000/svg', 'path');
                    hitArea.setAttribute('d', pathD);
                    hitArea.setAttribute('fill', 'none');
                    hitArea.setAttribute('stroke', 'transparent');
                    hitArea.setAttribute('stroke-width', '14');
                    hitArea.style.pointerEvents = 'stroke';
                    hitArea.style.cursor = 'pointer';

                    hitArea.addEventListener('mouseenter', (e) => {
                        path.classList.add('link-highlight');
                        arrow.classList.add('link-highlight');

                        // Подсветка задач через состояние React
                        setHoveredLinkTaskIds([fromTask.id, toTask.id]);

                        if (onLinkHover) onLinkHover(fromTask, toTask, e.clientX, e.clientY);
                    });

                    hitArea.addEventListener('mousemove', (e) => {
                        if (onLinkHover) onLinkHover(fromTask, toTask, e.clientX, e.clientY);
                    });

                    hitArea.addEventListener('mouseleave', () => {
                        path.classList.remove('link-highlight');
                        arrow.classList.remove('link-highlight');

                        // Сброс подсветки задач
                        setHoveredLinkTaskIds([]);

                        if (onLinkHover) onLinkHover(null, null, 0, 0);
                    });

                    mainGroup.appendChild(hitArea);
                }
            });
        },
        [showDependencies, showAllDependencies, groupByMode, getLinkColor, isInterBatchLink, svgRef, containerRef, timelineRef, tasks, enableLinkHover, onLinkHover],
    );

    const scheduleRedraw = useCallback(() => {
        if (suppressedRef.current) return;
        if (redrawRafRef.current !== null) cancelAnimationFrame(redrawRafRef.current);
        redrawRafRef.current = requestAnimationFrame(() => {
            redrawRafRef.current = null;
            if (timelineRef.current) drawDependencies(tasks);
        });
    }, [drawDependencies, tasks, timelineRef]);

    const suppress = useCallback(() => {
        suppressedRef.current = true;
        if (resumeTimerRef.current !== null) { clearTimeout(resumeTimerRef.current); resumeTimerRef.current = null; }
        const svg = svgRef.current;
        if (svg) svg.style.display = 'none';
    }, [svgRef]);

    const resume = useCallback(() => {
        suppressedRef.current = false;
        if (timelineRef.current) drawDependencies(tasks);
    }, [drawDependencies, tasks, timelineRef]);

    const handleItemOver = useCallback((props: any) => {
        if (!props.item || suppressedRef.current) return;
        const itemId = String(props.item);
        const isGroup = itemId.startsWith(GROUP_PREFIX);
        const task = tasks.find((t) => t.id === itemId);
        if (!isGroup && (!task || task.item_type === 'downtime' || task.item_type === 'setup')) return;

        hoveredTaskIdRef.current = itemId;
        if (task?.batch_id && !NON_BATCH_VALUES.has(task.batch_id)) {
            if (hoveredBatchIdRef.current !== task.batch_id) {
                hoveredBatchIdRef.current = task.batch_id;
                if (onHoverBatch) onHoverBatch(task.batch_id);
            }
        }
        if (timelineRef.current) drawDependencies(tasks);
    }, [tasks, drawDependencies, onHoverBatch, timelineRef]);

    const handleItemOut = useCallback((props: any) => {
        if (!props.item || suppressedRef.current) return;
        const itemId = String(props.item);
        const task = tasks.find((t) => t.id === itemId);
        hoveredTaskIdRef.current = null;
        if (task?.batch_id && hoveredBatchIdRef.current === task.batch_id) {
            hoveredBatchIdRef.current = null;
            if (onHoverBatch) onHoverBatch(null);
        }
        if (timelineRef.current) drawDependencies(tasks);
    }, [tasks, drawDependencies, onHoverBatch, timelineRef]);

    const getHoveredTaskId = useCallback(() => hoveredTaskIdRef.current, []);
    const resetHover = useCallback(() => {
        hoveredTaskIdRef.current = null;
        hoveredBatchIdRef.current = null;
        setHoveredLinkTaskIds([]); // Очищаем состояние при сбросе
        if (onHoverBatch) onHoverBatch(null);
    }, [onHoverBatch]);

    return {
        drawDependencies, scheduleRedraw, handleItemOver, handleItemOut, getHoveredTaskId, resetHover, suppress, resume,
        hoveredLinkTaskIds, // <--- Возвращаем
    };
};