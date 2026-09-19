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

interface PlanContextType {
    currentVersionId: string | null;
    currentPlanName: string;
    versions: PlanVersion[];
    setPlan: (versionId: string | null, name: string) => void;
    loadVersions: () => Promise<void>;
    createPlan: (name: string, versionType: string, comment?: string) => Promise<PlanVersion>;
    deletePlan: (versionId: string) => Promise<void>;
}

export const PlanContext = createContext<PlanContextType | undefined>(undefined);

export const PlanProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [currentVersionId, setCurrentVersionId] = useState<string | null>(null);
    const [currentPlanName, setCurrentPlanName] = useState<string>("Режим редактирования");
    const [versions, setVersions] = useState<PlanVersion[]>([]);

    // ✅ Итерация 11 (fix): используем useAuth, чтобы не грузить версии
    // до аутентификации пользователя.
    const {isAuthenticated, isLoading} = useAuth();

    // ✅ Итерация 11 (fix): useCallback для стабильной ссылки.
    const loadVersions = useCallback(async () => {
        try {
            const response = await axios.get(`${API_BASE_URL}/api/v1/schedule/versions`);
            setVersions(Array.isArray(response.data) ? response.data : []);
        } catch (err: any) {
            if (err.response?.status !== 401) {
                console.error("Ошибка загрузки версий планов:", err);
            }
        }
    }, []);

    // ✅ Итерация 11 (fix): загружаем версии ТОЛЬКО когда пользователь
    // аутентифицирован и загрузка auth завершена.
    useEffect(() => {
        if (!isLoading && isAuthenticated) {
            loadVersions();
        }
    }, [isLoading, isAuthenticated, loadVersions]);

    // ✅ useCallback для setPlan.
    const setPlan = useCallback((versionId: string | null, name: string) => {
        setCurrentVersionId(versionId);
        setCurrentPlanName(name || "Режим редактирования");
    }, []);

    // ✅ useCallback для createPlan.
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

    // ✅ useCallback для deletePlan.
    const deletePlan = useCallback(async (versionId: string): Promise<void> => {
        await axios.delete(`${API_BASE_URL}/api/v1/schedule/versions/${versionId}`);
        setVersions((prev) => prev.filter((v) => v.id !== versionId));

        setCurrentVersionId((prevId) => {
            if (prevId === versionId) {
                setCurrentPlanName("Режим редактирования");
                return null;
            }
            return prevId;
        });
    }, []);

    return (
        <PlanContext.Provider value={{
            currentVersionId,
            currentPlanName,
            versions,
            setPlan,
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