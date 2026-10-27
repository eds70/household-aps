// frontend/src/hooks/useGanttTimeline.ts
import type {MutableRefObject, RefObject} from 'react';
import {useCallback, useEffect, useRef} from 'react';
import {Timeline, type TimelineOptions} from 'vis-timeline/standalone';
import {DataSet} from 'vis-data';

import type {BatchBracket, GroupByMode, TaskData} from '../types';
import type {GanttGroup, GanttItem, ViewportState,} from '../components/gantt/types';
import {
    BATCH_BRACKET_BLOCKED_COLOR,
    BATCH_BRACKET_DASH_ARRAY,
    BATCH_BRACKET_DASH_ARRAY_HIGHLIGHTED,
    BATCH_BRACKET_LABEL_FONT_FAMILY,
    BATCH_BRACKET_LABEL_FONT_SIZE,
    BATCH_BRACKET_LABEL_HEIGHT,
    BATCH_BRACKET_LABEL_OFFSET_Y,
    BATCH_BRACKET_LABEL_PADDING_X,
    BATCH_BRACKET_LABEL_TEXT_COLOR,
    BATCH_BRACKET_PADDING_PX,
    BATCH_BRACKET_STROKE_OPACITY,
    BATCH_BRACKET_STROKE_OPACITY_HIGHLIGHTED,
    BATCH_BRACKET_STROKE_WIDTH,
    BATCH_BRACKET_STROKE_WIDTH_HIGHLIGHTED,
    BATCH_BRACKETS_Z_INDEX,
    BATCH_LABEL_MAX_LENGTH,
    DIMMED_LABEL_CLASS,
    DIMMED_TASK_CLASS,
    HIGHLIGHTED_TASK_CLASS,
    MAX_VISIBLE_BATCH_BRACKETS,
    NON_BATCH_VALUES,
} from '../components/gantt/constants';
import {buildGanttItems} from '../utils/ganttRenderItems';
import {buildMinimapTimelineOptions} from '../utils/ganttTimelineOptions';
import {getGroupKeyFromId, groupFillParts} from '../utils/ganttGroups';
import {buildBatchBrackets} from '../utils/ganttBrackets';
import {readViewportFromStorage} from './useGanttViewport';
import type {UseGanttDependenciesResult} from './useGanttDependencies';
import type {UseGanttFiltersResult} from './useGanttFilters';

export interface UseGanttTimelineParams {
    containerRef: RefObject<HTMLElement | null>;
    minimapContainerRef: RefObject<HTMLElement | null>;
    timelineRef: MutableRefObject<Timeline | null>;
    minimapRef: MutableRefObject<Timeline | null>;
    tasks: TaskData[];
    isReadOnly: boolean;
    localEditMode: boolean;
    showMinimap: boolean;
    showDependencies: boolean;
    showAllDependencies: boolean;
    showSetups: boolean;
    showDowntimes: boolean;
    versionId: string | null;
    expandedGroups: Set<string>;
    onToggleGroup?: (groupKey: string) => void;
    viewportRef: MutableRefObject<ViewportState | null>;
    suppressViewportSyncRef: MutableRefObject<boolean>;
    minimapSyncingRef: MutableRefObject<boolean>;
    saveViewportToStorage: (view: ViewportState) => void;
    persistCurrentViewport: () => void;
    deps: UseGanttDependenciesResult;
    filters: UseGanttFiltersResult;
    onTaskEdit: (taskId: string) => void;
    onBatchClick: (batchId: string) => void;
    onMoveTask: (item: any, callback: (item: any) => void) => void | Promise<void>;
    onError: (message: string) => void;
    setFilteredCount: (count: number) => void;
    onItemChange?: (itemId: string | null, start: Date | null, end: Date | null, mouseX: number, mouseY: number) => void;
    groupByMode: GroupByMode;
    showBatchBrackets: boolean;
    highlightedBatchId: string | null;
    onBracketClick?: (batchId: string) => void;
    hoveredLinkTaskIds?: string[];
}

export interface UseGanttTimelineResult {
    renderTimeline: (tasksData: TaskData[], equipment: string[]) => void;
    destroy: () => void;
}

const TEXT_UPDATE_INTERVAL_MS = 150;
const TOOLTIP_HIDE_DELAY_MS = 1200;
const MIN_TASK_DURATION_MS = 60_000;
const RANGE_SUPPRESS_DEBOUNCE_MS = 150;

export const useGanttTimeline = (
    params: UseGanttTimelineParams,
): UseGanttTimelineResult => {
    const {
        containerRef, minimapContainerRef, timelineRef, minimapRef, tasks, isReadOnly, localEditMode,
        showMinimap, showDependencies, showAllDependencies, showSetups, showDowntimes, versionId,
        expandedGroups, onToggleGroup, viewportRef, suppressViewportSyncRef, minimapSyncingRef,
        saveViewportToStorage, persistCurrentViewport, deps, filters, onTaskEdit, onBatchClick,
        onMoveTask, onError, setFilteredCount, onItemChange, groupByMode, showBatchBrackets,
        highlightedBatchId, onBracketClick, hoveredLinkTaskIds = []
    } = params;

    const clickTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const rangeResumeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    const dragStateRef = useRef<{
        itemId: string; operationType: 'move' | 'resize'; startX: number;
        originalStartMs: number; originalEndMs: number; originalDurationMs: number;
        msPerPx: number; fixedEndMs: number; fixedStartMs: number;
        lastMouseX: number; lastMouseY: number; tooltipShown: boolean;
    } | null>(null);

    const rafIdRef = useRef<number | null>(null);
    const pendingEventRef = useRef<PointerEvent | MouseEvent | null>(null);
    const lastTextUpdateAtRef = useRef<number>(0);
    const hideTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const bracketsRafRef = useRef<number | null>(null);
    const bracketsPendingTasksRef = useRef<TaskData[] | null>(null);

    const destroy = useCallback(() => {
        if (timelineRef.current) { timelineRef.current.destroy(); timelineRef.current = null; }
        if (minimapRef.current) { minimapRef.current.destroy(); minimapRef.current = null; }
        if (clickTimeoutRef.current) { clearTimeout(clickTimeoutRef.current); clickTimeoutRef.current = null; }
        if (rafIdRef.current !== null) { cancelAnimationFrame(rafIdRef.current); rafIdRef.current = null; }
        if (hideTimerRef.current !== null) { clearTimeout(hideTimerRef.current); hideTimerRef.current = null; }
        if (bracketsRafRef.current !== null) { cancelAnimationFrame(bracketsRafRef.current); bracketsRafRef.current = null; }
        if (rangeResumeTimerRef.current !== null) { clearTimeout(rangeResumeTimerRef.current); rangeResumeTimerRef.current = null; }
    }, [timelineRef, minimapRef]);

    const detectOperationType = (target: HTMLElement): 'move' | 'resize' => {
        if (target.closest('.vis-drag-left') || target.closest('.vis-drag-right')) return 'resize';
        return 'move';
    };

    const getTaskIdFromElement = (el: HTMLElement | null): string | null => {
        if (!el) return null;
        const itemEl = el.closest('.vis-item.vis-range') as HTMLElement | null;
        if (!itemEl) return null;
        const visItem = (itemEl as any)['vis-item'];
        if (!visItem || !visItem.id) return null;
        return String(visItem.id);
    };

    const attachNativeDragListeners = useCallback(() => {
        const container = containerRef.current;
        if (!container) return () => {};

        const onPointerDown = (e: PointerEvent) => {
            const target = e.target as HTMLElement;
            if (!target?.closest('.vis-item.vis-range')) return;

            const itemId = getTaskIdFromElement(target);
            if (!itemId) return;
            if (itemId.startsWith('setup_') || itemId.startsWith('weekend_') || itemId.startsWith('__group__')) return;

            const task = tasks.find((t) => t.id === itemId);
            if (!task || !localEditMode) return;

            const timeline = timelineRef.current;
            if (!timeline) return;

            const operationType = detectOperationType(target);

            let msPerPx = 1;
            try {
                const range = timeline.getWindow();
                const totalMs = range.end.getTime() - range.start.getTime();
                const centerPanel = container.querySelector('.vis-panel.vis-center') as HTMLElement | null;
                const panelWidth = centerPanel?.clientWidth || container.clientWidth || 1;
                msPerPx = totalMs / panelWidth;
            } catch {}

            const startMs = new Date(task.start).getTime();
            const endMs = new Date(task.end).getTime();

            dragStateRef.current = {
                itemId, operationType, startX: e.clientX, originalStartMs: startMs, originalEndMs: endMs,
                originalDurationMs: endMs - startMs, msPerPx, fixedEndMs: endMs, fixedStartMs: startMs,
                lastMouseX: e.clientX, lastMouseY: e.clientY, tooltipShown: false,
            };

            deps.suppress();

            if (rafIdRef.current !== null) { cancelAnimationFrame(rafIdRef.current); rafIdRef.current = null; }
            pendingEventRef.current = null;
            lastTextUpdateAtRef.current = 0;
            if (hideTimerRef.current !== null) { clearTimeout(hideTimerRef.current); hideTimerRef.current = null; }
        };

        const onPointerMove = (e: PointerEvent) => {
            const st = dragStateRef.current;
            if (!st) return;

            st.lastMouseX = e.clientX;
            st.lastMouseY = e.clientY;

            pendingEventRef.current = e;
            if (rafIdRef.current !== null) return;

            rafIdRef.current = requestAnimationFrame(() => {
                rafIdRef.current = null;
                const ev = pendingEventRef.current;
                pendingEventRef.current = null;
                if (!ev || !dragStateRef.current) return;

                const state = dragStateRef.current;
                const deltaPx = ev.clientX - state.startX;
                const deltaMs = deltaPx * state.msPerPx;

                let newStartMs: number;
                let newEndMs: number;

                if (state.operationType === 'move') {
                    newStartMs = state.originalStartMs + deltaMs;
                    newEndMs = state.originalEndMs + deltaMs;
                } else {
                    const originalWidthPx = state.originalDurationMs / state.msPerPx;
                    const midX = state.startX + originalWidthPx / 2;

                    if (ev.clientX < midX) {
                        newStartMs = state.originalStartMs + deltaMs;
                        newEndMs = state.fixedEndMs;
                        if (newStartMs >= newEndMs - MIN_TASK_DURATION_MS) newStartMs = newEndMs - MIN_TASK_DURATION_MS;
                    } else {
                        newStartMs = state.fixedStartMs;
                        newEndMs = state.originalEndMs + deltaMs;
                        if (newEndMs <= newStartMs + MIN_TASK_DURATION_MS) newEndMs = newStartMs + MIN_TASK_DURATION_MS;
                    }
                }

                if (!onItemChange) return;

                const now = performance.now();
                const shouldUpdateText = now - lastTextUpdateAtRef.current > TEXT_UPDATE_INTERVAL_MS;

                if (!state.tooltipShown) {
                    onItemChange(state.itemId, new Date(newStartMs), new Date(newEndMs), ev.clientX, ev.clientY);
                    state.tooltipShown = true;
                    lastTextUpdateAtRef.current = now;
                } else if (shouldUpdateText) {
                    onItemChange(state.itemId, new Date(newStartMs), new Date(newEndMs), ev.clientX, ev.clientY);
                    lastTextUpdateAtRef.current = now;
                } else {
                    onItemChange(state.itemId, null, null, ev.clientX, ev.clientY);
                }
            });
        };

        const onPointerUp = () => {
            const st = dragStateRef.current;
            dragStateRef.current = null;

            if (rafIdRef.current !== null) { cancelAnimationFrame(rafIdRef.current); rafIdRef.current = null; }
            pendingEventRef.current = null;

            deps.resume();

            if (onItemChange && st?.itemId) {
                if (hideTimerRef.current !== null) clearTimeout(hideTimerRef.current);
                hideTimerRef.current = setTimeout(() => {
                    hideTimerRef.current = null;
                    onItemChange(null, null, null, 0, 0);
                }, TOOLTIP_HIDE_DELAY_MS);
            }
        };

        const onMouseDown = (e: MouseEvent) => onPointerDown(e as unknown as PointerEvent);
        const onMouseMove = (e: MouseEvent) => { if (dragStateRef.current) onPointerMove(e as unknown as PointerEvent); };
        const onMouseUp = () => { if (dragStateRef.current) onPointerUp(); };

        container.addEventListener('pointerdown', onPointerDown, true);
        container.addEventListener('mousedown', onMouseDown, true);
        window.addEventListener('pointermove', onPointerMove, true);
        window.addEventListener('mousemove', onMouseMove, true);
        window.addEventListener('pointerup', onPointerUp, true);
        window.addEventListener('mouseup', onMouseUp, true);

        return () => {
            container.removeEventListener('pointerdown', onPointerDown, true);
            container.removeEventListener('mousedown', onMouseDown, true);
            window.removeEventListener('pointermove', onPointerMove, true);
            window.removeEventListener('mousemove', onMouseMove, true);
            window.removeEventListener('pointerup', onPointerUp, true);
            window.removeEventListener('mouseup', onMouseUp, true);
        };
    }, [containerRef, timelineRef, tasks, isReadOnly, localEditMode, onItemChange, deps]);

    const drawBatchBrackets = useCallback(
        (allTasks: TaskData[]) => {
            const container = containerRef.current;
            if (!container) return;

            const centerPanel = container.querySelector('.vis-panel.vis-center') as HTMLElement | null;
            if (!centerPanel) return;

            const existingSvg = centerPanel.querySelector('.gantt-batch-brackets-svg');
            if (existingSvg && existingSvg.parentElement) existingSvg.parentElement.removeChild(existingSvg);

            container.querySelectorAll(`.${DIMMED_TASK_CLASS}, .${HIGHLIGHTED_TASK_CLASS}`).forEach((el) => {
                el.classList.remove(DIMMED_TASK_CLASS);
                el.classList.remove(HIGHLIGHTED_TASK_CLASS);
            });

            if (groupByMode !== 'equipment' || !showBatchBrackets) return;

            const allBrackets = buildBatchBrackets(allTasks);
            if (allBrackets.length === 0) return;

            const brackets = allBrackets.slice(0, MAX_VISIBLE_BATCH_BRACKETS);

            const centerRect = centerPanel.getBoundingClientRect();
            if (centerRect.width === 0 || centerRect.height === 0) return;

            const itemEls = container.querySelectorAll<HTMLElement>('.vis-item.vis-range');

            const boxMap = new Map<string, { left: number; right: number; top: number; bottom: number; el: HTMLElement }>();

            itemEls.forEach((el) => {
                const visItem = (el as any)['vis-item'];
                if (!visItem || !visItem.id) return;

                const itemId = String(visItem.id);
                const domEl: HTMLElement = (visItem.dom && visItem.dom.box) || el;
                const rect = domEl.getBoundingClientRect();
                if (rect.width === 0 || rect.height === 0) return;

                boxMap.set(itemId, {
                    left: rect.left - centerRect.left, right: rect.right - centerRect.left,
                    top: rect.top - centerRect.top, bottom: rect.bottom - centerRect.top, el: domEl,
                });
            });

            if (boxMap.size === 0) return;

            if (highlightedBatchId) {
                const selectedBracket = brackets.find((b) => b.batchId === highlightedBatchId);
                if (selectedBracket) {
                    const selectedTaskIds = new Set(selectedBracket.taskIds);
                    boxMap.forEach((box, taskId) => {
                        if (selectedTaskIds.has(taskId)) box.el.classList.add(HIGHLIGHTED_TASK_CLASS);
                        else box.el.classList.add(DIMMED_TASK_CLASS);
                    });
                }
            }

            const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
            svg.setAttribute('class', 'gantt-batch-brackets-svg');
            svg.style.position = 'absolute'; svg.style.left = '0'; svg.style.top = '0';
            svg.style.width = `${centerRect.width}px`; svg.style.height = `${centerRect.height}px`;
            svg.style.pointerEvents = 'none'; svg.style.overflow = 'visible';
            svg.style.zIndex = String(BATCH_BRACKETS_Z_INDEX);
            svg.setAttribute('viewBox', `0 0 ${Math.max(1, centerRect.width)} ${Math.max(1, centerRect.height)}`);

            interface BracketBox {
                bracket: BatchBracket; x: number; y: number; w: number; h: number;
                labelX: number; labelY: number; labelW: number; labelH: number;
                isHighlighted: boolean; isBlocked: boolean; strokeColor: string;
                firstTaskTop: number; firstTaskLeft: number;
            }

            const bracketBoxes: BracketBox[] = [];

            for (const bracket of brackets) {
                let minLeft = Infinity, maxRight = -Infinity, minTop = Infinity, maxBottom = -Infinity;
                let hasAny = false, firstTaskTop = Infinity, firstTaskLeft = Infinity;

                for (const taskId of bracket.taskIds) {
                    const box = boxMap.get(taskId);
                    if (!box) continue;
                    hasAny = true;
                    if (box.left < minLeft) minLeft = box.left;
                    if (box.right > maxRight) maxRight = box.right;
                    if (box.top < minTop) minTop = box.top;
                    if (box.bottom > maxBottom) maxBottom = box.bottom;
                    if (box.top < firstTaskTop) { firstTaskTop = box.top; firstTaskLeft = box.left; }
                }

                if (!hasAny) continue;

                const pad = BATCH_BRACKET_PADDING_PX;
                const x = Math.max(0, minLeft - pad);
                const y = Math.max(0, minTop - pad);
                const w = Math.max(0, Math.min(centerRect.width - x, maxRight - minLeft + pad * 2));
                const h = Math.max(0, maxBottom - minTop + pad * 2);

                const labelY = Math.max(0, firstTaskTop - BATCH_BRACKET_LABEL_HEIGHT - BATCH_BRACKET_LABEL_OFFSET_Y);
                const labelX = Math.max(0, firstTaskLeft);

                const truncatedLabel = bracket.label.length > BATCH_LABEL_MAX_LENGTH ? bracket.label.substring(0, BATCH_LABEL_MAX_LENGTH - 1) + '…' : bracket.label;
                const estimatedTextWidth = truncatedLabel.length * BATCH_BRACKET_LABEL_FONT_SIZE * 0.6 + BATCH_BRACKET_LABEL_PADDING_X * 2 + 8;
                const maxLabelWidth = Math.max(0, centerRect.width - labelX);
                const labelW = Math.max(0, Math.min(estimatedTextWidth, maxLabelWidth));

                const isHighlighted = highlightedBatchId === bracket.batchId;
                const isBlocked = bracket.hasBlockedTasks;
                const strokeColor = isBlocked ? BATCH_BRACKET_BLOCKED_COLOR : bracket.color;

                bracketBoxes.push({
                    bracket, x, y, w, h, labelX, labelY, labelW, labelH: BATCH_BRACKET_LABEL_HEIGHT,
                    isHighlighted, isBlocked, strokeColor, firstTaskTop, firstTaskLeft,
                });
            }

            const sortedForLabels = [...bracketBoxes].sort((a, b) => {
                if (a.isHighlighted && !b.isHighlighted) return -1;
                if (!a.isHighlighted && b.isHighlighted) return 1;
                return a.firstTaskTop - b.firstTaskTop;
            });

            const visibleLabels: BracketBox[] = [];
            const labelsOverlap = (a: BracketBox, b: BracketBox): boolean => !(
                a.labelX + a.labelW < b.labelX || b.labelX + b.labelW < a.labelX ||
                a.labelY + a.labelH < b.labelY || b.labelY + b.labelH < a.labelY
            );

            for (const box of sortedForLabels) {
                if (box.isHighlighted) { visibleLabels.push(box); continue; }
                if (!visibleLabels.some((v) => labelsOverlap(v, box))) visibleLabels.push(box);
            }

            const visibleLabelSet = new Set(visibleLabels.map((v) => v.bracket.batchId));

            for (const box of bracketBoxes) {
                const { bracket, x, y, w, h, labelX, labelY, labelW, labelH, isHighlighted, isBlocked, strokeColor } = box;
                if (!isFinite(w) || !isFinite(h) || w <= 0 || h <= 0 || !isFinite(x) || !isFinite(y)) continue;

                if (isHighlighted) {
                    const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
                    rect.setAttribute('x', String(x)); rect.setAttribute('y', String(y));
                    rect.setAttribute('width', String(w)); rect.setAttribute('height', String(h));
                    rect.setAttribute('rx', '4'); rect.setAttribute('ry', '4');
                    rect.setAttribute('fill', 'none'); rect.setAttribute('stroke', strokeColor);
                    rect.setAttribute('stroke-width', String(BATCH_BRACKET_STROKE_WIDTH_HIGHLIGHTED));
                    rect.setAttribute('stroke-opacity', String(BATCH_BRACKET_STROKE_OPACITY_HIGHLIGHTED));
                    if (BATCH_BRACKET_DASH_ARRAY_HIGHLIGHTED) rect.setAttribute('stroke-dasharray', BATCH_BRACKET_DASH_ARRAY_HIGHLIGHTED);
                    svg.appendChild(rect);
                } else if (isBlocked) {
                    const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
                    rect.setAttribute('x', String(x)); rect.setAttribute('y', String(y));
                    rect.setAttribute('width', String(w)); rect.setAttribute('height', String(h));
                    rect.setAttribute('rx', '4'); rect.setAttribute('ry', '4');
                    rect.setAttribute('fill', 'none'); rect.setAttribute('stroke', BATCH_BRACKET_BLOCKED_COLOR);
                    rect.setAttribute('stroke-width', String(BATCH_BRACKET_STROKE_WIDTH));
                    rect.setAttribute('stroke-opacity', String(BATCH_BRACKET_STROKE_OPACITY));
                    if (BATCH_BRACKET_DASH_ARRAY) rect.setAttribute('stroke-dasharray', BATCH_BRACKET_DASH_ARRAY);
                    svg.appendChild(rect);
                }

                if (!visibleLabelSet.has(bracket.batchId)) continue;
                if (!isFinite(labelW) || !isFinite(labelH) || labelW <= 0 || labelH <= 0 || !isFinite(labelX) || !isFinite(labelY)) continue;

                const truncatedText = bracket.label.length > BATCH_LABEL_MAX_LENGTH ? bracket.label.substring(0, BATCH_LABEL_MAX_LENGTH - 1) + '…' : bracket.label;

                const isDimmed = highlightedBatchId !== null && !isHighlighted && !isBlocked;
                const labelGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
                labelGroup.setAttribute('class', 'gantt-batch-label-group' + (isHighlighted ? ' highlighted' : '') + (isDimmed ? ` ${DIMMED_LABEL_CLASS}` : ''));
                if (onBracketClick) {
                    labelGroup.style.cursor = 'pointer'; labelGroup.style.pointerEvents = 'auto';
                    labelGroup.addEventListener('click', (ev) => { ev.stopPropagation(); onBracketClick(bracket.batchId); });
                }
                svg.appendChild(labelGroup);

                const labelRect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
                labelRect.setAttribute('x', String(labelX)); labelRect.setAttribute('y', String(labelY));
                labelRect.setAttribute('width', String(labelW)); labelRect.setAttribute('height', String(labelH));
                labelRect.setAttribute('rx', '3'); labelRect.setAttribute('ry', '3');
                labelRect.setAttribute('fill', strokeColor); labelRect.setAttribute('fill-opacity', isHighlighted ? '1' : '0.9');
                if (isHighlighted) { labelRect.setAttribute('stroke', '#ffffff'); labelRect.setAttribute('stroke-width', '1.5'); }
                labelGroup.appendChild(labelRect);

                const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                text.setAttribute('x', String(labelX + BATCH_BRACKET_LABEL_PADDING_X));
                text.setAttribute('y', String(labelY + labelH / 2 + 4));
                text.setAttribute('fill', BATCH_BRACKET_LABEL_TEXT_COLOR);
                text.setAttribute('font-size', `${BATCH_BRACKET_LABEL_FONT_SIZE}px`);
                text.setAttribute('font-weight', '600'); text.setAttribute('font-family', BATCH_BRACKET_LABEL_FONT_FAMILY);
                text.style.pointerEvents = 'none'; text.style.userSelect = 'none';
                text.textContent = `${isBlocked ? '🔒 ' : ''}${truncatedText}`;
                labelGroup.appendChild(text);
            }

            if (window.getComputedStyle(centerPanel).position === 'static') centerPanel.style.position = 'relative';
            centerPanel.appendChild(svg);
        },
        [containerRef, groupByMode, showBatchBrackets, highlightedBatchId, onBracketClick],
    );

    const scheduleDrawBatchBrackets = useCallback(
        (allTasks: TaskData[]) => {
            bracketsPendingTasksRef.current = allTasks;
            if (bracketsRafRef.current !== null) return;
            bracketsRafRef.current = requestAnimationFrame(() => {
                bracketsRafRef.current = null;
                const pending = bracketsPendingTasksRef.current;
                bracketsPendingTasksRef.current = null;
                if (pending) drawBatchBrackets(pending);
            });
        },
        [drawBatchBrackets],
    );

    useEffect(() => {
        const container = containerRef.current;
        if (!container) return;

        const allItems = container.querySelectorAll('.vis-item.link-highlight');
        allItems.forEach((el) => el.classList.remove('link-highlight'));

        if (hoveredLinkTaskIds.length > 0) {
            const idsSet = new Set(hoveredLinkTaskIds);
            const items = container.querySelectorAll('.vis-item.vis-range');
            items.forEach((el) => {
                const visItem = (el as any)['vis-item'];
                if (visItem && visItem.id && idsSet.has(String(visItem.id))) {
                    el.classList.add('link-highlight');
                }
            });
        }
    }, [hoveredLinkTaskIds, containerRef]);

    const renderTimeline = useCallback(
        (tasksData: TaskData[], equipment: string[]) => {
            if (!containerRef.current) return;

            if (timelineRef.current && !suppressViewportSyncRef.current) {
                try {
                    const range = timelineRef.current.getWindow();
                    if (range && range.start && range.end) {
                        viewportRef.current = { start: new Date(range.start).toISOString(), end: new Date(range.end).toISOString() };
                        saveViewportToStorage(viewportRef.current);
                    }
                } catch {}
            }

            if (timelineRef.current) { timelineRef.current.destroy(); timelineRef.current = null; }
            if (minimapRef.current) { minimapRef.current.destroy(); minimapRef.current = null; }

            const container = containerRef.current;
            const existingBrackets = container.querySelector('.gantt-batch-brackets-svg');
            if (existingBrackets && existingBrackets.parentElement) existingBrackets.parentElement.removeChild(existingBrackets);

            container.querySelectorAll(`.${DIMMED_TASK_CLASS}, .${HIGHLIGHTED_TASK_CLASS}`).forEach((el) => {
                el.classList.remove(DIMMED_TASK_CLASS);
                el.classList.remove(HIGHLIGHTED_TASK_CLASS);
            });

            const filteredTasks = filters.filteredTasks;
            setFilteredCount(filteredTasks.length);

            const groupedTasks = groupFillParts(filteredTasks, expandedGroups);

            const built = buildGanttItems({
                filteredTasks: groupedTasks, originalTasks: filteredTasks, equipment,
                showDependencies, showAllDependencies, showSetups, showDowntimes, groupByMode,
            });

            if (built.items.length === 0 && built.weekendBackgrounds.length === 0) {
                if (containerRef.current) containerRef.current.innerHTML = '';
                if (minimapContainerRef.current) minimapContainerRef.current.innerHTML = '';
                return;
            }

            const groupsWithDivider = addGroupDivider(built.groups);
            const groups = new DataSet<GanttGroup>(groupsWithDivider);
            const items = new DataSet<any>(built.items);
            const minimapGroups = new DataSet<GanttGroup>(built.minimapGroups);
            const minimapItems = new DataSet<GanttItem>(built.minimapItems);

            const options: TimelineOptions = {
                groupOrder: 'content', moveable: true, zoomable: true, selectable: true, multiselect: false,
                stack: false, orientation: 'top', showCurrentTime: true, zoomMin: 1000 * 60 * 60 * 2, zoomMax: 1000 * 60 * 60 * 24 * 90,
                margin: {item: 2, axis: 5}, verticalScroll: true, locale: 'ru',
                editable: { add: false, updateTime: localEditMode, updateGroup: false, remove: false },
                onMove: (item: any, callback: (item: any) => void) => {
                    const itemId = String(item?.id ?? '');
                    if (itemId.startsWith('setup_') || itemId.startsWith('weekend_') || itemId.startsWith('__group__')) {
                        const original = tasks.find((t) => t.id === item.id);
                        callback(original ? { ...item, start: original.start, end: original.end } : item);
                        return;
                    }
                    if (isReadOnly) {
                        const original = tasks.find((t) => t.id === item.id);
                        callback(original ? { ...item, start: original.start, end: original.end } : item);
                        return;
                    }
                    try { void onMoveTask(item, callback); }
                    catch (err: any) {
                        const detail = err?.response?.data?.detail;
                        onError(typeof detail === 'string' ? detail : 'Ошибка перемещения задачи');
                        const original = tasks.find((t) => t.id === item.id);
                        callback(original ? { ...item, start: original.start, end: original.end } : item);
                    }
                },
            };

            const newTimeline = new Timeline(containerRef.current, items as any, groups as any, options);
            timelineRef.current = newTimeline;

            requestAnimationFrame(() => {
                if (timelineRef.current) {
                    try { timelineRef.current.redraw(); } catch {}
                }
            });
            setTimeout(() => {
                if (timelineRef.current) {
                    try { timelineRef.current.redraw(); } catch {}
                }
            }, 100);
            setTimeout(() => {
                if (timelineRef.current) {
                    try { timelineRef.current.redraw(); } catch {}
                }
            }, 300);

            const detachNativeListeners = attachNativeDragListeners();
            (newTimeline as any).__detachNativeListeners = detachNativeListeners;

            const saved = viewportRef.current ?? readViewportFromStorage(versionId);
            suppressViewportSyncRef.current = true;

            const applyWindow = (start: Date | string, end: Date | string, label: string) => {
                if (!timelineRef.current) return;
                try { timelineRef.current.setWindow(new Date(start), new Date(end), {animation: false}); }
                catch (err) {
                    console.warn(`[renderTimeline] setWindow (${label}) FAILED`, err);
                    timelineRef.current.fit();
                }
            };

            if (saved) {
                viewportRef.current = saved;
                requestAnimationFrame(() => applyWindow(saved.start, saved.end, 'RAF (saved)'));
                setTimeout(() => applyWindow(saved.start, saved.end, 'timeout 300ms (saved)'), 300);
                setTimeout(() => { suppressViewportSyncRef.current = false; }, 500);
            } else {
                const MAX_FIT_WINDOW_MS = 1000 * 60 * 60 * 24 * 7;
                let minStartMs = Infinity, maxEndMs = -Infinity;
                for (const item of built.items) {
                    if (!item || !item.start || !item.end) continue;
                    const s = new Date(item.start).getTime(), e = new Date(item.end).getTime();
                    if (s < minStartMs) minStartMs = s;
                    if (e > maxEndMs) maxEndMs = e;
                }
                if (isFinite(minStartMs) && isFinite(maxEndMs)) {
                    let windowEndMs = maxEndMs;
                    if (windowEndMs - minStartMs > MAX_FIT_WINDOW_MS) windowEndMs = minStartMs + MAX_FIT_WINDOW_MS;
                    const defaultStart = new Date(minStartMs), defaultEnd = new Date(windowEndMs);
                    viewportRef.current = { start: defaultStart.toISOString(), end: defaultEnd.toISOString() };
                    requestAnimationFrame(() => applyWindow(defaultStart, defaultEnd, 'RAF (default data range)'));
                    setTimeout(() => applyWindow(defaultStart, defaultEnd, 'timeout 300ms (default data range)'), 300);
                    setTimeout(() => { if (viewportRef.current) saveViewportToStorage(viewportRef.current); }, 600);
                }
                setTimeout(() => { suppressViewportSyncRef.current = false; }, 700);
            }

            newTimeline.on('rangechange', () => {
                persistCurrentViewport();
                deps.suppress();
                if (rangeResumeTimerRef.current !== null) clearTimeout(rangeResumeTimerRef.current);
                rangeResumeTimerRef.current = setTimeout(() => { rangeResumeTimerRef.current = null; deps.resume(); }, RANGE_SUPPRESS_DEBOUNCE_MS);
                if (showAllDependencies && !deps.getHoveredTaskId()) deps.scheduleRedraw();
                scheduleDrawBatchBrackets(tasksData);
            });

            newTimeline.on('rangechanged', () => {
                if (rangeResumeTimerRef.current !== null) { clearTimeout(rangeResumeTimerRef.current); rangeResumeTimerRef.current = null; }
                deps.resume();
                if (showAllDependencies && !deps.getHoveredTaskId()) deps.drawDependencies(tasksData);
                scheduleDrawBatchBrackets(tasksData);
            });

            newTimeline.on('changed', () => {
                deps.resume();
                scheduleDrawBatchBrackets(tasksData);
            });

            newTimeline.on('itemover', deps.handleItemOver);
            newTimeline.on('itemout', deps.handleItemOut);

            newTimeline.on('click', (props: any) => {
                if (!props.item) return;
                const itemId = String(props.item);
                const task = tasks.find((t) => t.id === itemId);
                if (!task) {
                    if (itemId.startsWith('__group__') && onToggleGroup) {
                        const groupKey = getGroupKeyFromId(itemId);
                        if (groupKey) onToggleGroup(groupKey);
                    }
                    return;
                }
                if (clickTimeoutRef.current) {
                    clearTimeout(clickTimeoutRef.current);
                    clickTimeoutRef.current = null;
                    if (task.batch_id && !NON_BATCH_VALUES.has(task.batch_id)) onBatchClick(task.batch_id);
                } else {
                    clickTimeoutRef.current = setTimeout(() => { clickTimeoutRef.current = null; }, 300);
                }
            });

            const tryDrawDeps = (attempt: number) => {
                if (!timelineRef.current) return;
                const containerEl = containerRef.current;
                if (!containerEl) return;
                const renderedCount = containerEl.querySelectorAll('.vis-item.vis-range').length;
                if (renderedCount > 0) {
                    deps.drawDependencies(tasksData);
                    scheduleDrawBatchBrackets(tasksData);
                    try { timelineRef.current.redraw(); } catch {}
                } else if (attempt < 30) {
                    setTimeout(() => tryDrawDeps(attempt + 1), 100);
                }
            };
            requestAnimationFrame(() => tryDrawDeps(1));

            try { scheduleDrawBatchBrackets(tasksData); }
            catch (err) { console.warn('[GanttPage] drawBatchBrackets failed:', err); }

            if (!showMinimap || !minimapContainerRef.current) return;

            const minimapOptions: TimelineOptions = buildMinimapTimelineOptions();
            const newMinimap = new Timeline(minimapContainerRef.current, minimapItems as any, minimapGroups as any, minimapOptions);
            minimapRef.current = newMinimap;

            const syncMinimapToMain = () => {
                if (!minimapRef.current || !timelineRef.current || minimapSyncingRef.current) return;
                minimapSyncingRef.current = true;
                try {
                    const range = minimapRef.current.getWindow();
                    timelineRef.current.setWindow(range.start, range.end, {animation: false});
                } finally { setTimeout(() => { minimapSyncingRef.current = false; }, 50); }
            };

            const syncMainToMinimap = () => {
                if (!minimapRef.current || !timelineRef.current || minimapSyncingRef.current) return;
                minimapSyncingRef.current = true;
                try {
                    const range = timelineRef.current.getWindow();
                    minimapRef.current.setWindow(range.start, range.end, {animation: false});
                } finally { setTimeout(() => { minimapSyncingRef.current = false; }, 50); }
            };

            try {
                const mainRange = newTimeline.getWindow();
                newMinimap.setWindow(mainRange.start, mainRange.end, {animation: false});
            } catch {}

            newMinimap.on('rangechange', syncMinimapToMain);
            newTimeline.on('rangechange', () => { persistCurrentViewport(); syncMainToMinimap(); });
        },
        [
            containerRef, minimapContainerRef, timelineRef, minimapRef, tasks, isReadOnly, showMinimap,
            showDependencies, showAllDependencies, showSetups, showDowntimes, versionId, expandedGroups,
            onToggleGroup, viewportRef, suppressViewportSyncRef, minimapSyncingRef, saveViewportToStorage,
            persistCurrentViewport, deps, filters, onTaskEdit, onBatchClick, onMoveTask, onError,
            setFilteredCount, attachNativeDragListeners, groupByMode, scheduleDrawBatchBrackets,
        ],
    );

    const destroyWithListeners = useCallback(() => {
        const tl = timelineRef.current as any;
        if (tl && tl.__detachNativeListeners) {
            try { tl.__detachNativeListeners(); } catch {}
            tl.__detachNativeListeners = null;
        }
        destroy();
    }, [timelineRef, destroy]);

    return { renderTimeline, destroy: destroyWithListeners };
};

const addGroupDivider = (groups: GanttGroup[]): GanttGroup[] => {
    if (groups.length === 0) return groups;
    let lastReactorIdx = -1;
    groups.forEach((g, idx) => { if (g.id.startsWith('REACTOR')) lastReactorIdx = idx; });
    if (lastReactorIdx === -1) return groups;
    return groups.map((g, idx) => {
        if (idx === lastReactorIdx) return { ...g, className: `${g.className || ''} group-divider-after`.trim() };
        if (idx === 0) return { ...g, className: `${g.className || ''} group-first`.trim() };
        return g;
    });
};