// src/context/PlainContext.tsx
import React, { createContext, useState, useEffect, useContext } from 'react';
import axios from 'axios';
import { API_BASE_URL } from '../config';

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

    const loadVersions = async () => {
        try {
            const response = await axios.get(`${API_BASE_URL}/api/v1/schedule/versions`);
            setVersions(response.data);
            // ✅ НЕ устанавливаем currentVersionId автоматически
            // Справочники должны показывать актуальные данные из основных таблиц
        } catch (err) {
            console.error("Ошибка загрузки версий планов:", err);
        }
    };

    useEffect(() => {
        loadVersions();
    }, []);

    const setPlan = (versionId: string | null, name: string) => {
        setCurrentVersionId(versionId);
        setCurrentPlanName(name || "Режим редактирования");
    };

    const createPlan = async (name: string, versionType: string, comment?: string): Promise<PlanVersion> => {
        const response = await axios.post(`${API_BASE_URL}/api/v1/schedule/versions`, {
            name,
            version_type: versionType,
            comment,
        });
        const newVersion: PlanVersion = response.data;
        setVersions((prev) => [newVersion, ...prev]);
        return newVersion;
    };

    const deletePlan = async (versionId: string): Promise<void> => {
        await axios.delete(`${API_BASE_URL}/api/v1/schedule/versions/${versionId}`);
        setVersions((prev) => prev.filter((v) => v.id !== versionId));
        // Если удалили текущий выбранный план — сбрасываем в режим редактирования
        if (currentVersionId === versionId) {
            setCurrentVersionId(null);
            setCurrentPlanName("Режим редактирования");
        }
    };

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