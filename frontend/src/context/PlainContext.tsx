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
}

// Текущий план: либо конкретный план, либо null (режим редактирования)
export interface CurrentPlan {
    id: string;
    name: string;
}

interface PlanContextType {
    currentVersionId: string | null;
    currentPlanName: string;
    versions: PlanVersion[];
    setPlan: (versionId: string | null, name: string) => void;
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
    const [currentPlan, setCurrentPlan] = useState<CurrentPlan | null>(() => {
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            if (raw) {
                const parsed = JSON.parse(raw);
                if (parsed && parsed.id && parsed.name) {
                    return parsed as CurrentPlan;
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
                // Обновляем имя, если оно изменилось (например, после перепланирования)
                const fresh = list.find((v) => v.id === prev.id);
                if (fresh && fresh.name !== prev.name) {
                    return {id: prev.id, name: fresh.name};
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

    const setPlan = useCallback((versionId: string | null, name: string) => {
        if (!versionId) {
            setCurrentPlan(null);
            return;
        }
        setCurrentPlan({id: versionId, name: name || 'План без названия'});
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

    return (
        <PlanContext.Provider value={{
            currentVersionId,
            currentPlanName,
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