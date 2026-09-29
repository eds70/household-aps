// frontend/src/hooks/useGanttFilters.ts
/**
 * Хук для фильтрации задач на Ганте (Итерация 13.17 + 13.18).
 *
 * Вынесено из GanttPage.tsx (renderTimeline).
 *
 * Логика:
 *  - Принимает все задачи + текущие фильтры.
 *  - Возвращает отфильтрованный список задач.
 *  - Возвращает количество отфильтрованных задач.
 *
 * Фильтры:
 *  - searchQuery         — поиск по operation_name / batch_id / product_id
 *  - equipmentFilter     — фильтр по equipment_id (мультивыбор)
 *  - productFilter       — фильтр по product_id (мультивыбор)
 *  - batchFilter         — фильтр по конкретной batch_id
 *  - showOnlyBlocked     — только is_lab_blocked === true
 *  - showOnlySlowCooling — только cooling_mode === 'slow'
 *  - showOnlyCzIncomplete — только LINE_FILL с cz_status !== 'COMPLETED'
 *  - showOnlyPinned      — только is_pinned === true (Итерация 13.18)
 *
 * ВАЖНО:
 *  - Всегда фильтрует только "настоящие" task (item_type === 'task' | undefined).
 *  - setup и downtime сюда не попадают (они генерируются позже).
 */
import {useMemo} from 'react';
import type {TaskData} from '../types';

export interface GanttFilters {
    searchQuery: string;
    equipmentFilter: string[];
    productFilter: string[];
    batchFilter: string | null;
    showOnlyBlocked: boolean;
    showOnlySlowCooling: boolean;
    showOnlyCzIncomplete: boolean;
    /** Итерация 13.18: показывать только закреплённые задачи. */
    showOnlyPinned: boolean;
}

export interface UseGanttFiltersResult {
    /** Отфильтрованные задачи (только "настоящие" task, без setup/downtime). */
    filteredTasks: TaskData[];
    /** Количество отфильтрованных задач. */
    filteredCount: number;
    /** Всего задач в исходном наборе (только "настоящие" task). */
    totalTasks: number;
    /** Активны ли хотя бы одни фильтры. */
    hasActiveFilters: boolean;
}

/**
 * Фильтрует задачи по всем фильтрам Ганта.
 *
 * @param allTasks — все задачи (включая setup, downtime — они отсеиваются).
 * @param filters  — объект с активными фильтрами.
 */
export const useGanttFilters = (
    allTasks: TaskData[],
    filters: GanttFilters,
): UseGanttFiltersResult => {
    return useMemo(() => {
        // 1. Оставляем только "настоящие" задачи
        let result = allTasks.filter(
            (task) => task.item_type === 'task' || !task.item_type,
        );
        const totalTasks = result.length;

        const {
            searchQuery,
            equipmentFilter,
            productFilter,
            batchFilter,
            showOnlyBlocked,
            showOnlySlowCooling,
            showOnlyCzIncomplete,
            showOnlyPinned,
        } = filters;

        // 2. Фильтр по лабораторной блокировке
        if (showOnlyBlocked) {
            result = result.filter((task) => task.is_lab_blocked === true);
        }

        // 3. Фильтр по замедленному охлаждению
        if (showOnlySlowCooling) {
            result = result.filter((task) => task.cooling_mode === 'slow');
        }

        // 4. Фильтр по незавершённому ЧЗ
        if (showOnlyCzIncomplete) {
            result = result.filter(
                (task) =>
                    task.task_role === 'LINE_FILL' &&
                    !!task.cz_status &&
                    task.cz_status !== 'COMPLETED',
            );
        }

        // 5. Итерация 13.18: фильтр по закреплённым
        if (showOnlyPinned) {
            result = result.filter((task) => task.is_pinned === true);
        }

        // 6. Поиск по подстроке
        if (searchQuery) {
            const query = searchQuery.toLowerCase();
            result = result.filter(
                (task) =>
                    task.operation_name.toLowerCase().includes(query) ||
                    task.batch_id.toLowerCase().includes(query) ||
                    task.product_id.toLowerCase().includes(query),
            );
        }

        // 7. Фильтр по оборудованию (мультивыбор)
        if (equipmentFilter.length > 0) {
            result = result.filter((task) =>
                equipmentFilter.includes(task.equipment_id),
            );
        }

        // 8. Фильтр по продуктам (мультивыбор)
        if (productFilter.length > 0) {
            result = result.filter((task) =>
                productFilter.includes(task.product_id),
            );
        }

        // 9. Фильтр по конкретной партии
        if (batchFilter) {
            result = result.filter((task) => task.batch_id === batchFilter);
        }

        const hasActiveFilters =
            searchQuery.length > 0 ||
            equipmentFilter.length > 0 ||
            productFilter.length > 0 ||
            batchFilter !== null ||
            showOnlyBlocked ||
            showOnlySlowCooling ||
            showOnlyCzIncomplete ||
            showOnlyPinned;

        return {
            filteredTasks: result,
            filteredCount: result.length,
            totalTasks,
            hasActiveFilters,
        };
    }, [
        allTasks,
        filters.searchQuery,
        filters.equipmentFilter,
        filters.productFilter,
        filters.batchFilter,
        filters.showOnlyBlocked,
        filters.showOnlySlowCooling,
        filters.showOnlyCzIncomplete,
        filters.showOnlyPinned,
    ]);
};