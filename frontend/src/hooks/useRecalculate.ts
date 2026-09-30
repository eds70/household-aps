// frontend/src/hooks/useRecalculate.ts
/**
 * Хук для пересчёта плана с Ганта (Итерация 13.17 + 13.19 + 13.21).
 *
 * Логика:
 *  1. Проверяет, что план открыт.
 *  2. Если skipSettingsCheck === false И plan_settings пуст — открывает
 *     RecalcSettingsDialog (через onNeedsSettings).
 *  3. Запускает POST /schedule/reschedule с reason='MANUAL'.
 *  4. Возвращает новую версию через onSuccess.
 *
 * Итерация 13.19:
 *  - Добавлен параметр skipSettingsCheck (по умолчанию false).
 *  - Если он true — проверка plan_settings пропускается, идёт
 *    прямой вызов reschedule. Используется кнопкой
 *    «Пересчитать без изменений» в RecalcSettingsDialog.
 *
 * Итерация 13.21:
 *  - Передаём replace_version_id = versionId. Бэкенд архивирует
 *    старую версию (если она не используется в what-if).
 *  - onSuccess получает второй аргумент Response с полями
 *    replace_archived / replace_blocked / replace_blocked_reason
 *    / used_by_whatif.
 *  - В UI это позволяет показать Alert «старая версия не архивирована».
 */
import {useCallback, useState} from 'react';
import {planSettingsApi, rescheduleApi, settingsApi} from '../services/api';
import type {RescheduleResponse} from '../types';

export interface UseRecalculateOptions {
    versionId: string | null;
    /**
     * Итерация 13.21: колбэк onSuccess теперь получает второй аргумент —
     * полный RescheduleResponse. Это позволяет вызывающему коду
     * показать Alert о replace_blocked.
     */
    onSuccess: (
        newVersionId: string,
        response: RescheduleResponse,
    ) => void;
    onNeedsSettings: () => void;
    onError: (message: string) => void;
}

export interface RecalculateResult {
    recalculating: boolean;
    recalculate: (skipSettingsCheck?: boolean) => Promise<void>;
}

export const useRecalculate = (
    options: UseRecalculateOptions,
): RecalculateResult => {
    const {versionId, onSuccess, onNeedsSettings, onError} = options;
    const [recalculating, setRecalculating] = useState(false);

    const recalculate = useCallback(async (skipSettingsCheck: boolean = false) => {
        if (!versionId) {
            onError('План не открыт. Откройте план из истории.');
            return;
        }

        // 1. Проверяем наличие plan_settings (можно пропустить)
        if (!skipSettingsCheck) {
            try {
                const planData = await planSettingsApi.getForVersion(versionId);
                const settingsCount = Object.keys(planData.settings || {}).length;
                if (settingsCount === 0) {
                    onNeedsSettings();
                    return;
                }
            } catch (err: any) {
                // Если plan_settings недоступны — открываем мастер
                onNeedsSettings();
                return;
            }
        }

        // 2. Проверяем настройку auto_archive_on_recalc
        //    (Итерация 13.21: по умолчанию архивируем старую версию).
        let autoArchive = true;
        try {
            const planningSettings = await settingsApi.getCategory('planning');
            if (typeof planningSettings.auto_archive_on_recalc === 'boolean') {
                autoArchive = planningSettings.auto_archive_on_recalc;
            }
        } catch {
            // Если не удалось прочитать — используем default = true
            autoArchive = true;
        }

        // 3. Запускаем пересчёт
        setRecalculating(true);
        try {
            const response = await rescheduleApi.reschedule({
                from_version_id: versionId,
                reason: 'MANUAL',
                changes: {},
                frozen_before: null,
                comment: 'Пересчёт после ручных правок на Ганте',
                // Итерация 13.21: заменяем старую версию, если настройка включена
                replace_version_id: autoArchive ? versionId : null,
            });

            if (!response.to_version_id) {
                onError(response.message || 'Не удалось создать новую версию');
                return;
            }

            // Итерация 13.21: передаём полный Response вторым аргументом
            onSuccess(response.to_version_id, response);
        } catch (err: any) {
            const detail = err.response?.data?.detail;
            onError(
                typeof detail === 'string'
                    ? detail
                    : (detail?.reason || 'Ошибка пересчёта плана'),
            );
        } finally {
            setRecalculating(false);
        }
    }, [versionId, onSuccess, onNeedsSettings, onError]);

    return {recalculating, recalculate};
};