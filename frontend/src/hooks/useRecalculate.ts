// frontend/src/hooks/useRecalculate.ts
/**
 * Хук для пересчёта плана с Ганта (Итерация 13.17).
 *
 * Логика:
 *  1. Проверяет, что план открыт и есть plan_settings.
 *  2. Если plan_settings пуст — возвращает needsSettings: true,
 *     родитель должен открыть PlanSettingsWizard.
 *  3. Если всё ок — запускает POST /schedule/reschedule с
 *     reason='MANUAL' и возвращает новую версию.
 *  4. Сбрасывает флаг hasUnsavedChanges.
 */
import {useCallback, useState} from 'react';
import {planSettingsApi, rescheduleApi} from '../services/api';

export interface UseRecalculateOptions {
    versionId: string | null;
    onSuccess: (newVersionId: string) => void;
    onNeedsSettings: () => void;
    onError: (message: string) => void;
}

export interface RecalculateResult {
    recalculating: boolean;
    recalculate: () => Promise<void>;
}

export const useRecalculate = (
    options: UseRecalculateOptions,
): RecalculateResult => {
    const {versionId, onSuccess, onNeedsSettings, onError} = options;
    const [recalculating, setRecalculating] = useState(false);

    const recalculate = useCallback(async () => {
        if (!versionId) {
            onError('План не открыт. Откройте план из истории.');
            return;
        }

        // 1. Проверяем наличие plan_settings
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

        // 2. Запускаем пересчёт
        setRecalculating(true);
        try {
            const response = await rescheduleApi.reschedule({
                from_version_id: versionId,
                reason: 'MANUAL',
                changes: {},
                frozen_before: null,
                comment: 'Пересчёт после ручных правок на Ганте',
            });

            if (!response.to_version_id) {
                onError(response.message || 'Не удалось создать новую версию');
                return;
            }

            onSuccess(response.to_version_id);
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