// frontend/src/hooks/useGanttActions.ts
/**
 * Хук-агрегатор действий на диаграмме Ганта (Итерация 13.17 + 13.18).
 *
 * Объединяет:
 *  - useCascadeMove (pin/unpin/shift через каскад);
 *  - useTaskResize (move/resize через каскад);
 *  - useDragTooltip (показ tooltip при перетаскивании);
 *  - useRecalculate (пересчёт плана + проверка plan_settings);
 *  - колбэки для TaskContextMenu (копирование ID, показать операции).
 *
 * Итерация 13.18 (fix #5):
 *  - Tooltip теперь показывается из нативных mousemove/mouseup
 *    слушателей (см. useGanttTimeline).
 *  - handleItemChange различает:
 *      * (itemId, start, end, x, y) — полное обновление;
 *      * (itemId, null, null, x, y) — только позиция;
 *      * (null, null, null, 0, 0) — скрыть tooltip.
 */
import {useCallback} from 'react';
import type {Timeline} from 'vis-timeline/standalone';
import {useCascadeMove} from './useCascadeMove';
import {useTaskResize} from './useTaskResize';
import {useDragTooltip} from './useDragTooltip';
import {useRecalculate} from './useRecalculate';
import {ROLE_COLORS, ROLE_COLORS_DEFAULT,} from '../components/gantt/constants';
import type {TaskData, ValidationErrorState} from '../types';

export interface UseGanttActionsOptions {
    /** Все задачи текущего плана. */
    tasks: TaskData[];
    /** Сеттер задач (для оптимистичного обновления). */
    setTasks: React.Dispatch<React.SetStateAction<TaskData[]>>;
    /** ID открытого плана (или null в режиме редактирования). */
    versionId: string | null;
    /** Общий сеттер ошибок (показывается вверху страницы). */
    setError: (message: string | null) => void;
    /** Сеттер состояния ошибки валидации (для MoveValidationDialog). */
    setValidationError: (state: ValidationErrorState) => void;
    /** Открыть диалог задачи (для «Все операции партии»). */
    onOpenTaskDialog: (task: TaskData) => void;
    /** Успешный пересчёт: переключиться на новую версию. */
    onRecalcSuccess: (newVersionId: string) => void;
    /** Пересчёт: у плана нет plan_settings — открыть RecalcSettingsDialog. */
    onRecalcNeedsSettings: () => void;
    /** Реф на Timeline, чтобы обновлять отдельные элементы. */
    timelineRef?: React.MutableRefObject<Timeline | null>;
    /** Активен ли фильтр «только закреплённые». */
    showOnlyPinned?: boolean;
    /** Колбэк для пересчёта filteredCount. */
    onFilteredCountChange?: (count: number) => void;
}

export interface UseGanttActionsResult {
    recalculate: () => Promise<void>;
    recalculating: boolean;
    handleMove: (item: any, callback: (item: any) => void) => Promise<void>;
    handlePinTask: (task: TaskData) => Promise<void>;
    handleUnpinTask: (task: TaskData) => Promise<void>;
    handleShiftTask: (task: TaskData, deltaMinutes: number) => void;
    handleCopyTaskId: (task: TaskData) => void;
    handleCopyBatchId: (task: TaskData) => void;
    handleShowBatchOperations: (task: TaskData) => void;
    /**
     * Колбэк показа tooltip при drag / resize.
     *
     *  - (itemId, start, end, x, y) — полное обновление (показать
     *    новый текст).
     *  - (itemId, null, null, x, y) — только позиция.
     *  - (null, null, null, 0, 0) — скрыть tooltip.
     */
    handleItemChange: (
        itemId: string | null,
        start: Date | null,
        end: Date | null,
        mouseX: number,
        mouseY: number,
    ) => void;
    dragTooltip: ReturnType<typeof useDragTooltip>['tooltip'];
}

export const useGanttActions = (
    options: UseGanttActionsOptions,
): UseGanttActionsResult => {
    const {
        tasks,
        setTasks,
        versionId,
        setError,
        setValidationError,
        onOpenTaskDialog,
        onRecalcSuccess,
        onRecalcNeedsSettings,
        timelineRef,
        showOnlyPinned = false,
        onFilteredCountChange,
    } = options;

    const tooltip = useDragTooltip();

    const recalc = useRecalculate({
        versionId,
        onSuccess: onRecalcSuccess,
        onNeedsSettings: onRecalcNeedsSettings,
        onError: (message) => setError(message),
    });

    const cascadeMove = useCascadeMove({
        versionId,
        onTaskUpdated: (taskId, newStart, newEnd) => {
            setTasks((prev) =>
                prev.map((t) =>
                    t.id === taskId
                        ? {...t, start: newStart, end: newEnd}
                        : t,
                ),
            );
        },
        onCascadeMoved: (movedTasks) => {
            setTasks((prev) =>
                prev.map((t) => {
                    const moved = movedTasks.find(
                        (m) => m.task_id === t.id,
                    );
                    return moved
                        ? {
                            ...t,
                            start: moved.new_start,
                            end: moved.new_end,
                        }
                        : t;
                }),
            );
        },
        onError: (msg) => setError(msg),
        onValidationError: setValidationError,
    });

    const taskResize = useTaskResize({
        tasks,
        versionId,
        onTaskUpdated: (taskId, newStart, newEnd) => {
            setTasks((prev) =>
                prev.map((t) =>
                    t.id === taskId
                        ? {...t, start: newStart, end: newEnd}
                        : t,
                ),
            );
        },
        onCascadeMoved: (movedTasks) => {
            setTasks((prev) =>
                prev.map((t) => {
                    const moved = movedTasks.find(
                        (m) => m.task_id === t.id,
                    );
                    return moved
                        ? {
                            ...t,
                            start: moved.new_start,
                            end: moved.new_end,
                        }
                        : t;
                }),
            );
        },
        onError: (msg) => setError(msg),
        onValidationError: setValidationError,
    });

    // ==========================================
    // handleItemChange — показ tooltip
    // ==========================================
    const handleItemChange = useCallback((
        itemId: string | null,
        start: Date | null,
        end: Date | null,
        mouseX: number,
        mouseY: number,
    ) => {
        // Скрыть tooltip
        if (!itemId) {
            tooltip.hide();
            return;
        }

        // Найти задачу
        const task = tasks.find((t) => t.id === itemId);
        if (!task) return;

        // Не показываем для setup / downtime / group
        if (
            itemId.startsWith('setup_') ||
            itemId.startsWith('weekend_') ||
            itemId.startsWith('__group__')
        ) {
            return;
        }

        // Только позиция (без обновления текста)
        if (start === null && end === null) {
            tooltip.updatePosition(mouseX, mouseY);
            return;
        }

        // Полное обновление (позиция + текст)
        const realStart = start ?? new Date(task.start);
        const realEnd = end ?? new Date(task.end);

        const durationMin = Math.round(
            (realEnd.getTime() - realStart.getTime()) / 60000,
        );
        const originalDurationMin = task.duration_minutes;
        const deltaMinutes = durationMin - originalDurationMin;

        // Определяем resize: длительность изменилась > 1 мин
        const isResize = Math.abs(deltaMinutes) > 0;

        const operationType: 'move' | 'resize' = isResize
            ? 'resize'
            : 'move';

        tooltip.show(
            mouseX,
            mouseY,
            `Длительность: ${durationMin} мин`,
            {
                operationType,
                startTime: realStart.toISOString(),
                endTime: realEnd.toISOString(),
                originalStart: task.start,
                originalEnd: task.end,
                deltaMinutes,
            },
        );
    }, [tasks, tooltip]);

    // ==========================================
    // Обновление конкретного item в vis-timeline
    // ==========================================
    const updateTimelineItem = useCallback(
        (task: TaskData, isPinned: boolean) => {
            if (!timelineRef?.current) return;
            const itemsData: any = (timelineRef.current as any)
                .itemsData;
            if (!itemsData) return;

            const existing = itemsData.get(task.id);
            if (!existing) return;

            const {style, className} = buildTaskStyle(task, isPinned);
            const content = buildTaskContent(task, isPinned);

            itemsData.update({
                ...existing,
                content,
                style,
                className,
            });
        },
        [timelineRef],
    );

    const removeTimelineItem = useCallback(
        (taskId: string) => {
            if (!timelineRef?.current) return;
            const itemsData: any = (timelineRef.current as any)
                .itemsData;
            if (!itemsData) return;

            try {
                itemsData.remove(taskId);
            } catch {
                // ignore
            }
        },
        [timelineRef],
    );

    // ==========================================
    // Пересчёт filteredCount
    // ==========================================
    const recalcFilteredCount = useCallback(() => {
        if (!onFilteredCountChange || !timelineRef?.current) {
            return;
        }
        const itemsData: any = (timelineRef.current as any)
            .itemsData;
        if (!itemsData) return;

        const visibleIds: string[] = itemsData.getIds() || [];
        const realTaskCount = visibleIds.filter(
            (id) =>
                !id.startsWith('setup_') &&
                !id.startsWith('weekend_') &&
                !id.startsWith('__group__'),
        ).length;

        onFilteredCountChange(realTaskCount);
    }, [onFilteredCountChange, timelineRef]);

    // ==========================================
    // Pin / Unpin
    // ==========================================
    const handlePinTask = useCallback(
        async (task: TaskData) => {
            await cascadeMove.togglePin(task, true);
            setTasks((prev) =>
                prev.map((t) =>
                    t.id === task.id ? {...t, is_pinned: true} : t,
                ),
            );
            updateTimelineItem(task, true);
            recalcFilteredCount();
        },
        [
            cascadeMove,
            setTasks,
            updateTimelineItem,
            recalcFilteredCount,
        ],
    );

    const handleUnpinTask = useCallback(
        async (task: TaskData) => {
            await cascadeMove.togglePin(task, false);
            setTasks((prev) =>
                prev.map((t) =>
                    t.id === task.id ? {...t, is_pinned: false} : t,
                ),
            );

            if (showOnlyPinned) {
                removeTimelineItem(task.id);
            } else {
                updateTimelineItem(task, false);
            }
            recalcFilteredCount();
        },
        [
            cascadeMove,
            setTasks,
            showOnlyPinned,
            updateTimelineItem,
            removeTimelineItem,
            recalcFilteredCount,
        ],
    );

    const handleShiftTask = useCallback(
        (task: TaskData, deltaMinutes: number) => {
            void cascadeMove.shiftTask(task, deltaMinutes);
        },
        [cascadeMove],
    );

    const handleCopyTaskId = useCallback((task: TaskData) => {
        void navigator.clipboard.writeText(task.id);
    }, []);

    const handleCopyBatchId = useCallback((task: TaskData) => {
        if (task.batch_id) {
            void navigator.clipboard.writeText(task.batch_id);
        }
    }, []);

    const handleShowBatchOperations = useCallback(
        (task: TaskData) => {
            onOpenTaskDialog(task);
        },
        [onOpenTaskDialog],
    );

    return {
        recalculate: recalc.recalculate,
        recalculating: recalc.recalculating,
        handleMove: taskResize.handleMove,
        handlePinTask,
        handleUnpinTask,
        handleShiftTask,
        handleCopyTaskId,
        handleCopyBatchId,
        handleShowBatchOperations,
        handleItemChange,
        dragTooltip: tooltip.tooltip,
    };
};

// ==========================================
// Утилиты построения content и style
// ==========================================

const buildTaskContent = (
    task: TaskData,
    isPinned: boolean,
): string => {
    const prefix = isPinned ? '📌 ' : '';
    const blockedIcon = task.is_lab_blocked ? '🔒 ' : '';
    const slowCoolingIcon =
        task.cooling_mode === 'slow' ? '⏳ ' : '';
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

    const contentColor = isPinned
        ? '#1976d2'
        : task.is_lab_blocked
            ? '#e74c3c'
            : task.cooling_mode === 'slow'
                ? '#e67e22'
                : '#2c3e50';

    return `
        <div style="padding: 4px; font-size: 11px;">
          <div style="font-weight: bold; color: ${contentColor}; margin-bottom: 2px;">
            ${prefix}${blockedIcon}${slowCoolingIcon}${czIcon}${shortName}
          </div>
          <div style="font-size: 10px; color: #555;">${task.duration_minutes} мин</div>
        </div>
    `;
};

const buildTaskStyle = (
    task: TaskData,
    isPinned: boolean,
): {style: string; className: string} => {
    if (isPinned) {
        return {
            style:
                `background-color: #e3f2fd; ` +
                `border: 2px solid #1976d2; ` +
                `border-left: 6px solid #1976d2; ` +
                `border-radius: 4px; ` +
                `box-shadow: 0 0 4px rgba(25, 118, 210, 0.35);`,
            className: 'item-pinned',
        };
    }

    const roleColor =
        ROLE_COLORS[task.task_role || ''] || ROLE_COLORS_DEFAULT;
    return {
        style: `background-color: ${roleColor}25; border-left: 4px solid ${roleColor}; border-radius: 4px;`,
        className: '',
    };
};