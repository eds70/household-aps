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
     *
     * UI использует это, чтобы понять, можно ли открывать план
     * в readonly-режиме. Если false — вместо readonly показываем
     * предупреждение «план пуст, требуется пересчёт».
     */
    has_snapshot?: boolean;
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
     * true  — план полноценный, справочники читаются из снапшотов.
     * false — план пуст (снапшотов нет), справочники будут пустыми.
     */
    currentPlanHasSnapshot: boolean;
    versions: PlanVersion[];
    setPlan: (versionId: string | null, name: string, hasSnapshot?: boolean) => void;
    clearPlan: () => void;
    loadVersions: () => Promise<void>;
    createPlan: (name: string, versionType: string, comment?: string) => Promise<PlanVersion>;
    deletePlan: (versionId: string) => Promise<void>;
}

export const PlanContext = createContext<PlanContextType | undefined>(undefined);

const STORAGE_KEY = 'aps_current_plan';

export const PlanProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    // Итерация 13.13: храним id и name в одном объекте,
    // чтобы они не могли рассинхронизироваться.
    // Также сохраняем в localStorage — чтобы план не сбрасывался при F5.
    //
    // Итерация 13.15: добавлен has_snapshot — чтобы UI знал, можно ли
    // читать справочники из снапшотов или план пуст.
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

    const loadVersions = useCallback(async () => {
        try {
            const response = await axios.get(`${API_BASE_URL}/api/v1/schedule/versions`);
            const list: PlanVersion[] = Array.isArray(response.data) ? response.data : [];
            setVersions(list);

            // Синхронизация: если сохранённый план больше не существует в БД — сбрасываем его.
            setCurrentPlan((prev) => {
                if (!prev) return prev;
                const stillExists = list.some((v) => v.id === prev.id);
                if (!stillExists) {
                    return null;
                }
                // Обновляем имя и has_snapshot, если они изменились
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
    }, []);

    const currentVersionId = currentPlan?.id ?? null;
    const currentPlanName = currentPlan?.name ?? "Режим редактирования";
    const currentPlanHasSnapshot = currentPlan?.has_snapshot ?? true;

    return (
        <PlanContext.Provider value={{
            currentVersionId,
            currentPlanName,
            currentPlanHasSnapshot,
            versions,
            setPlan,
            clearPlan,
            loadVersions,
            createPlan,
            deletePlan,
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