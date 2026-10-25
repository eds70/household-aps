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
    has_snapshot?: boolean;
    is_archived?: boolean;
    parent_version_id?: string | null;
    has_advisor_notes?: boolean;
    is_draft?: boolean;
}

export interface CurrentPlan {
    id: string;
    name: string;
    has_snapshot: boolean;
    has_advisor_notes: boolean;
    is_draft?: boolean;
    parent_version_id?: string | null;
}

interface PlanContextType {
    currentVersionId: string | null;
    currentPlanName: string;
    currentPlanHasSnapshot: boolean;
    currentPlanHasAdvisorNotes: boolean;
    isCurrentPlanDraft: boolean;

    planDirty: boolean;
    markPlanDirty: () => void;
    clearPlanDirty: () => void;

    localEditMode: boolean;
    setLocalEditMode: (value: boolean) => void;

    // НОВОЕ: Состояние расчета (для прогресс-бара)
    isCalculating: boolean;
    setIsCalculating: (value: boolean) => void;

    versions: PlanVersion[];
    setPlan: (
        versionId: string | null,
        name: string,
        hasSnapshot?: boolean,
        hasAdvisorNotes?: boolean,
        isDraft?: boolean,
        parentVersionId?: string | null,
    ) => void;
    clearPlan: () => void;
    loadVersions: () => Promise<void>;
    createPlan: (name: string, versionType: string, comment?: string) => Promise<PlanVersion>;
    deletePlan: (versionId: string) => Promise<void>;
    deleteArchivedVersions: () => Promise<number>;

    includeArchived: boolean;
    setIncludeArchived: (value: boolean) => void;

    unarchiveVersion: (versionId: string) => Promise<void>;
    archiveVersion: (versionId: string) => Promise<void>;

    startDraft: (versionId: string) => Promise<void>;
    commitDraft: (versionId: string) => Promise<void>;
    discardDraft: () => Promise<void>;
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
                        has_advisor_notes: parsed.has_advisor_notes === true,
                        is_draft: parsed.is_draft === true,
                        parent_version_id: parsed.parent_version_id || null,
                    } as CurrentPlan;
                }
            }
        } catch {}
        return null;
    });
    const [versions, setVersions] = useState<PlanVersion[]>([]);

    const [includeArchived, setIncludeArchivedState] = useState<boolean>(() => {
        try { return localStorage.getItem(STORAGE_KEY_INCLUDE_ARCHIVED) === '1'; } catch { return false; }
    });

    const [planDirty, setPlanDirty] = useState<boolean>(false);
    const [localEditMode, setLocalEditMode] = useState<boolean>(true);

    // НОВОЕ: Флаг расчета
    const [isCalculating, setIsCalculating] = useState<boolean>(false);

    const {isAuthenticated, isLoading} = useAuth();

    useEffect(() => {
        try {
            if (currentPlan) localStorage.setItem(STORAGE_KEY, JSON.stringify(currentPlan));
            else localStorage.removeItem(STORAGE_KEY);
        } catch {}
    }, [currentPlan]);

    useEffect(() => {
        try { localStorage.setItem(STORAGE_KEY_INCLUDE_ARCHIVED, includeArchived ? '1' : '0'); } catch {}
    }, [includeArchived]);

    useEffect(() => {
        if (!currentPlan?.id) return;
        try {
            const key = `aps_plan_dirty_${currentPlan.id}`;
            if (planDirty) localStorage.setItem(key, '1');
            else localStorage.removeItem(key);
        } catch {}
    }, [planDirty, currentPlan?.id]);

    useEffect(() => {
        if (!currentPlan?.id) { setPlanDirty(false); return; }
        try { setPlanDirty(localStorage.getItem(`aps_plan_dirty_${currentPlan.id}`) === '1'); } catch { setPlanDirty(false); }
    }, [currentPlan?.id]);

    useEffect(() => {
        // Если открыт черновик — включаем режим редактирования.
        // Если открыт обычный план — выключаем.
        // Если план не открыт — включаем (глобальный режим справочников).
        if (currentPlan?.id) {
            setLocalEditMode(currentPlan.is_draft === true);
        } else {
            setLocalEditMode(true);
        }
    }, [currentPlan?.id, currentPlan?.is_draft]);

    const setIncludeArchived = useCallback((value: boolean) => { setIncludeArchivedState(value); }, []);

    const loadVersions = useCallback(async () => {
        try {
            // Запрашиваем ВСЕ версии, включая черновики и архивные, чтобы текущий план не потерялся
            const response = await api.get('/api/v1/schedule/versions', {
                params: { include_archived: true, include_drafts: true }
            });
            const list: PlanVersion[] = Array.isArray(response.data) ? response.data : [];
            setVersions(list);

            setCurrentPlan((prev) => {
                if (!prev) return prev;
                const fresh = list.find((v) => v.id === prev.id);
                if (!fresh) {
                    // Если плана нет даже с черновиками — значит, его удалили
                    return null;
                }
                const freshHasSnapshot = fresh.has_snapshot !== false;
                const freshHasAdvisorNotes = fresh.has_advisor_notes === true;
                const freshIsDraft = fresh.is_draft === true;
                if (
                    fresh.name !== prev.name ||
                    freshHasSnapshot !== prev.has_snapshot ||
                    freshHasAdvisorNotes !== prev.has_advisor_notes ||
                    freshIsDraft !== prev.is_draft
                ) {
                    return {
                        id: prev.id,
                        name: fresh.name,
                        has_snapshot: freshHasSnapshot,
                        has_advisor_notes: freshHasAdvisorNotes,
                        is_draft: freshIsDraft,
                        parent_version_id: fresh.parent_version_id || prev.parent_version_id
                    };
                }
                return prev;
            });
        } catch (err: any) {
            if (err.response?.status !== 401) console.error("Ошибка загрузки версий планов:", err);
        }
    }, []);

    useEffect(() => {
        if (!isLoading && isAuthenticated) loadVersions();
    }, [isLoading, isAuthenticated, loadVersions]);

    const setPlan = useCallback((
        versionId: string | null,
        name: string,
        hasSnapshot: boolean = true,
        hasAdvisorNotes: boolean = false,
        isDraft: boolean = false,
        parentVersionId: string | null = null
    ) => {
        if (!versionId) { setCurrentPlan(null); return; }
        setCurrentPlan({
            id: versionId,
            name: name || 'План без названия',
            has_snapshot: hasSnapshot,
            has_advisor_notes: hasAdvisorNotes,
            is_draft: isDraft,
            parent_version_id: parentVersionId
        });
    }, []);

    const clearPlan = useCallback(() => { setCurrentPlan(null); }, []);
    const markPlanDirty = useCallback(() => { setPlanDirty(true); }, []);
    const clearPlanDirty = useCallback(() => { setPlanDirty(false); }, []);

    const createPlan = useCallback(async (name: string, versionType: string, comment?: string): Promise<PlanVersion> => {
        const response = await api.post('/api/v1/schedule/versions', { name, version_type: versionType, comment });
        const newVersion: PlanVersion = response.data;
        setVersions((prev) => [newVersion, ...prev]);
        setPlanDirty(false);
        return newVersion;
    }, []);

    const deletePlan = useCallback(async (versionId: string): Promise<void> => {
        await api.delete(`/api/v1/schedule/versions/${versionId}`);
        setVersions((prev) => prev.filter((v) => v.id !== versionId));
        setCurrentPlan((prev) => (prev && prev.id === versionId ? null : prev));
        try { localStorage.removeItem(`aps_plan_dirty_${versionId}`); } catch {}
    }, []);

    const deleteArchivedVersions = useCallback(async (): Promise<number> => {
        const archivedIds = versions.filter((v) => v.is_archived).map((v) => v.id);
        if (archivedIds.length === 0) return 0;
        let deletedCount = 0;
        for (const id of archivedIds) {
            try { await api.delete(`/api/v1/schedule/versions/${id}`); deletedCount++; } catch (err) { console.warn(`Не удалось удалить версию ${id}:`, err); }
        }
        setVersions((prev) => prev.filter((v) => !v.is_archived));
        return deletedCount;
    }, [versions]);

    const unarchiveVersion = useCallback(async (versionId: string): Promise<void> => {
        await api.put(`/api/v1/schedule/versions/${versionId}/unarchive`);
        await loadVersions();
    }, [loadVersions]);

    const archiveVersion = useCallback(async (versionId: string): Promise<void> => {
        await api.put(`/api/v1/schedule/versions/${versionId}/archive`);
        await loadVersions();
    }, [loadVersions]);

    // ==========================================
    // ЧЕРНОВИКИ (DRAFTS)
    // ==========================================

    const startDraft = useCallback(async (versionId: string) => {
        const response = await api.post(`/api/v1/schedule/versions/${versionId}/draft`);
        const draft = response.data;

        // Если бэкенд вернул "Существующий черновик", переименовываем его для UI
        const displayName = draft.name === 'Существующий черновик'
            ? `${currentPlan?.name || 'План'} (черновик)`
            : draft.name;

        setPlan(draft.id, displayName, true, false, true, versionId);
        setLocalEditMode(true);
        await loadVersions();
    }, [setPlan, loadVersions, currentPlan?.name]);

    const commitDraft = useCallback(async (versionId: string) => {
        await api.post(`/api/v1/schedule/versions/${versionId}/commit`);
        await loadVersions();
        setCurrentPlan((prev) => (prev && prev.id === versionId ? { ...prev, is_draft: false, name: prev.name.replace(' (черновик)', '').replace('📝 ', '') } : prev));
        setLocalEditMode(false);
    }, [loadVersions]);

    const discardDraft = useCallback(async () => {
        if (!currentPlan || !currentPlan.is_draft) return;

        const parentId = currentPlan.parent_version_id;
        const draftId = currentPlan.id;

        await api.delete(`/api/v1/schedule/versions/${draftId}`);

        if (parentId) {
            const parentVersion = versions.find(v => v.id === parentId);
            if (parentVersion) {
                setPlan(parentVersion.id, parentVersion.name, parentVersion.has_snapshot, parentVersion.has_advisor_notes, false, null);
            } else {
                clearPlan();
            }
        } else {
            clearPlan();
        }

        await loadVersions();
    }, [currentPlan, versions, setPlan, clearPlan, loadVersions]);

    const currentVersionId = currentPlan?.id ?? null;
    const currentPlanName = currentPlan?.name ?? "Режим редактирования";
    const currentPlanHasSnapshot = currentPlan?.has_snapshot ?? true;
    const currentPlanHasAdvisorNotes = currentPlan?.has_advisor_notes ?? false;
    const isCurrentPlanDraft = currentPlan?.is_draft ?? false;

    return (
        <PlanContext.Provider value={{
            currentVersionId, currentPlanName, currentPlanHasSnapshot, currentPlanHasAdvisorNotes, isCurrentPlanDraft,
            planDirty, markPlanDirty, clearPlanDirty, versions, setPlan, clearPlan, loadVersions, createPlan, deletePlan,
            deleteArchivedVersions, includeArchived, setIncludeArchived, unarchiveVersion, archiveVersion,
            localEditMode, setLocalEditMode, startDraft, commitDraft, discardDraft,
            isCalculating, setIsCalculating,
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