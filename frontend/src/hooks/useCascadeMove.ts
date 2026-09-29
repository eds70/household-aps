// frontend/src/hooks/useCascadeMove.ts
/**
 * Хук для каскадного сдвига задач через API (Итерация 13.17).
 *
 * Используется для:
 *  - сдвига задачи на ±1 час из контекстного меню;
 *  - pin/unpin задачи.
 */
import {useCallback} from 'react';
import {rescheduleApi} from '../services/api';
import type {TaskData, ValidationErrorState} from '../types';

export interface UseCascadeMoveOptions {
    versionId: string | null;
    onTaskUpdated: (taskId: string, newStart: string, newEnd: string) => void;
    onCascadeMoved: (movedTasks: Array<{task_id: string; new_start: string; new_end: string}>) => void;
    onError: (message: string) => void;
    onValidationError: (state: ValidationErrorState) => void;
    onSuccess?: (message: string) => void;
}

export const useCascadeMove = (options: UseCascadeMoveOptions) => {
    const {
        versionId,
        onTaskUpdated,
        onCascadeMoved,
        onError,
        onValidationError,
        onSuccess,
    } = options;

    /**
     * Сдвигает задачу на deltaMinutes (может быть отрицательным).
     */
    const shiftTask = useCallback(async (
        task: TaskData,
        deltaMinutes: number,
    ) => {
        const oldStart = new Date(task.start);
        const oldEnd = new Date(task.end);

        const newStart = new Date(oldStart.getTime() + deltaMinutes * 60000);
        const newEnd = new Date(oldEnd.getTime() + deltaMinutes * 60000);

        try {
            const response = await rescheduleApi.moveTaskCascade(
                task.id,
                newStart.toISOString(),
                newEnd.toISOString(),
                versionId || undefined,
            );

            onTaskUpdated(
                task.id,
                newStart.toISOString(),
                newEnd.toISOString(),
            );

            if (response.moved_tasks && response.moved_tasks.length > 0) {
                onCascadeMoved(response.moved_tasks);
            }

            if (onSuccess) {
                onSuccess(
                    `Задача сдвинута на ${deltaMinutes > 0 ? '+' : ''}${deltaMinutes} мин. ` +
                    `Сдвинуто: ${response.moved_tasks?.length ?? 0}`,
                );
            }
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
                        : 'Ошибка сдвига задачи',
                );
            }
        }
    }, [versionId, onTaskUpdated, onCascadeMoved, onError, onValidationError, onSuccess]);

    /**
     * Закрепляет или открепляет задачу.
     */
    const togglePin = useCallback(async (
        task: TaskData,
        isPinned: boolean,
    ) => {
        try {
            await rescheduleApi.pinTask(
                task.id,
                isPinned,
                versionId || undefined,
            );
            if (onSuccess) {
                onSuccess(isPinned ? 'Задача закреплена' : 'Задача откреплена');
            }
        } catch (err: any) {
            const detail = err.response?.data?.detail;
            onError(
                typeof detail === 'string'
                    ? detail
                    : 'Ошибка закрепления',
            );
        }
    }, [versionId, onError, onSuccess]);

    return {shiftTask, togglePin};
};