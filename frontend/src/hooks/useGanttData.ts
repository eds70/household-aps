// frontend/src/hooks/useGanttData.ts
/**
 * Хук для загрузки данных Ганта (Итерация 13.17).
 *
 * Вынесено из GanttPage.tsx.
 *
 * Логика:
 *  - При смене versionId — загружает данные.
 *  - Считает статистику (blocked, cooling_slow, cz_incomplete).
 *  - Возвращает: loading, error, stats, tasks, equipmentList, productList.
 *  - Метод refresh() — принудительная перезагрузка.
 */
import {useCallback, useEffect, useState} from 'react';
import {ganttApi} from '../services/api';
import type {TaskData} from '../types';

export interface GanttStats {
    totalTasks: number;
    makespanHours: number;
    equipmentCount: number;
    blockedCount: number;
    coolingSlowCount: number;
    czIncompleteCount: number;
}

export interface UseGanttDataResult {
    loading: boolean;
    error: string | null;
    setError: (err: string | null) => void;
    stats: GanttStats;
    tasks: TaskData[];
    setTasks: React.Dispatch<React.SetStateAction<TaskData[]>>;
    equipmentList: string[];
    productList: string[];
    refresh: () => Promise<void>;
}

const INITIAL_STATS: GanttStats = {
    totalTasks: 0,
    makespanHours: 0,
    equipmentCount: 0,
    blockedCount: 0,
    coolingSlowCount: 0,
    czIncompleteCount: 0,
};

export const useGanttData = (
    versionId: string | null,
): UseGanttDataResult => {
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [stats, setStats] = useState<GanttStats>(INITIAL_STATS);
    const [tasks, setTasks] = useState<TaskData[]>([]);
    const [equipmentList, setEquipmentList] = useState<string[]>([]);
    const [productList, setProductList] = useState<string[]>([]);

    const loadGanttData = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const data = await ganttApi.getData(versionId || undefined);
            const typedTasks = data.tasks as TaskData[];

            const blockedCount = typedTasks.filter(
                (t) => t.is_lab_blocked === true,
            ).length;
            const coolingSlowCount = typedTasks.filter(
                (t) => t.cooling_mode === 'slow',
            ).length;
            const czIncompleteCount = typedTasks.filter(
                (t) =>
                    t.task_role === 'LINE_FILL' &&
                    t.cz_status &&
                    t.cz_status !== 'COMPLETED',
            ).length;

            setStats({
                totalTasks: data.total_tasks,
                makespanHours: data.makespan_hours,
                equipmentCount: data.equipment_list.length,
                blockedCount,
                coolingSlowCount,
                czIncompleteCount,
            });
            setTasks(typedTasks);
            setEquipmentList(data.equipment_list);
            setProductList(data.product_list);
        } catch (err: any) {
            setError(
                err.response?.data?.detail || 'Ошибка загрузки данных Ганта',
            );
        } finally {
            setLoading(false);
        }
    }, [versionId]);

    useEffect(() => {
        void loadGanttData();
    }, [loadGanttData]);

    return {
        loading,
        error,
        setError,
        stats,
        tasks,
        setTasks,
        equipmentList,
        productList,
        refresh: loadGanttData,
    };
};