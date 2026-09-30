// frontend/src/context/PlainContext.tsx
import React, {createContext, useCallback, useContext, useEffect, useState} from 'react';
import axios from 'axios';
import {API_BASE_URL} from '../config';
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
     *
     * true  — план рассчитан или создан через snapshot_all_catalogs.
     * false — «пустой» план (создан до Итерации 13.15, снапшотов нет).
     */
    has_snapshot?: boolean;
    /**
     * Итерация 13.21: архивная версия.
     * Архивные версии скрыты из списка по умолчанию.
     */
    is_archived?: boolean;
    /**
     * Итерация 13.21: ID родительской версии.
     * Используется для построения иерархии в «Истории планов».
     */
    parent_version_id?: string | null;
}

// Текущий план: либо конкретный план, либо null (режим редактирования)
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
     * Итерация 13.19: флаг «план содержит несохранённые изменения,
     * влияющие на расчёт».
     *
     * Устанавливается через markPlanDirty() при:
     *   - изменении справочников (продукты, оборудование, операции,
     *     рецепты, материалы);
     *   - изменении заказов и партий;
     *   - изменении capacity пулов;
     *   - лабораторной блокировке / разблокировке;
     *   - изменении calendar_event;
     *   - изменении app_settings / plan_settings;
     *   - перемещении / изменении длительности задачи на Ганте
     *     (move-cascade / resize);
     *   - pin / unpin задачи.
     *
     * Сбрасывается через clearPlanDirty() при:
     *   - успешном пересчёте (recalculate);
     *   - смене активного плана;
     *   - создании нового плана.
     */
    planDirty: boolean;
    markPlanDirty: () => void;
    clearPlanDirty: () => void;

    versions: PlanVersion[];
    setPlan: (versionId: string | null, name: string, hasSnapshot?: boolean) => void;
    clearPlan: () => void;
    loadVersions: () => Promise<void>;
    createPlan: (name: string, versionType: string, comment?: string) => Promise<PlanVersion>;
    deletePlan: (versionId: string) => Promise<void>;

    /**
     * Итерация 13.21: показывать ли архивные версии в списке.
     * Сохраняется в localStorage, чтобы не сбрасываться при F5.
     */
    includeArchived: boolean;
    setIncludeArchived: (value: boolean) => void;

    /**
     * Итерация 13.21: разархивировать версию плана.
     * После успеха обновляет список versions.
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
     * По умолчанию — false (список чистый).
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
     * Хранится в localStorage по ключу плана, чтобы не терялся при F5.
     */
    const [planDirty, setPlanDirty] = useState<boolean>(false);

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
     * Итерация 13.19: сохраняем planDirty в localStorage per-plan,
     * чтобы флаг не терялся при F5.
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
     * Итерация 13.21: сеттер для includeArchived с автоматической
     * перезагрузкой списка версий.
     */
    const setIncludeArchived = useCallback((value: boolean) => {
        setIncludeArchivedState(value);
    }, []);

    const loadVersions = useCallback(async () => {
        try {
            // Итерация 13.21 (Вариант B): всегда получаем ВСЕ версии
            // (включая архивные). Фильтрация — на фронте, в SchedulePage.
            const response = await axios.get(
                `${API_BASE_URL}/api/v1/schedule/versions`,
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
        const response = await axios.post(`${API_BASE_URL}/api/v1/schedule/versions`, {
            name,
            version_type: versionType,
            comment,
        });
        const newVersion: PlanVersion = response.data;
        setVersions((prev) => [newVersion, ...prev]);
        // Новый план создан со снапшотами и настройками — «чистый».
        setPlanDirty(false);
        return newVersion;
    }, []);

    const deletePlan = useCallback(async (versionId: string): Promise<void> => {
        await axios.delete(`${API_BASE_URL}/api/v1/schedule/versions/${versionId}`);
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
        await axios.put(
            `${API_BASE_URL}/api/v1/schedule/versions/${versionId}/unarchive`,
        );
        // Перезагружаем список — разархивированная появится,
        // если includeArchived = false (или останется, если true).
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