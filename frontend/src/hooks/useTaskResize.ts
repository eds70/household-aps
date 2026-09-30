// frontend/src/hooks/useTaskResize.ts
/**
 * Хук для обработки resize задачи (изменение длительности) на Ганте.
 *
 * Итерация 13.17.
 * Итерация 13.19: после успешного API-вызова помечаем план «грязным»
 *   (markPlanDirty), потому что новая длительность задачи влияет
 *   на следующий пересчёт solver'ом.
 */
import {useCallback} from 'react';
import {rescheduleApi} from '../services/api';
import {usePlan} from '../context/PlainContext';
import type {TaskData, ValidationErrorState} from '../types';

export interface UseTaskResizeOptions {
    tasks: TaskData[];
    versionId: string | null;
    onTaskUpdated: (
        taskId: string,
        newStart: string,
        newEnd: string,
        durationMin: number,
    ) => void;
    onCascadeMoved: (
        movedTasks: Array<{ task_id: string; new_start: string; new_end: string }>,
    ) => void;
    onError: (message: string) => void;
    onValidationError: (state: ValidationErrorState) => void;
}

export interface UseTaskResizeResult {
    handleMove: (item: any, callback: (item: any) => void) => Promise<void>;
}

export const useTaskResize = (
    options: UseTaskResizeOptions,
): UseTaskResizeResult => {
    const {
        tasks,
        versionId,
        onTaskUpdated,
        onCascadeMoved,
        onError,
        onValidationError,
    } = options;

    // Итерация 13.19: пометка плана «грязным»
    const {markPlanDirty} = usePlan();

    const handleMove = useCallback(async (
        item: any,
        callback: (item: any) => void,
    ) => {
        const taskId = String(item?.id ?? '');
        if (!taskId) {
            callback(item);
            return;
        }

        // Не обрабатываем setup, downtime, группы
        if (
            taskId.startsWith('setup_') ||
            taskId.startsWith('weekend_') ||
            taskId.startsWith('__group__')
        ) {
            const original = tasks.find((t) => t.id === taskId);
            callback(original
                ? {...item, start: original.start, end: original.end}
                : item);
            return;
        }

        const originalTask = tasks.find((t) => t.id === taskId);
        if (!originalTask) {
            callback(item);
            return;
        }

        const newStart = new Date(item.start).toISOString();
        const newEnd = new Date(item.end).toISOString();
        const oldStart = new Date(originalTask.start).toISOString();
        const oldEnd = new Date(originalTask.end).toISOString();

        // Ничего не изменилось
        if (newStart === oldStart && newEnd === oldEnd) {
            callback(item);
            return;
        }

        // Определяем resize vs move по длительности
        const oldDurationMs = new Date(oldEnd).getTime() - new Date(oldStart).getTime();
        const newDurationMs = new Date(newEnd).getTime() - new Date(newStart).getTime();
        const durationChanged = Math.abs(newDurationMs - oldDurationMs) > 60_000;
        const isResize = durationChanged;

        try {
            let response;
            if (isResize) {
                response = await rescheduleApi.resizeTask(
                    taskId,
                    newStart,
                    newEnd,
                    versionId || undefined,
                );
            } else {
                response = await rescheduleApi.moveTaskCascade(
                    taskId,
                    newStart,
                    newEnd,
                    versionId || undefined,
                );
            }

            // Итерация 13.19: успешно применили — пометить план
            markPlanDirty();

            const newDuration = Math.round(newDurationMs / 60000);
            onTaskUpdated(taskId, newStart, newEnd, newDuration);

            if (response.moved_tasks && response.moved_tasks.length > 0) {
                onCascadeMoved(response.moved_tasks);
            }

            callback(item);
        } catch (err: any) {
            const status = err.response?.status;
            const detail = err.response?.data?.detail;

            if (status === 400 || status === 409) {
                const reason = typeof detail === 'object' && detail !== null
                    ? detail.reason
                    : typeof detail === 'string'
                        ? detail
                        : 'Перемещение запрещено';
                const details = typeof detail === 'object' && detail !== null
                    ? (detail.details || [])
                    : [];
                const blockedTask = typeof detail === 'object' && detail !== null
                    ? detail.blocked_task
                    : undefined;

                onValidationError({
                    open: true,
                    reason,
                    details,
                    blockedTask,
                });
            } else {
                onError(
                    typeof detail === 'string'
                        ? detail
                        : 'Ошибка сохранения перемещения',
                );
            }

            // Возвращаем задачу на исходное место
            callback({
                ...item,
                start: originalTask.start,
                end: originalTask.end,
            });
        }
    }, [
        tasks,
        versionId,
        onTaskUpdated,
        onCascadeMoved,
        onError,
        onValidationError,
        markPlanDirty,
    ]);

    return {handleMove};
};