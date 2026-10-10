// frontend/src/context/PlainContext.tsx
import React, {createContext, useCallback, useContext, useEffect, useState} from 'react';
import api from '../services/api';
import {useAuth} from './AuthContext';

export interface PlanVersion {
    id: string;
    name: string;
    version_type: string;
    is_active: boolean;
    created_at: string;
    comment?: string | null;
    /**
     * Итерация 13.15: заполнены ли снапшот-таблицы для этой версии.
     */
    has_snapshot?: boolean;
    /**
     * Итерация 13.21: архивная версия.
     */
    is_archived?: boolean;
    /**
     * Итерация 13.21: ID родительской версии.
     */
    parent_version_id?: string | null;
}

export interface CurrentPlan {
    id: string;
    name: string;
    has_snapshot: boolean;
}

interface PlanContextType {
    currentVersionId: string | null;
    currentPlanName: string;
    /**
     * Итерация 13.15: есть ли снапшоты у текущего плана.
     */
    currentPlanHasSnapshot: boolean;

    /**
     * Итерация 13.19: флаг «план содержит несохранённые изменения».
     */
    planDirty: boolean;
    markPlanDirty: () => void;
    clearPlanDirty: () => void;

    /**
     * Итерация 14.2: локальный режим редактирования для Ганта.
     * Если true — задачи можно таскать/ресайзить.
     * Используется в GanttPage и MainLayout (для иконки в шапке).
     */
    localEditMode: boolean;
    setLocalEditMode: (value: boolean) => void;

    versions: PlanVersion[];
    setPlan: (versionId: string | null, name: string, hasSnapshot?: boolean) => void;
    clearPlan: () => void;
    loadVersions: () => Promise<void>;
    createPlan: (name: string, versionType: string, comment?: string) => Promise<PlanVersion>;
    deletePlan: (versionId: string) => Promise<void>;

    /**
     * Итерация 13.21: показывать ли архивные версии в списке.
     */
    includeArchived: boolean;
    setIncludeArchived: (value: boolean) => void;

    /**
     * Итерация 13.21: разархивировать версию плана.
     */
    unarchiveVersion: (versionId: string) => Promise<void>;
}

export const PlanContext = createContext<PlanContextType | undefined>(undefined);

const STORAGE_KEY = 'aps_current_plan';
const STORAGE_KEY_INCLUDE_ARCHIVED = 'aps_include_archived';

export const PlanProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [currentPlan, setCurrentPlan] = useState<CurrentPlan | null>(() => {
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            if (raw) {
                const parsed = JSON.parse(raw);
                if (parsed && parsed.id && parsed.name) {
                    return {
                        id: parsed.id,
                        name: parsed.name,
                        has_snapshot: parsed.has_snapshot !== false,
                    } as CurrentPlan;
                }
            }
        } catch {
            // ignore
        }
        return null;
    });
    const [versions, setVersions] = useState<PlanVersion[]>([]);

    /**
     * Итерация 13.21: показывать ли архивные версии.
     */
    const [includeArchived, setIncludeArchivedState] = useState<boolean>(() => {
        try {
            return localStorage.getItem(STORAGE_KEY_INCLUDE_ARCHIVED) === '1';
        } catch {
            return false;
        }
    });

    /**
     * Итерация 13.19: флаг «план содержит несохранённые изменения».
     */
    const [planDirty, setPlanDirty] = useState<boolean>(false);

    /**
     * Итерация 14.2: глобальный режим редактирования для Ганта.
     * По умолчанию — true (когда план не открыт).
     * Синхронизируется с currentVersionId: при открытии плана
     * сбрасывается в false (readonly).
     */
    const [localEditMode, setLocalEditMode] = useState<boolean>(true);

    const {isAuthenticated, isLoading} = useAuth();

    // Сохраняем currentPlan в localStorage при каждом изменении
    useEffect(() => {
        try {
            if (currentPlan) {
                localStorage.setItem(STORAGE_KEY, JSON.stringify(currentPlan));
            } else {
                localStorage.removeItem(STORAGE_KEY);
            }
        } catch {
            // ignore
        }
    }, [currentPlan]);

    // Итерация 13.21: сохраняем includeArchived в localStorage
    useEffect(() => {
        try {
            localStorage.setItem(
                STORAGE_KEY_INCLUDE_ARCHIVED,
                includeArchived ? '1' : '0',
            );
        } catch {
            // ignore
        }
    }, [includeArchived]);

    /**
     * Итерация 13.19: сохраняем planDirty в localStorage per-plan.
     */
    useEffect(() => {
        if (!currentPlan?.id) return;
        try {
            const key = `aps_plan_dirty_${currentPlan.id}`;
            if (planDirty) {
                localStorage.setItem(key, '1');
            } else {
                localStorage.removeItem(key);
            }
        } catch {
            // ignore
        }
    }, [planDirty, currentPlan?.id]);

    /**
     * Итерация 13.19: восстанавливаем planDirty при смене плана.
     */
    useEffect(() => {
        if (!currentPlan?.id) {
            setPlanDirty(false);
            return;
        }
        try {
            const key = `aps_plan_dirty_${currentPlan.id}`;
            setPlanDirty(localStorage.getItem(key) === '1');
        } catch {
            setPlanDirty(false);
        }
    }, [currentPlan?.id]);

    /**
     * Итерация 14.2: при открытии плана → readonly по умолчанию.
     * При закрытии → редактирование.
     */
    useEffect(() => {
        if (currentPlan?.id) {
            setLocalEditMode(false);
        } else {
            setLocalEditMode(true);
        }
    }, [currentPlan?.id]);

    /**
     * Итерация 13.21: сеттер для includeArchived.
     */
    const setIncludeArchived = useCallback((value: boolean) => {
        setIncludeArchivedState(value);
    }, []);

    const loadVersions = useCallback(async () => {
        try {
            // Итерация 13.21: всегда получаем ВСЕ версии.
            // Итерация 17.x: используем общий api-клиент вместо голого axios,
            // чтобы интерцептор нормализовал detail в строку при 403/500.
            const response = await api.get(
                '/api/v1/schedule/versions',
                { params: { include_archived: true } },
            );
            const list: PlanVersion[] = Array.isArray(response.data) ? response.data : [];
            setVersions(list);

            setCurrentPlan((prev) => {
                if (!prev) return prev;
                const stillExists = list.some((v) => v.id === prev.id);
                if (!stillExists) {
                    return null;
                }
                const fresh = list.find((v) => v.id === prev.id);
                if (fresh) {
                    const freshHasSnapshot = fresh.has_snapshot !== false;
                    if (
                        fresh.name !== prev.name ||
                        freshHasSnapshot !== prev.has_snapshot
                    ) {
                        return {
                            id: prev.id,
                            name: fresh.name,
                            has_snapshot: freshHasSnapshot,
                        };
                    }
                }
                return prev;
            });
        } catch (err: any) {
            if (err.response?.status !== 401) {
                console.error("Ошибка загрузки версий планов:", err);
            }
        }
    }, []);

    useEffect(() => {
        if (!isLoading && isAuthenticated) {
            loadVersions();
        }
    }, [isLoading, isAuthenticated, loadVersions]);

    const setPlan = useCallback((
        versionId: string | null,
        name: string,
        hasSnapshot: boolean = true,
    ) => {
        if (!versionId) {
            setCurrentPlan(null);
            return;
        }
        setCurrentPlan({
            id: versionId,
            name: name || 'План без названия',
            has_snapshot: hasSnapshot,
        });
    }, []);

    const clearPlan = useCallback(() => {
        setCurrentPlan(null);
    }, []);

    const markPlanDirty = useCallback(() => {
        setPlanDirty(true);
    }, []);

    const clearPlanDirty = useCallback(() => {
        setPlanDirty(false);
    }, []);

    const createPlan = useCallback(async (
        name: string,
        versionType: string,
        comment?: string,
    ): Promise<PlanVersion> => {
        const response = await api.post('/api/v1/schedule/versions', {
            name,
            version_type: versionType,
            comment,
        });
        const newVersion: PlanVersion = response.data;
        setVersions((prev) => [newVersion, ...prev]);
        setPlanDirty(false);
        return newVersion;
    }, []);

    const deletePlan = useCallback(async (versionId: string): Promise<void> => {
        await api.delete(`/api/v1/schedule/versions/${versionId}`);
        setVersions((prev) => prev.filter((v) => v.id !== versionId));

        setCurrentPlan((prev) => {
            if (prev && prev.id === versionId) {
                return null;
            }
            return prev;
        });
        try {
            localStorage.removeItem(`aps_plan_dirty_${versionId}`);
        } catch {
            // ignore
        }
    }, []);

    /**
     * Итерация 13.21: разархивация версии.
     */
    const unarchiveVersion = useCallback(async (versionId: string): Promise<void> => {
        await api.put(
            `/api/v1/schedule/versions/${versionId}/unarchive`,
        );
        await loadVersions();
    }, [loadVersions]);

    const currentVersionId = currentPlan?.id ?? null;
    const currentPlanName = currentPlan?.name ?? "Режим редактирования";
    const currentPlanHasSnapshot = currentPlan?.has_snapshot ?? true;

    return (
        <PlanContext.Provider value={{
            currentVersionId,
            currentPlanName,
            currentPlanHasSnapshot,
            planDirty,
            markPlanDirty,
            clearPlanDirty,
            versions,
            setPlan,
            clearPlan,
            loadVersions,
            createPlan,
            deletePlan,
            // Итерация 13.21
            includeArchived,
            setIncludeArchived,
            unarchiveVersion,
            // ==========================================
            // Итерация 14.2: глобальный режим редактирования
            // ==========================================
            localEditMode,
            setLocalEditMode,
        }}>
            {children}
        </PlanContext.Provider>
    );
};

export const usePlan = () => {
    const context = useContext(PlanContext);
    if (!context) throw new Error("usePlan must be used within PlanProvider");
    return context;
};