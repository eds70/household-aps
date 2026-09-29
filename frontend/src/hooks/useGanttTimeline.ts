// frontend/src/hooks/useGanttTimeline.ts
import type {MutableRefObject, RefObject} from 'react';
/**
 * Хук для рендера основного Timeline и миникарты (Итерация 13.17 + 13.18).
 *
 * Итерация 13.18 (fix #5):
 *   - vis-timeline 8.x НЕ генерирует события itemmoving / itemmoved /
 *     itemresizing / itemresized. Поэтому tooltip при перетаскивании
 *     и resize показывается через нативные pointer-события на
 *     контейнере диаграммы.
 *   - Тип операции (move | resize) определяется по DOM-зоне под
 *     курсором: .vis-drag-left / .vis-drag-right → resize,
 *     .vis-drag-center → move.
 *   - Оптимизации против мерцания:
 *       * rAF-троттлинг pointermove;
 *       * разделение обновления позиции (каждый кадр) и текста
 *         (раз в 150 мс);
 *       * DragTooltip использует transform: translate вместо left/top.
 *   - Pointer Events API: vis-timeline 8.x слушает pointerdown и
 *     делает preventDefault, из-за чего mousedown НЕ генерируется.
 *     Поэтому основной набор слушателей — pointerdown / pointermove /
 *     pointerup; mouse-события оставлены как fallback.
 */
import {useCallback, useRef} from 'react';
import {Timeline, type TimelineOptions} from 'vis-timeline/standalone';
import {DataSet} from 'vis-data';

import type {TaskData} from '../types';
import type {GanttGroup, GanttItem, ViewportState,} from '../components/gantt/types';
import {NON_BATCH_VALUES} from '../components/gantt/constants';
import {buildGanttItems} from '../utils/ganttRenderItems';
import {buildMinimapTimelineOptions} from '../utils/ganttTimelineOptions';
import {getGroupKeyFromId, groupFillParts} from '../utils/ganttGroups';
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

    /**
     * Колбэк показа tooltip. Вызывается:
     *  - с (itemId, start, end, x, y) — полное обновление
     *    (при первом показе и раз в ~150 мс при движении);
     *  - с (itemId, null, null, x, y) — только позиция
     *    (быстрое обновление каждый кадр);
     *  - с (null, null, null, 0, 0) — скрыть tooltip.
     */
    onItemChange?: (
        itemId: string | null,
        start: Date | null,
        end: Date | null,
        mouseX: number,
        mouseY: number,
    ) => void;
}

export interface UseGanttTimelineResult {
    renderTimeline: (tasksData: TaskData[], equipment: string[]) => void;
    destroy: () => void;
}

// ==========================================
// Константы
// ==========================================

const TEXT_UPDATE_INTERVAL_MS = 150;
const TOOLTIP_HIDE_DELAY_MS = 1200;
const MIN_TASK_DURATION_MS = 60_000; // 1 минута

export const useGanttTimeline = (
    params: UseGanttTimelineParams,
): UseGanttTimelineResult => {
    const {
        containerRef,
        minimapContainerRef,
        timelineRef,
        minimapRef,
        tasks,
        isReadOnly,
        showMinimap,
        showDependencies,
        showAllDependencies,
        showSetups,
        showDowntimes,
        versionId,
        expandedGroups,
        onToggleGroup,
        viewportRef,
        suppressViewportSyncRef,
        minimapSyncingRef,
        saveViewportToStorage,
        persistCurrentViewport,
        deps,
        filters,
        onTaskEdit,
        onBatchClick,
        onMoveTask,
        onError,
        setFilteredCount,
        onItemChange,
    } = params;

    const clickTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    // ==========================================
    // Рефы для нативных слушателей drag
    // ==========================================
    const dragStateRef = useRef<{
        itemId: string;
        operationType: 'move' | 'resize';
        startX: number;
        originalStartMs: number;
        originalEndMs: number;
        originalDurationMs: number;
        msPerPx: number;
        fixedEndMs: number;
        fixedStartMs: number;
        lastMouseX: number;
        lastMouseY: number;
        tooltipShown: boolean;
    } | null>(null);

    const rafIdRef = useRef<number | null>(null);
    const pendingEventRef = useRef<PointerEvent | MouseEvent | null>(null);
    const lastTextUpdateAtRef = useRef<number>(0);
    const hideTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    const destroy = useCallback(() => {
        if (timelineRef.current) {
            timelineRef.current.destroy();
            timelineRef.current = null;
        }
        if (minimapRef.current) {
            minimapRef.current.destroy();
            minimapRef.current = null;
        }
        if (clickTimeoutRef.current) {
            clearTimeout(clickTimeoutRef.current);
            clickTimeoutRef.current = null;
        }
        if (rafIdRef.current !== null) {
            cancelAnimationFrame(rafIdRef.current);
            rafIdRef.current = null;
        }
        if (hideTimerRef.current !== null) {
            clearTimeout(hideTimerRef.current);
            hideTimerRef.current = null;
        }
    }, [timelineRef, minimapRef]);

    // ==========================================
    // Хелперы
    // ==========================================

    const detectOperationType = (
        target: HTMLElement,
    ): 'move' | 'resize' => {
        // vis-timeline рисует внутри .vis-item.vis-range три зоны:
        //   .vis-drag-left   — resize за начало
        //   .vis-drag-center — move
        //   .vis-drag-right  — resize за конец
        if (target.closest('.vis-drag-left')) return 'resize';
        if (target.closest('.vis-drag-right')) return 'resize';
        return 'move';
    };

    const getTaskIdFromElement = (
        el: HTMLElement | null,
    ): string | null => {
        if (!el) return null;
        const itemEl = el.closest(
            '.vis-item.vis-range',
        ) as HTMLElement | null;
        if (!itemEl) return null;
        const visItem = (itemEl as any)['vis-item'];
        if (!visItem || !visItem.id) return null;
        return String(visItem.id);
    };

    // ==========================================
    // Нативные слушатели drag (pointer + mouse fallback)
    // ==========================================
    const attachNativeDragListeners = useCallback(() => {
        const container = containerRef.current;
        if (!container) return () => {};

        // --------------------------------------------------
        // pointerdown — начать drag
        // --------------------------------------------------
        const onPointerDown = (e: PointerEvent) => {
            const target = e.target as HTMLElement;

            // Только по задачам
            if (!target?.closest('.vis-item.vis-range')) return;

            const itemId = getTaskIdFromElement(target);
            if (!itemId) return;

            // setup / downtime / group — не тащим
            if (
                itemId.startsWith('setup_') ||
                itemId.startsWith('weekend_') ||
                itemId.startsWith('__group__')
            ) {
                return;
            }

            const task = tasks.find((t) => t.id === itemId);
            if (!task) return;

            if (isReadOnly) return;

            const timeline = timelineRef.current;
            if (!timeline) return;

            const operationType = detectOperationType(target);

            // Считаем msPerPx = (window.end - window.start) / clientWidth
            // центральной панели диаграммы.
            let msPerPx = 1;
            try {
                const range = timeline.getWindow();
                const totalMs =
                    range.end.getTime() - range.start.getTime();
                const centerPanel = container.querySelector(
                    '.vis-panel.vis-center',
                ) as HTMLElement | null;
                const panelWidth =
                    centerPanel?.clientWidth ||
                    container.clientWidth ||
                    1;
                msPerPx = totalMs / panelWidth;
            } catch {
                // ignore
            }

            const startMs = new Date(task.start).getTime();
            const endMs = new Date(task.end).getTime();

            dragStateRef.current = {
                itemId,
                operationType,
                startX: e.clientX,
                originalStartMs: startMs,
                originalEndMs: endMs,
                originalDurationMs: endMs - startMs,
                msPerPx,
                fixedEndMs: endMs,
                fixedStartMs: startMs,
                lastMouseX: e.clientX,
                lastMouseY: e.clientY,
                tooltipShown: false,
            };

            // Сброс состояния rAF
            if (rafIdRef.current !== null) {
                cancelAnimationFrame(rafIdRef.current);
                rafIdRef.current = null;
            }
            pendingEventRef.current = null;
            lastTextUpdateAtRef.current = 0;

            // Отменяем скрытие tooltip (если таймер уже тикал)
            if (hideTimerRef.current !== null) {
                clearTimeout(hideTimerRef.current);
                hideTimerRef.current = null;
            }
        };

        // --------------------------------------------------
        // pointermove — обновить tooltip (rAF-троттлинг)
        // --------------------------------------------------
        const onPointerMove = (e: PointerEvent) => {
            const st = dragStateRef.current;
            if (!st) return;

            st.lastMouseX = e.clientX;
            st.lastMouseY = e.clientY;

            // rAF-троттлинг: одно обновление на кадр
            pendingEventRef.current = e;
            if (rafIdRef.current !== null) return;

            rafIdRef.current = requestAnimationFrame(() => {
                rafIdRef.current = null;
                const ev = pendingEventRef.current;
                pendingEventRef.current = null;
                if (!ev || !dragStateRef.current) return;

                const state = dragStateRef.current;

                // Считаем новое время
                const deltaPx = ev.clientX - state.startX;
                const deltaMs = deltaPx * state.msPerPx;

                let newStartMs: number;
                let newEndMs: number;

                if (state.operationType === 'move') {
                    newStartMs = state.originalStartMs + deltaMs;
                    newEndMs = state.originalEndMs + deltaMs;
                } else {
                    // resize: определяем, за какой край тянут
                    const originalWidthPx =
                        state.originalDurationMs / state.msPerPx;
                    const midX = state.startX + originalWidthPx / 2;

                    if (ev.clientX < midX) {
                        // Тянем за левый край: фиксирован конец
                        newStartMs = state.originalStartMs + deltaMs;
                        newEndMs = state.fixedEndMs;
                        if (
                            newStartMs >=
                            newEndMs - MIN_TASK_DURATION_MS
                        ) {
                            newStartMs =
                                newEndMs - MIN_TASK_DURATION_MS;
                        }
                    } else {
                        // Тянем за правый край: фиксировано начало
                        newStartMs = state.fixedStartMs;
                        newEndMs = state.originalEndMs + deltaMs;
                        if (
                            newEndMs <=
                            newStartMs + MIN_TASK_DURATION_MS
                        ) {
                            newEndMs =
                                newStartMs + MIN_TASK_DURATION_MS;
                        }
                    }
                }

                if (!onItemChange) return;

                const now = performance.now();
                const shouldUpdateText =
                    now - lastTextUpdateAtRef.current >
                    TEXT_UPDATE_INTERVAL_MS;

                if (!state.tooltipShown) {
                    // Первый показ — полное обновление
                    onItemChange(
                        state.itemId,
                        new Date(newStartMs),
                        new Date(newEndMs),
                        ev.clientX,
                        ev.clientY,
                    );
                    state.tooltipShown = true;
                    lastTextUpdateAtRef.current = now;
                } else if (shouldUpdateText) {
                    // Обновляем и позицию, и текст (реже)
                    onItemChange(
                        state.itemId,
                        new Date(newStartMs),
                        new Date(newEndMs),
                        ev.clientX,
                        ev.clientY,
                    );
                    lastTextUpdateAtRef.current = now;
                } else {
                    // Обновляем только позицию — быстро
                    onItemChange(
                        state.itemId,
                        null,
                        null,
                        ev.clientX,
                        ev.clientY,
                    );
                }
            });
        };

        // --------------------------------------------------
        // pointerup — завершить drag
        // --------------------------------------------------
        const onPointerUp = () => {
            const st = dragStateRef.current;
            dragStateRef.current = null;

            if (rafIdRef.current !== null) {
                cancelAnimationFrame(rafIdRef.current);
                rafIdRef.current = null;
            }
            pendingEventRef.current = null;

            // vis-timeline сам вызовет onMove и обновит задачу.
            // Скрываем tooltip через небольшую задержку.
            if (onItemChange && st?.itemId) {
                if (hideTimerRef.current !== null) {
                    clearTimeout(hideTimerRef.current);
                }
                hideTimerRef.current = setTimeout(() => {
                    hideTimerRef.current = null;
                    onItemChange(null, null, null, 0, 0);
                }, TOOLTIP_HIDE_DELAY_MS);
            }
        };

        // --------------------------------------------------
        // Mouse-event обёртки (fallback для старых браузеров
        // и на случай, если pointerdown был preventDefault'нут)
        // --------------------------------------------------
        const onMouseDown = (e: MouseEvent) => {
            // Дедупликация: если уже обработали pointerdown
            // для того же самого события — не обрабатываем.
            // В современных браузерах mouse приходит после pointer,
            // но с задержкой; если pointer сработал, mousedown может
            // вообще не прийти (если был preventDefault).
            onPointerDown(e as unknown as PointerEvent);
        };

        const onMouseMove = (e: MouseEvent) => {
            // Если drag ещё не начат (pointerdown не сработал),
            // mousemove ничего не делает.
            if (!dragStateRef.current) return;
            onPointerMove(e as unknown as PointerEvent);
        };

        const onMouseUp = () => {
            if (!dragStateRef.current) return;
            onPointerUp();
        };

        // --------------------------------------------------
        // Регистрация: pointer + mouse (fallback)
        // --------------------------------------------------
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
    }, [
        containerRef,
        timelineRef,
        tasks,
        isReadOnly,
        onItemChange,
    ]);

    // ==========================================
    // Основной рендер
    // ==========================================
    const renderTimeline = useCallback(
        (tasksData: TaskData[], equipment: string[]) => {
            if (!containerRef.current) return;

            // 1. Сохранить viewport
            if (
                timelineRef.current &&
                !suppressViewportSyncRef.current
            ) {
                try {
                    const range = timelineRef.current.getWindow();
                    if (range && range.start && range.end) {
                        viewportRef.current = {
                            start: new Date(range.start).toISOString(),
                            end: new Date(range.end).toISOString(),
                        };
                        saveViewportToStorage(viewportRef.current);
                    }
                } catch {
                    // ignore
                }
            }

            // 2. Destroy старых
            if (timelineRef.current) {
                timelineRef.current.destroy();
                timelineRef.current = null;
            }
            if (minimapRef.current) {
                minimapRef.current.destroy();
                minimapRef.current = null;
            }

            // 3. Данные
            const filteredTasks = filters.filteredTasks;
            setFilteredCount(filteredTasks.length);

            const groupedTasks = groupFillParts(
                filteredTasks,
                expandedGroups,
            );

            const built = buildGanttItems({
                filteredTasks: groupedTasks,
                equipment,
                showDependencies,
                showAllDependencies,
                showSetups,
                showDowntimes,
            });

            if (
                built.items.length === 0 &&
                built.weekendBackgrounds.length === 0
            ) {
                if (containerRef.current)
                    containerRef.current.innerHTML = '';
                if (minimapContainerRef.current)
                    minimapContainerRef.current.innerHTML = '';
                return;
            }

            // 4. DataSet
            const groupsWithDivider = addGroupDivider(built.groups);
            const groups = new DataSet<GanttGroup>(groupsWithDivider);
            const items = new DataSet<any>(built.items);
            const minimapGroups = new DataSet<GanttGroup>(
                built.minimapGroups,
            );
            const minimapItems = new DataSet<GanttItem>(
                built.minimapItems,
            );

            // 5. Опции Timeline
            const options: TimelineOptions = {
                groupOrder: 'content',
                moveable: true,
                zoomable: true,
                selectable: true,
                multiselect: false,
                stack: false,
                orientation: 'top',
                showCurrentTime: true,
                zoomMin: 1000 * 60 * 60 * 2,
                zoomMax: 1000 * 60 * 60 * 24 * 90,
                margin: {item: 2, axis: 5},
                verticalScroll: true,
                locale: 'ru',
                editable: {
                    add: false,
                    updateTime: !isReadOnly,
                    updateGroup: false,
                    remove: false,
                },
                onMove: (item: any, callback: (item: any) => void) => {
                    const itemId = String(item?.id ?? '');
                    if (
                        itemId.startsWith('setup_') ||
                        itemId.startsWith('weekend_') ||
                        itemId.startsWith('__group__')
                    ) {
                        const original = tasks.find(
                            (t) => t.id === item.id,
                        );
                        callback(
                            original
                                ? {
                                    ...item,
                                    start: original.start,
                                    end: original.end,
                                }
                                : item,
                        );
                        return;
                    }

                    if (isReadOnly) {
                        const original = tasks.find(
                            (t) => t.id === item.id,
                        );
                        callback(
                            original
                                ? {
                                    ...item,
                                    start: original.start,
                                    end: original.end,
                                }
                                : item,
                        );
                        return;
                    }

                    try {
                        void onMoveTask(item, callback);
                    } catch (err: any) {
                        const detail = err?.response?.data?.detail;
                        onError(
                            typeof detail === 'string'
                                ? detail
                                : 'Ошибка перемещения задачи',
                        );
                        const original = tasks.find(
                            (t) => t.id === item.id,
                        );
                        callback(
                            original
                                ? {
                                    ...item,
                                    start: original.start,
                                    end: original.end,
                                }
                                : item,
                        );
                    }
                },
            };

            // 6. Создать Timeline
            const newTimeline = new Timeline(
                containerRef.current,
                items as any,
                groups as any,
                options,
            );
            timelineRef.current = newTimeline;

            // 7. Прикрепить нативные слушатели drag (tooltip)
            const detachNativeListeners = attachNativeDragListeners();

            // Сохраняем cleanup на случай destroy
            (newTimeline as any).__detachNativeListeners =
                detachNativeListeners;

            // 8. Viewport
            const saved =
                viewportRef.current ??
                readViewportFromStorage(versionId);

            suppressViewportSyncRef.current = true;

            const applyWindow = (
                start: Date | string,
                end: Date | string,
                label: string,
            ) => {
                if (!timelineRef.current) return;
                try {
                    timelineRef.current.setWindow(
                        new Date(start),
                        new Date(end),
                        {animation: false},
                    );
                } catch (err) {
                    console.warn(
                        `[renderTimeline] setWindow (${label}) FAILED`,
                        err,
                    );
                    timelineRef.current.fit();
                }
            };

            if (saved) {
                viewportRef.current = saved;
                requestAnimationFrame(() => {
                    applyWindow(saved.start, saved.end, 'RAF (saved)');
                });
                setTimeout(() => {
                    applyWindow(
                        saved.start,
                        saved.end,
                        'timeout 300ms (saved)',
                    );
                }, 300);
                setTimeout(() => {
                    suppressViewportSyncRef.current = false;
                }, 500);
            } else {
                const MAX_FIT_WINDOW_MS = 1000 * 60 * 60 * 24 * 7;
                let minStartMs = Infinity;
                let maxEndMs = -Infinity;
                for (const item of built.items) {
                    if (!item || !item.start || !item.end) continue;
                    const s = new Date(item.start).getTime();
                    const e = new Date(item.end).getTime();
                    if (s < minStartMs) minStartMs = s;
                    if (e > maxEndMs) maxEndMs = e;
                }

                if (isFinite(minStartMs) && isFinite(maxEndMs)) {
                    let windowEndMs = maxEndMs;
                    if (
                        windowEndMs - minStartMs >
                        MAX_FIT_WINDOW_MS
                    ) {
                        windowEndMs =
                            minStartMs + MAX_FIT_WINDOW_MS;
                    }
                    const defaultStart = new Date(minStartMs);
                    const defaultEnd = new Date(windowEndMs);
                    viewportRef.current = {
                        start: defaultStart.toISOString(),
                        end: defaultEnd.toISOString(),
                    };
                    requestAnimationFrame(() => {
                        applyWindow(
                            defaultStart,
                            defaultEnd,
                            'RAF (default data range)',
                        );
                    });
                    setTimeout(() => {
                        applyWindow(
                            defaultStart,
                            defaultEnd,
                            'timeout 300ms (default data range)',
                        );
                    }, 300);
                    setTimeout(() => {
                        if (viewportRef.current) {
                            saveViewportToStorage(
                                viewportRef.current,
                            );
                        }
                    }, 600);
                }
                setTimeout(() => {
                    suppressViewportSyncRef.current = false;
                }, 700);
            }

            // 9. Обработчики
            newTimeline.on('rangechange', () => {
                persistCurrentViewport();
                if (
                    showAllDependencies &&
                    !deps.getHoveredTaskId()
                ) {
                    deps.scheduleRedraw();
                }
            });

            newTimeline.on('rangechanged', () => {
                if (
                    showAllDependencies &&
                    !deps.getHoveredTaskId()
                ) {
                    deps.drawDependencies(tasksData);
                }
            });

            newTimeline.on('changed', () => {
                deps.scheduleRedraw();
            });

            newTimeline.on('itemover', deps.handleItemOver);
            newTimeline.on('itemout', deps.handleItemOut);

            // 10. Клик
            newTimeline.on('click', (props: any) => {
                if (!props.item) return;
                const itemId = String(props.item);
                const task = tasks.find((t) => t.id === itemId);

                if (!task) {
                    if (
                        itemId.startsWith('__group__') &&
                        onToggleGroup
                    ) {
                        const groupKey =
                            getGroupKeyFromId(itemId);
                        if (groupKey) onToggleGroup(groupKey);
                    }
                    return;
                }

                if (clickTimeoutRef.current) {
                    clearTimeout(clickTimeoutRef.current);
                    clickTimeoutRef.current = null;
                    if (
                        task.batch_id &&
                        !NON_BATCH_VALUES.has(task.batch_id)
                    ) {
                        onBatchClick(task.batch_id);
                    }
                } else {
                    clickTimeoutRef.current = setTimeout(() => {
                        clickTimeoutRef.current = null;
                    }, 300);
                }
            });

            // 11. Зависимости
            const tryDrawDeps = (attempt: number) => {
                if (!timelineRef.current) return;
                const containerEl = containerRef.current;
                if (!containerEl) return;

                const renderedCount =
                    containerEl.querySelectorAll(
                        '.vis-item.vis-range',
                    ).length;

                if (renderedCount > 0) {
                    deps.drawDependencies(tasksData);
                } else if (attempt < 30) {
                    setTimeout(
                        () => tryDrawDeps(attempt + 1),
                        100,
                    );
                }
            };
            requestAnimationFrame(() => {
                tryDrawDeps(1);
            });

            // 12. Миникарта
            if (!showMinimap || !minimapContainerRef.current) return;

            const minimapOptions: TimelineOptions =
                buildMinimapTimelineOptions();
            const newMinimap = new Timeline(
                minimapContainerRef.current,
                minimapItems as any,
                minimapGroups as any,
                minimapOptions,
            );
            minimapRef.current = newMinimap;

            const syncMinimapToMain = () => {
                if (!minimapRef.current || !timelineRef.current)
                    return;
                if (minimapSyncingRef.current) return;
                minimapSyncingRef.current = true;
                try {
                    const range = minimapRef.current.getWindow();
                    timelineRef.current.setWindow(
                        range.start,
                        range.end,
                        {animation: false},
                    );
                } finally {
                    setTimeout(() => {
                        minimapSyncingRef.current = false;
                    }, 50);
                }
            };

            const syncMainToMinimap = () => {
                if (!minimapRef.current || !timelineRef.current)
                    return;
                if (minimapSyncingRef.current) return;
                minimapSyncingRef.current = true;
                try {
                    const range = timelineRef.current.getWindow();
                    minimapRef.current.setWindow(
                        range.start,
                        range.end,
                        {animation: false},
                    );
                } finally {
                    setTimeout(() => {
                        minimapSyncingRef.current = false;
                    }, 50);
                }
            };

            try {
                const mainRange = newTimeline.getWindow();
                newMinimap.setWindow(
                    mainRange.start,
                    mainRange.end,
                    {animation: false},
                );
            } catch {
                // ignore
            }

            newMinimap.on('rangechange', syncMinimapToMain);
            newTimeline.on('rangechange', () => {
                persistCurrentViewport();
                syncMainToMinimap();
            });
        },
        [
            containerRef,
            minimapContainerRef,
            timelineRef,
            minimapRef,
            tasks,
            isReadOnly,
            showMinimap,
            showDependencies,
            showAllDependencies,
            showSetups,
            showDowntimes,
            versionId,
            expandedGroups,
            onToggleGroup,
            viewportRef,
            suppressViewportSyncRef,
            minimapSyncingRef,
            saveViewportToStorage,
            persistCurrentViewport,
            deps,
            filters,
            onTaskEdit,
            onBatchClick,
            onMoveTask,
            onError,
            setFilteredCount,
            attachNativeDragListeners,
        ],
    );

    // Cleanup нативных слушателей при destroy
    const destroyWithListeners = useCallback(() => {
        const tl = timelineRef.current as any;
        if (tl && tl.__detachNativeListeners) {
            try {
                tl.__detachNativeListeners();
            } catch {
                // ignore
            }
            tl.__detachNativeListeners = null;
        }
        destroy();
    }, [timelineRef, destroy]);

    return {
        renderTimeline,
        destroy: destroyWithListeners,
    };
};

// ==========================================
// Разделитель групп (последний реактор)
// ==========================================

const addGroupDivider = (groups: GanttGroup[]): GanttGroup[] => {
    if (groups.length === 0) return groups;

    let lastReactorIdx = -1;
    groups.forEach((g, idx) => {
        if (g.id.startsWith('REACTOR')) {
            lastReactorIdx = idx;
        }
    });

    if (lastReactorIdx === -1) return groups;

    return groups.map((g, idx) => {
        if (idx === lastReactorIdx) {
            return {
                ...g,
                className: `${g.className || ''} group-divider-after`.trim(),
            };
        }
        if (idx === 0) {
            return {
                ...g,
                className: `${g.className || ''} group-first`.trim(),
            };
        }
        return g;
    });
};