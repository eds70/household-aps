// frontend/src/pages/SchedulePage.tsx
import React, {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {useNavigate} from 'react-router-dom';
import {type PlanVersion, usePlan} from '../context/PlainContext';
import type {ColDef, GridReadyEvent, RowDoubleClickedEvent, RowStyle, SelectionChangedEvent} from 'ag-grid-community';
import {AllCommunityModule, ModuleRegistry} from 'ag-grid-community';
import {
    Accordion,
    AccordionDetails,
    AccordionSummary,
    Alert,
    Box,
    Button,
    Card,
    CardContent,
    Checkbox,
    Chip,
    CircularProgress,
    Divider,
    FormControl,
    FormControlLabel,
    IconButton,
    InputLabel,
    MenuItem,
    Select,
    TextField,
    Tooltip,
    Typography,
} from '@mui/material';
import {
    Add as AddIcon,
    Archive as ArchiveIcon,
    ArrowDropDown as ArrowDropDownIcon,
    ArrowRight as ArrowRightIcon,
    Autorenew as RescheduleIcon,
    Close as CloseIcon,
    Delete as DeleteIcon,
    Edit as EditIcon,
    Error as ErrorIcon,
    ExpandMore as ExpandMoreIcon,
    History as HistoryIcon,
    Info as InfoIcon,
    Launch as LaunchIcon,
    PlayArrow as PlayIcon,
    Psychology as AdvisorIcon,
    Refresh as RefreshIcon,
    Save as SaveIcon,
    Settings as SettingsIcon,
    Timeline as TimelineIcon,
    Unarchive as UnarchiveIcon,
    Visibility as ViewIcon,
    Warning as WarningIcon,
} from '@mui/icons-material';
import {Allotment} from 'allotment';
import 'allotment/dist/style.css';
import {advisorApi, planSettingsApi, rescheduleApi, scheduleApi, settingsApi} from '../services/api';
import type {AdvisorResponse, AdvisorSeverity, AdvisorTip, RescheduleReason, RescheduleResponse,} from '../types';
import PlanSettingsWizard, {type WizardMode} from './PlanSettingsWizard';
import DraggableDialog from '../components/common/DraggableDialog';
import {ConfirmDialog} from '../components/common/ConfirmDialog';
import Hint from '../components/help/Hint';
import {useExpandedRoots} from '../hooks/useExpandedRoots';
import AppAgGrid from '../components/common/AppAgGrid';
import RecalcProgressDialog from '../components/gantt/RecalcProgressDialog';

ModuleRegistry.registerModules([AllCommunityModule]);

const VERSION_TYPE_LABELS: Record<string, string> = {
    MONTHLY: 'Месячный (ОКП)',
    SHIFT: 'Посменный',
    WHAT_IF: 'Сценарий "что если"',
};

const SEVERITY_COLORS: Record<AdvisorSeverity, 'error' | 'warning' | 'info'> = {
    CRITICAL: 'error', WARNING: 'warning', INFO: 'info',
};

const SEVERITY_LABELS: Record<AdvisorSeverity, string> = {
    CRITICAL: 'Критично', WARNING: 'Внимание', INFO: 'Инфо',
};

const SEVERITY_ICONS: Record<AdvisorSeverity, React.ReactNode> = {
    CRITICAL: <ErrorIcon fontSize="small" />,
    WARNING: <WarningIcon fontSize="small" />,
    INFO: <InfoIcon fontSize="small" />,
};

const DEFAULT_HORIZON_HOURS = 720;
const DEFAULT_TIMEOUT_SECONDS = 600;

interface PlanVersionWithPath extends PlanVersion {
    path: string[];
    depth: number;
    rootId: string;
    hasChildren: boolean;
}

const buildVersionTree = (versions: PlanVersion[]): PlanVersionWithPath[] => {
    const byId = new Map<string, PlanVersion>();
    for (const v of versions) byId.set(v.id, v);

    const childrenMap = new Map<string, PlanVersion[]>();
    for (const v of versions) {
        const parentId = v.parent_version_id && byId.has(v.parent_version_id) ? v.parent_version_id : '__root__';
        if (!childrenMap.has(parentId)) childrenMap.set(parentId, []);
        childrenMap.get(parentId)!.push(v);
    }

    for (const children of childrenMap.values()) {
        children.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
    }

    const result: PlanVersionWithPath[] = [];
    const visit = (version: PlanVersion, path: string[], depth: number, rootId: string) => {
        const newPath = [...path, version.id];
        const children = childrenMap.get(version.id) || [];
        const hasChildren = children.length > 0;
        result.push({...version, path: newPath, depth, rootId, hasChildren});
        for (const child of children) visit(child, newPath, depth + 1, rootId);
    };

    const roots = childrenMap.get('__root__') || [];
    for (const root of roots) visit(root, [], 0, root.id);

    return result;
};

interface ConfirmState {
    open: boolean;
    title: string;
    message: string;
    onConfirm: () => void;
    severity?: 'warning' | 'error' | 'info';
    confirmText?: string;
}

const SchedulePage: React.FC = () => {
    const {
        versions, setPlan, clearPlan, loadVersions, currentVersionId,
        currentPlanName,
        isCurrentPlanDraft,
        includeArchived, setIncludeArchived, unarchiveVersion,
        archiveVersion, deleteArchivedVersions,
        isCalculating, setIsCalculating,
    } = usePlan();
    const navigate = useNavigate();

    const [horizonHours, setHorizonHours] = useState<number>(DEFAULT_HORIZON_HOURS);
    const [solverTimeout, setSolverTimeout] = useState<number>(DEFAULT_TIMEOUT_SECONDS);
    const [planningStartDate, setPlanningStartDate] = useState<string>('');
    const [settingsLoaded, setSettingsLoaded] = useState(false);
    const [settingsSaving, setSettingsSaving] = useState(false);

    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState<any>(null);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);

    const [advisorData, setAdvisorData] = useState<AdvisorResponse | null>(null);
    const [advisorLoading, setAdvisorLoading] = useState(false);
    const [advisorError, setAdvisorError] = useState<string | null>(null);
    const [advisorForVersionId, setAdvisorForVersionId] = useState<string | null>(null);

    const [shiftHistoryOpen, setShiftHistoryOpen] = useState(false);
    const [shiftHistoryData, setShiftHistoryData] = useState<AdvisorTip | null>(null);

    const [wizardOpen, setWizardOpen] = useState(false);
    const [wizardMode, setWizardMode] = useState<WizardMode>('edit');
    const [wizardVersionId, setWizardVersionId] = useState<string | null>(null);
    const [wizardBaseVersionId, setWizardBaseVersionId] = useState<string | null>(null);
    const [wizardInitialName, setWizardInitialName] = useState<string>('');

    const [rescheduleDialogOpen, setRescheduleDialogOpen] = useState(false);
    const [rescheduleForm, setRescheduleForm] = useState<{reason: RescheduleReason; frozen_before: string; comment: string;}>({ reason: 'DELAY', frozen_before: '', comment: '' });
    const [rescheduling, setRescheduling] = useState(false);
    const [rescheduleResult, setRescheduleResult] = useState<RescheduleResponse | null>(null);

    const [confirmState, setConfirmState] = useState<ConfirmState>({
        open: false,
        title: '',
        message: '',
        onConfirm: () => {},
    });

    const expandedRoots = useExpandedRoots();
    const isLoadingAdvisorRef = useRef(false);
    const gridApiRef = useRef<any>(null);

    const showConfirm = (opts: Omit<ConfirmState, 'open'>) => {
        setConfirmState({ ...opts, open: true });
    };
    const hideConfirm = () => {
        setConfirmState(prev => ({ ...prev, open: false }));
    };

    const savePlanningSettings = useCallback(async (horizon: number, timeout: number, startDate: string): Promise<boolean> => {
        setSettingsSaving(true);
        try {
            const payload: Record<string, any> = { horizon_hours: horizon, timeout_seconds: timeout };
            if (startDate) payload.planning_start_date = `${startDate}T08:00:00`;
            await settingsApi.updateBulk(payload);
            return true;
        } catch (err: any) {
            const detail = err.response?.data?.detail;
            setError(typeof detail === 'string' ? detail : 'Ошибка сохранения настроек');
            return false;
        } finally {
            setSettingsSaving(false);
        }
    }, []);

    const loadAdvisor = useCallback(async (versionIdOverride?: string) => {
        if (isLoadingAdvisorRef.current) {
            console.log('[Advisor] Запрос уже выполняется, пропускаем');
            return;
        }
        isLoadingAdvisorRef.current = true;
        setAdvisorLoading(true);
        setAdvisorError(null);

        const targetVersionId = versionIdOverride || currentVersionId || undefined;

        try {
            const data = await advisorApi.getAdvice(targetVersionId);
            setAdvisorData(data);
            setAdvisorForVersionId(versionIdOverride && versionIdOverride !== currentVersionId ? versionIdOverride : null);
        } catch (err: any) {
            const detail = err.response?.data?.detail;
            setAdvisorError(typeof detail === 'string' ? detail : 'Ошибка загрузки подсказок');
        } finally {
            setAdvisorLoading(false);
            isLoadingAdvisorRef.current = false;
        }
    }, [currentVersionId]);

    useEffect(() => {
        loadVersions();
        loadAdvisor();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [loadVersions]);

    useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                const settings = await settingsApi.getCategory('planning');
                if (cancelled) return;
                if (typeof settings.horizon_hours === 'number') setHorizonHours(settings.horizon_hours);
                if (typeof settings.timeout_seconds === 'number') setSolverTimeout(settings.timeout_seconds);
                if (typeof settings.planning_start_date === 'string' && settings.planning_start_date.length > 0) {
                    setPlanningStartDate(settings.planning_start_date.slice(0, 10));
                }
            } catch (err: any) {
                console.warn('[SchedulePage] Не удалось загрузить настройки planning:', err);
            } finally {
                if (!cancelled) setSettingsLoaded(true);
            }

            if (currentVersionId && !cancelled) {
                try {
                    const planData = await planSettingsApi.getForVersion(currentVersionId);
                    if (cancelled) return;
                    const t = planData.settings.timeout_seconds;
                    const h = planData.settings.horizon_hours;
                    const d = planData.settings.planning_start_date;
                    if (typeof t === 'number' && t > 0) setSolverTimeout(t);
                    if (typeof h === 'number' && h > 0) setHorizonHours(h);
                    if (typeof d === 'string' && d.length > 0) setPlanningStartDate(d.slice(0, 10));
                } catch (err: any) {
                    console.warn('[SchedulePage] Не удалось загрузить настройки плана:', err);
                }
            }
        })();
        return () => { cancelled = true; };
    }, [currentVersionId]);

    const handleBuildSchedule = async () => {
        if (!currentVersionId) {
            setError('Сначала откройте план');
            return;
        }
        setLoading(true); setError(null); setResult(null);
        setIsCalculating(true);
        try {
            await savePlanningSettings(horizonHours, solverTimeout, planningStartDate);
            const data = await scheduleApi.build({
                horizon_hours: horizonHours,
                timeout_seconds: solverTimeout,
                version_id: currentVersionId,
            });
            setResult(data);
            await loadVersions();
            await loadAdvisor();
        } catch (err: any) {
            const detail = err.response?.data?.detail;
            setError(typeof detail === 'string' ? detail : 'Ошибка при построении плана');
        } finally {
            setLoading(false);
            setIsCalculating(false);
        }
    };

    const handleSaveSettings = async () => {
        const ok = await savePlanningSettings(horizonHours, solverTimeout, planningStartDate);
        if (ok) {
            if (currentVersionId) {
                try {
                    const payload: Record<string, any> = {
                        horizon_hours: horizonHours,
                        timeout_seconds: solverTimeout,
                    };
                    if (planningStartDate) payload.planning_start_date = `${planningStartDate}T08:00:00`;
                    await planSettingsApi.updateForVersion(currentVersionId, { settings: payload });
                } catch (err: any) {
                    console.warn('[SchedulePage] Ошибка сохранения plan_settings:', err);
                }
            }
            setError(null);
        }
    };

    const handleDeletePlan = async (version: PlanVersion) => {
        showConfirm({
            title: 'Удаление плана',
            message: `Вы уверены, что хотите удалить план "${version.name}"?`,
            severity: 'error',
            confirmText: 'Удалить',
            onConfirm: async () => {
                hideConfirm();
                try {
                    await scheduleApi.deleteVersion(version.id);
                    if (currentVersionId === version.id) clearPlan();
                    await loadVersions();
                } catch (err: any) {
                    setError(err.response?.data?.detail || 'Ошибка удаления плана');
                }
            }
        });
    };

    const handleUnarchivePlan = async (version: PlanVersion) => {
        showConfirm({
            title: 'Разархивация',
            message: `Разархивировать план "${version.name}"?`,
            severity: 'info',
            confirmText: 'Разархивировать',
            onConfirm: async () => {
                hideConfirm();
                try {
                    await unarchiveVersion(version.id);
                    setSuccess(`План «${version.name}» разархивирован`);
                } catch (err: any) {
                    setError(err.response?.data?.detail || 'Ошибка разархивации плана');
                }
            }
        });
    };

    const handleArchivePlan = async (version: PlanVersion) => {
        showConfirm({
            title: 'Архивация',
            message: `Архивировать план "${version.name}"?`,
            severity: 'warning',
            confirmText: 'Архивировать',
            onConfirm: async () => {
                hideConfirm();
                try {
                    await archiveVersion(version.id);
                    setSuccess(`План «${version.name}» архивирован`);
                } catch (err: any) {
                    setError(err.response?.data?.detail || 'Ошибка архивации плана');
                }
            }
        });
    };

    const handleClearArchive = async () => {
        const count = versions.filter((v) => v.is_archived).length;
        if (count === 0) return;

        showConfirm({
            title: 'Очистка архива',
            message: `Удалить все архивные версии (${count} шт)?`,
            severity: 'error',
            confirmText: 'Удалить всё',
            onConfirm: async () => {
                hideConfirm();
                try {
                    const deleted = await deleteArchivedVersions();
                    setSuccess(`Удалено архивных версий: ${deleted}`);
                } catch (err: any) {
                    setError('Ошибка очистки архива');
                }
            }
        });
    };

    const handleSelectPlan = useCallback((version: PlanVersion) => {
        setPlan(version.id, version.name, version.has_snapshot !== false, version.has_advisor_notes === true, version.is_draft, version.parent_version_id);
    }, [setPlan]);

    const handleOpenPlanGantt = (version: PlanVersion) => {
        setPlan(version.id, version.name, version.has_snapshot !== false, version.has_advisor_notes === true, version.is_draft, version.parent_version_id);
        navigate('/gantt');
    };

    const handleClosePlan = () => clearPlan();

    const handleOpenWizardEdit = (versionId: string) => {
        setWizardMode('edit'); setWizardVersionId(versionId); setWizardOpen(true);
    };

    const handleOpenWizardCreate = () => {
        setWizardMode('create'); setWizardVersionId(null); setWizardBaseVersionId(null); setWizardInitialName(''); setWizardOpen(true);
    };

    const handleWizardSaved = async (versionId: string, action: 'save' | 'save-and-build' | 'create-and-build') => {
        await loadVersions();
        if (action === 'create-and-build' || action === 'save-and-build') {
            const createdPlan = versions.find((v) => v.id === versionId) || (await scheduleApi.getVersions() as PlanVersion[]).find((v: PlanVersion) => v.id === versionId);
            if (createdPlan) {
                setPlan(createdPlan.id, createdPlan.name, createdPlan.has_snapshot !== false, createdPlan.has_advisor_notes === true, createdPlan.is_draft, createdPlan.parent_version_id);
            }
            setWizardOpen(false);
            navigate(`/gantt?version_id=${versionId}`);
        }
    };

    const handleOpenReschedule = () => {
        if (!currentVersionId) { setError('Сначала откройте план'); return; }
        setRescheduleForm({ reason: 'DELAY', frozen_before: '', comment: '' });
        setRescheduleResult(null); setRescheduleDialogOpen(true);
    };

    const handleDoReschedule = async () => {
        if (!currentVersionId) return;
        setRescheduling(true); setError(null);
        try {
            let autoArchive = true;
            try {
                const planningSettings = await settingsApi.getCategory('planning');
                if (typeof planningSettings.auto_archive_on_recalc === 'boolean') autoArchive = planningSettings.auto_archive_on_recalc;
            } catch { autoArchive = true; }

            const payload = {
                from_version_id: currentVersionId, reason: rescheduleForm.reason,
                changes: {}, frozen_before: rescheduleForm.frozen_before || null,
                comment: rescheduleForm.comment || null,
                replace_version_id: autoArchive ? currentVersionId : null,
            };
            const res = await rescheduleApi.reschedule(payload);
            setRescheduleResult(res); await loadVersions();
            if (res.to_version_id) setPlan(res.to_version_id, `Перепланировано от ${new Date().toLocaleString('ru-RU')}`, true, false);
        } catch (err: any) {
            setError(typeof err.response?.data?.detail === 'string' ? err.response.data.detail : 'Ошибка перепланирования');
        } finally {
            setRescheduling(false);
        }
    };

    const openShiftHistory = useCallback((tip: AdvisorTip) => {
        setShiftHistoryData(tip); setShiftHistoryOpen(true);
    }, []);

    const shiftHistoryColDefs = useMemo<ColDef[]>(() => [
        { field: 'batch_id', headerName: 'Партия', width: 110, valueFormatter: p => p.value?.substring(0, 8) },
        { field: 'operation_name', headerName: 'Операция', flex: 1, minWidth: 200 },
        { field: 'old_start', headerName: 'Было', width: 140, valueFormatter: p => formatDateTimeShort(p.value) },
        { field: 'new_start', headerName: 'Стало', width: 140, valueFormatter: p => formatDateTimeShort(p.value) },
        { field: 'delta_minutes', headerName: 'Δ, мин', width: 90, type: 'numericColumn' },
        { field: 'reason', headerName: 'Причина', flex: 1.5, minWidth: 250, valueFormatter: p => p.value || '—' },
    ], []);

    const versionsForTree = useMemo<PlanVersion[]>(() => {
        if (includeArchived) return versions;
        const byId = new Map(versions.map((v) => [v.id, v]));
        const toKeep = new Set<string>();
        const addWithParents = (v: PlanVersion) => {
            if (toKeep.has(v.id)) return;
            toKeep.add(v.id);
            if (v.parent_version_id && byId.has(v.parent_version_id)) addWithParents(byId.get(v.parent_version_id)!);
        };
        for (const v of versions) if (!v.is_archived) addWithParents(v);
        return versions.filter((v) => toKeep.has(v.id));
    }, [versions, includeArchived]);

    const treeData = useMemo(() => buildVersionTree(versionsForTree), [versionsForTree]);

    const visibleRows = useMemo(() => treeData.filter((node) => node.depth === 0 || expandedRoots.isExpanded(node.rootId)), [treeData, expandedRoots]);

    const renderNameCell = useCallback((params: any) => {
        const v = params.data as PlanVersionWithPath | undefined;
        if (!v) return null;
        const isRoot = v.depth === 0;
        const isExpanded = isRoot && expandedRoots.isExpanded(v.id);
        const isActive = v.is_active;
        const isArchived = v.is_archived;
        const hasSnapshot = v.has_snapshot !== false;
        const hasAdvisorNotes = v.has_advisor_notes === true;

        const handleAdvisorClick = (e: React.MouseEvent) => {
            e.stopPropagation(); setAdvisorForVersionId(v.id); loadAdvisor(v.id);
        };

        return (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', width: '100%', height: '100%', minWidth: 0 }}>
                <div style={{ width: 28, height: 28, flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    {isRoot && v.hasChildren && (
                        <IconButton size="small" onClick={(e) => { e.stopPropagation(); expandedRoots.toggle(v.id); }} sx={{ p: 0.25 }}>
                            {isExpanded ? <ArrowDropDownIcon fontSize="small"/> : <ArrowRightIcon fontSize="small"/>}
                        </IconButton>
                    )}
                </div>
                {!hasSnapshot && <WarningIcon fontSize="small" sx={{ color: '#e67e22', flexShrink: 0 }} />}
                <div style={{ flex: '1 1 200px', minWidth: '150px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontWeight: isActive ? 700 : 400, color: isArchived ? '#95a5a6' : 'inherit', fontSize: '0.875rem', cursor: 'pointer', userSelect: 'none' }}>
                    {v.name}
                </div>
                {hasAdvisorNotes && (
                    <Tooltip title="Есть заметки Advisor — нажмите, чтобы открыть">
                        <IconButton size="small" onClick={handleAdvisorClick} sx={{ p: 0.25, color: '#8e44ad', flexShrink: 0 }}>
                            <AdvisorIcon fontSize="small" />
                        </IconButton>
                    </Tooltip>
                )}
                {isActive && <Chip label="активный" color="success" size="small" sx={{ height: 18, fontSize: '0.65rem', flexShrink: 0 }} />}
            </div>
        );
    }, [expandedRoots, setSuccess, setError, loadAdvisor]);

    const columnDefs: ColDef<PlanVersionWithPath>[] = useMemo(() => [
        {
            headerName: 'Наименование', field: 'name', flex: 2, minWidth: 400, cellRenderer: renderNameCell, sortable: false, filter: false,
            cellStyle: (params: any) => ({ paddingLeft: 12 + (params.data as PlanVersionWithPath).depth * 24 }),
        },
        { headerName: 'Тип', field: 'version_type', width: 160, valueFormatter: (p) => VERSION_TYPE_LABELS[p.value] || p.value },
        { headerName: 'Дата создания', field: 'created_at', width: 180, valueFormatter: (p) => p.value ? new Date(p.value).toLocaleString('ru-RU') : '—' },
        { headerName: 'Комментарий', field: 'comment', flex: 1, valueFormatter: (p) => p.value || '—' },
        {
            headerName: 'Действия', width: 300, editable: false, sortable: false, filter: false,
            cellRenderer: (params: any) => {
                const version = params.data as PlanVersionWithPath;
                const isCurrent = version.id === currentVersionId;
                const hasSnapshot = version.has_snapshot !== false;
                const isArchived = version.is_archived === true;
                return (
                    <Box sx={{ display: 'flex', gap: 0.5, alignItems: 'center' }}>
                        {isCurrent ? (
                            <Tooltip title="Закрыть план"><IconButton size="small" color="warning" onClick={handleClosePlan}><CloseIcon fontSize="small" /></IconButton></Tooltip>
                        ) : (
                            <Tooltip title={hasSnapshot ? "Открыть план (Гант)" : "Открыть (нет снапшотов)"}>
                                <IconButton size="small" color={hasSnapshot ? 'primary' : 'warning'} onClick={() => handleOpenPlanGantt(version)}><ViewIcon fontSize="small" /></IconButton>
                            </Tooltip>
                        )}
                        <Tooltip title="Открыть Гант"><IconButton size="small" onClick={() => navigate(`/gantt?version_id=${version.id}`)}><TimelineIcon fontSize="small" /></IconButton></Tooltip>
                        <Tooltip title="Мастер настроек"><IconButton size="small" color="info" onClick={() => handleOpenWizardEdit(version.id)}><SettingsIcon fontSize="small" /></IconButton></Tooltip>

                        {!isArchived && !isCurrent && (
                            <Tooltip title="Архивировать (скрыть)">
                                <IconButton size="small" color="warning" onClick={() => handleArchivePlan(version)}>
                                    <ArchiveIcon fontSize="small" />
                                </IconButton>
                            </Tooltip>
                        )}
                        {isArchived && (
                            <Tooltip title="Разархивировать">
                                <IconButton size="small" color="success" onClick={() => handleUnarchivePlan(version)}>
                                    <UnarchiveIcon fontSize="small" />
                                </IconButton>
                            </Tooltip>
                        )}
                        <Tooltip title="Удалить"><IconButton size="small" color="error" onClick={() => handleDeletePlan(version)}><DeleteIcon fontSize="small" /></IconButton></Tooltip>
                    </Box>
                );
            },
        },
    ], [currentVersionId, renderNameCell, expandedRoots, navigate, setPlan, clearPlan, handleArchivePlan, handleUnarchivePlan, handleDeletePlan, handleOpenPlanGantt, handleOpenWizardEdit, handleClosePlan]);

    const renderAdvisorPanel = () => {
        const showingOtherVersion = advisorForVersionId !== null && advisorForVersionId !== currentVersionId;
        const advisorVersionInfo = showingOtherVersion ? versions.find((v) => v.id === advisorForVersionId) : null;
        let advisorVersionLabel = '';
        if (showingOtherVersion) {
            const shortId = advisorForVersionId ? advisorForVersionId.split('-')[0] : '—';
            advisorVersionLabel = advisorVersionInfo ? `${advisorVersionInfo.name} (версия: ${shortId})` : `(версия: ${shortId})`;
        }

        return (
            <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column', m: 0.5 }}>
                <CardContent sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', minHeight: 0, p: 2 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.5, flexShrink: 0 }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                            <Typography variant="h6" sx={{ fontWeight: 600, fontSize: '1rem' }}>Подсказки Advisor</Typography>
                            <Hint id="planning.advisor" size="small"/>
                            {advisorData && advisorData.critical_count > 0 && <Chip label={`Критично: ${advisorData.critical_count}`} color="error" size="small" />}
                            {advisorData && advisorData.warning_count > 0 && <Chip label={`Внимание: ${advisorData.warning_count}`} color="warning" size="small" />}
                            {advisorData && advisorData.info_count > 0 && <Chip label={`Инфо: ${advisorData.info_count}`} color="info" size="small" variant="outlined" />}
                            {showingOtherVersion && (
                                <Tooltip title={`ID: ${advisorForVersionId}`} arrow>
                                    <Chip label={advisorVersionLabel} size="small" color="secondary" onDelete={() => { setAdvisorForVersionId(null); loadAdvisor(); }} sx={{ maxWidth: 480, '& .MuiChip-label': { overflow: 'hidden', textOverflow: 'ellipsis' } }} />
                                </Tooltip>
                            )}
                        </Box>
                        <Button size="small" startIcon={<RefreshIcon />} onClick={() => loadAdvisor(advisorForVersionId ?? undefined)} sx={{ textTransform: 'none' }}>Обновить</Button>
                    </Box>
                    <Divider sx={{ mb: 1.5, flexShrink: 0 }} />
                    <Box sx={{ flexGrow: 1, overflow: 'auto', minHeight: 0 }}>
                        {advisorLoading && <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}><CircularProgress size={24} /></Box>}
                        {!advisorLoading && advisorError && <Alert severity="error" onClose={() => setAdvisorError(null)}>{advisorError}</Alert>}
                        {!advisorLoading && !advisorError && (!advisorData || advisorData.tips.length === 0) && <Alert severity="success">Подсказок нет. Все проверки пройдены.</Alert>}
                        {!advisorLoading && !advisorError && advisorData && advisorData.tips.length > 0 && (
                            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                                {advisorData.tips.map((tip, index) => (
                                    <Accordion key={`${tip.code}-${index}`} sx={{ boxShadow: 'none', border: '1px solid #e0e0e0', '&:before': { display: 'none' }, '&.Mui-expanded': { margin: 0 } }}>
                                        <AccordionSummary expandIcon={<ExpandMoreIcon />} sx={{ minHeight: 40, '& .MuiAccordionSummary-content': { my: 0.5 } }}>
                                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, width: '100%' }}>
                                                <Chip icon={SEVERITY_ICONS[tip.severity] as any} label={SEVERITY_LABELS[tip.severity]} color={SEVERITY_COLORS[tip.severity]} size="small" />
                                                <Typography variant="body2" sx={{ fontWeight: 600, flexGrow: 1 }}>{tip.title}</Typography>
                                                {tip.code === 'SHIFTED_TASKS' && (
                                                    <Tooltip title="Открыть полную историю сдвигов">
                                                        <Chip size="small" label="История →" variant="outlined" onClick={(e) => { e.stopPropagation(); openShiftHistory(tip); }} sx={{ cursor: 'pointer', mr: 1 }} />
                                                    </Tooltip>
                                                )}
                                            </Box>
                                        </AccordionSummary>
                                        <AccordionDetails sx={{ pt: 0 }}>
                                            <Typography variant="body2" sx={{ mb: 1 }}>{tip.message}</Typography>
                                            {tip.details && Object.keys(tip.details).length > 0 && (
                                                <Box sx={{ mt: 1, pt: 1, borderTop: '1px dashed #e0e0e0', fontSize: '0.75rem', color: 'text.secondary' }}>
                                                    {Array.isArray(tip.details.sample) && tip.details.sample.length > 0 && (
                                                        <>
                                                            <Typography variant="caption" sx={{ fontWeight: 600, display: 'block', mb: 0.5 }}>Первые {Math.min(10, tip.details.sample.length)} сдвинутых задач:</Typography>
                                                            <Box component="table" sx={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.72rem', '& th': { textAlign: 'left', fontWeight: 600, pb: 0.25, color: '#555' }, '& td': { pb: 0.25, pr: 1, verticalAlign: 'top' } }}>
                                                                <thead><tr><th>Партия</th><th>Операция</th><th>Было → Стало</th><th>Δ мин</th><th>Причина</th></tr></thead>
                                                                <tbody>
                                                                {tip.details.sample.slice(0, 10).map((s: any, i: number) => (
                                                                    <tr key={i}>
                                                                        <td style={{ fontFamily: 'monospace' }}>{(s.batch_id || '').substring(0, 8)}</td>
                                                                        <td>{s.operation_name || '—'}</td>
                                                                        <td style={{ fontFamily: 'monospace', fontSize: '0.7rem' }}>{(s.old_start || '').substring(5, 16)} → {(s.new_start || '').substring(5, 16)}</td>
                                                                        <td>{s.delta_minutes ?? '—'}</td>
                                                                        <td>{s.reason || '—'}</td>
                                                                    </tr>
                                                                ))}
                                                                </tbody>
                                                            </Box>
                                                        </>
                                                    )}
                                                    {tip.details.plan_start && tip.details.plan_end && (
                                                        <Typography variant="caption" sx={{ display: 'block', mt: 0.5 }}><b>План:</b> {new Date(tip.details.plan_start).toLocaleDateString('ru-RU')} → {new Date(tip.details.plan_end).toLocaleDateString('ru-RU')}</Typography>
                                                    )}
                                                    {tip.details.reason && tip.details.batch_id && tip.code === 'SKIPPED_BATCHES' && (
                                                        <Typography variant="caption" sx={{ display: 'block', mt: 0.5 }}><b>Партия:</b> <span style={{ fontFamily: 'monospace' }}>{String(tip.details.batch_id).substring(0, 8)}</span> — {tip.details.reason}</Typography>
                                                    )}
                                                </Box>
                                            )}
                                        </AccordionDetails>
                                    </Accordion>
                                ))}
                            </Box>
                        )}
                    </Box>
                </CardContent>
            </Card>
        );
    };

    const renderPlansGrid = () => {
        const archivedCount = versions.filter((v) => v.is_archived).length;
        const totalRoots = treeData.filter((n) => n.depth === 0).length;
        const expandedCount = treeData.filter((n) => n.depth === 0 && expandedRoots.isExpanded(n.id)).length;

        return (
            <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column', m: 0.5 }}>
                <CardContent sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', minHeight: 0, p: 2 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1, flexShrink: 0, flexWrap: 'wrap' }}>
                        <HistoryIcon color="primary" />
                        <Typography variant="h6" sx={{ fontWeight: 600, fontSize: '1rem' }}>История планов ({visibleRows.length}/{treeData.length})</Typography>
                        <Hint id="planning.plan_dirty" size="small"/>
                        {archivedCount > 0 && !includeArchived && <Chip icon={<ArchiveIcon />} label={`Архив: ${archivedCount}`} size="small" color="default" variant="outlined" />}

                        <Box sx={{ display: 'flex', gap: 0.5, ml: 1 }}>
                            <Tooltip title="Развернуть все корни">
                                <Button size="small" variant="text" startIcon={<ArrowDropDownIcon />} onClick={() => expandedRoots.expandAll(treeData.filter(n => n.depth === 0).map(n => n.id))} disabled={expandedCount === totalRoots} sx={{ textTransform: 'none', fontSize: '0.75rem' }}>Развернуть</Button>
                            </Tooltip>
                            <Tooltip title="Свернуть все корни">
                                <Button size="small" variant="text" startIcon={<ArrowRightIcon />} onClick={() => expandedRoots.collapseAll(treeData.filter(n => n.depth === 0).map(n => n.id))} disabled={expandedCount === 0} sx={{ textTransform: 'none', fontSize: '0.75rem' }}>Свернуть</Button>
                            </Tooltip>
                        </Box>

                        {archivedCount > 0 && (
                            <Tooltip title="Удалить все архивные версии">
                                <Button size="small" variant="text" color="error" startIcon={<DeleteIcon />} onClick={handleClearArchive} sx={{ textTransform: 'none', fontSize: '0.75rem', ml: 1 }}>
                                    Очистить архив
                                </Button>
                            </Tooltip>
                        )}

                        <FormControlLabel control={<Checkbox size="small" checked={includeArchived} onChange={(e) => setIncludeArchived(e.target.checked)} />} label={<Typography variant="caption">Показать архивные</Typography>} sx={{ ml: 'auto' }} />
                        {currentVersionId && <Chip icon={<TimelineIcon />} label="Один из планов открыт" size="small" color="info" variant="outlined" />}
                    </Box>
                    <Box sx={{ flexGrow: 1, width: '100%', minHeight: 0 }}>
                        <AppAgGrid
                            rowData={visibleRows}
                            columnDefs={columnDefs}
                            defaultColDef={{ sortable: true, filter: true, resizable: true }}
                            rowSelection={{ mode: 'singleRow', enableClickSelection: true }}
                            onGridReady={(params: GridReadyEvent) => {
                                params.api.sizeColumnsToFit();
                                gridApiRef.current = params.api;
                                if (currentVersionId) {
                                    params.api.forEachNode((node: any) => {
                                        if (node.data && node.data.id === currentVersionId) {
                                            node.setSelected(true);
                                        }
                                    });
                                }
                            }}
                            getRowId={(params: any) => params.data.id}
                            onRowDoubleClicked={(params: RowDoubleClickedEvent) => handleSelectPlan(params.data)}
                            onSelectionChanged={(event: SelectionChangedEvent) => {
                                const selected = event.api.getSelectedRows();
                                if (selected.length > 0) {
                                    handleSelectPlan(selected[0]);
                                }
                            }}
                            getRowStyle={(params: any): RowStyle | undefined => {
                                const v = params.data as PlanVersionWithPath | undefined;
                                if (!v) return undefined;
                                if (v.id === currentVersionId) return { backgroundColor: '#e3f2fd', boxShadow: 'inset 4px 0 0 0 #1976d2', color: '#0d47a1' } as RowStyle;
                                if (v.is_active) return { backgroundColor: '#e8f5e9', color: '#1b5e20' } as RowStyle;
                                if (v.is_archived) return { backgroundColor: '#f5f5f5', color: '#7f8c8d' } as RowStyle;
                                if (v.has_snapshot === false) return { backgroundColor: '#fff8e1', color: '#7f6000' } as RowStyle;
                                return undefined;
                            }}
                        />
                    </Box>
                </CardContent>
            </Card>
        );
    };

    const buildDisabled = loading || isCalculating || !currentVersionId;
    const buildButtonLabel = !currentVersionId
        ? 'Откройте план'
        : (loading ? 'Расчёт...' : 'Построить план');

    return (
        <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2, flexShrink: 0 }}>
                <Typography variant="h4" component="h1" sx={{ fontWeight: 600, color: '#2c3e50' }}>Планирование производства</Typography>
                <Box sx={{ display: 'flex', gap: 1 }}>
                    <Button variant="outlined" startIcon={<RescheduleIcon />} onClick={handleOpenReschedule} disabled={!currentVersionId || isCurrentPlanDraft} sx={{ textTransform: 'none' }}>Перепланировать</Button>
                    <Button variant="outlined" startIcon={<AddIcon />} onClick={handleOpenWizardCreate} sx={{ textTransform: 'none' }}>Новый план</Button>
                </Box>
            </Box>

            {error && <Alert severity="error" sx={{ mb: 2, flexShrink: 0 }} onClose={() => setError(null)}>{error}</Alert>}
            {success && <Alert severity="success" sx={{ mb: 2, flexShrink: 0 }} onClose={() => setSuccess(null)}>{success}</Alert>}

            <Card sx={{ mb: 2, flexShrink: 0 }}>
                <CardContent sx={{ py: 2, '&:last-child': { pb: 2 } }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                        <Typography variant="h6" sx={{ fontWeight: 600, fontSize: '1rem' }}>Параметры расчёта</Typography>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            {settingsLoaded && <Chip label="Из настроек" size="small" color="info" variant="outlined" />}
                            {currentVersionId && (
                                <>
                                    <Chip
                                        icon={isCurrentPlanDraft ? <EditIcon /> : <TimelineIcon />}
                                        label={`План: ${currentPlanName}`}
                                        size="small"
                                        color={isCurrentPlanDraft ? 'warning' : 'primary'}
                                        variant="outlined"
                                        sx={{ maxWidth: 320, '& .MuiChip-label': { overflow: 'hidden', textOverflow: 'ellipsis' } }}
                                    />
                                </>
                            )}
                            {currentVersionId && !isCurrentPlanDraft && (
                                <Button size="small" variant="outlined" startIcon={<LaunchIcon />} onClick={() => navigate(`/gantt?version_id=${currentVersionId}`)} sx={{ textTransform: 'none' }}>
                                    Перейти на Гант
                                </Button>
                            )}
                            <Button size="small" variant="outlined" startIcon={<SaveIcon />} onClick={handleSaveSettings} disabled={settingsSaving} sx={{ textTransform: 'none' }}>{settingsSaving ? 'Сохранение...' : 'Сохранить настройки'}</Button>
                        </Box>
                    </Box>
                    <Box sx={{ display: 'flex', gap: 2, mb: 1.5, flexWrap: 'wrap', alignItems: 'flex-start' }}>
                        <TextField label="Горизонт (часы)" type="number" value={horizonHours} onChange={(e) => setHorizonHours(Number(e.target.value))} size="small" sx={{ width: 160 }} helperText="Сохраняется в app_settings" />
                        <TextField label="Таймаут solver (сек)" type="number" value={solverTimeout} onChange={(e) => setSolverTimeout(Number(e.target.value))} size="small" sx={{ width: 180 }} helperText="Сохраняется в app_settings" />
                        <TextField label="Дата начала планирования" type="date" value={planningStartDate} onChange={(e) => setPlanningStartDate(e.target.value)} size="small" sx={{ width: 200 }} helperText="Отсчёт горизонта (МСК)" slotProps={{ inputLabel: { shrink: true } }} />
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, height: 40, mt: 0 }}>
                            <Tooltip title={!currentVersionId ? 'Сначала откройте план в списке ниже' : 'Результат будет записан в открытый план'}>
                                <span>
                                    <Button
                                        variant="contained"
                                        startIcon={loading ? <CircularProgress size={20} /> : <PlayIcon />}
                                        onClick={handleBuildSchedule}
                                        disabled={buildDisabled}
                                        sx={{ textTransform: 'none', height: 40 }}
                                    >
                                        {buildButtonLabel}
                                    </Button>
                                </span>
                            </Tooltip>
                            <Hint id="planning.recalc" size="medium"/>
                        </Box>
                    </Box>
                    <Typography variant="caption" color="text.secondary">
                        💡 Расчёт записывается в открытый план (перезапись задач и снапшотов). Параметры сохраняются в app_settings.
                    </Typography>
                    {result && <Alert severity="success" sx={{ mt: 1 }}>Расчёт завершён: {result.total_tasks} задач, Makespan: {result.makespan_hours.toFixed(1)} ч</Alert>}
                </CardContent>
            </Card>

            <Box sx={{ flexGrow: 1, minHeight: 0, mx: -0.5 }}>
                <Allotment vertical defaultSizes={[30, 70]}>
                    <Allotment.Pane minSize={180} preferredSize="30%">{renderAdvisorPanel()}</Allotment.Pane>
                    <Allotment.Pane minSize={200}>{renderPlansGrid()}</Allotment.Pane>
                </Allotment>
            </Box>

            <PlanSettingsWizard
                open={wizardOpen}
                onClose={() => {
                    setWizardOpen(false);
                }}
                mode={wizardMode}
                versionId={wizardVersionId}
                baseVersionId={wizardBaseVersionId}
                initialName={wizardInitialName}
                onSaved={handleWizardSaved}
            />

            <DraggableDialog open={rescheduleDialogOpen} onClose={() => setRescheduleDialogOpen(false)} title="Перепланирование" initialWidth={640} initialHeight="auto" minWidth={480} minHeight={320}
                             actions={<><Button onClick={() => setRescheduleDialogOpen(false)}>{rescheduleResult ? 'Закрыть' : 'Отмена'}</Button>{!rescheduleResult && <Button onClick={handleDoReschedule} variant="contained" disabled={rescheduling} startIcon={rescheduling ? <CircularProgress size={20} /> : <RescheduleIcon />}>{rescheduling ? 'Перепланирование...' : 'Перепланировать'}</Button>}</>}
            >
                {!rescheduleResult ? (
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                        <Alert severity="info">Перепланирование создаст новую версию плана. Задачи до <b>frozen_before</b> и задачи с флагом <b>is_pinned</b> не будут двигаться.</Alert>
                        <FormControl fullWidth variant="outlined">
                            <InputLabel>Причина перепланирования</InputLabel>
                            <Select value={rescheduleForm.reason} label="Причина перепланирования" variant="outlined" onChange={(e) => setRescheduleForm({ ...rescheduleForm, reason: e.target.value as RescheduleReason })}>
                                <MenuItem value="DELAY">Задержка операции</MenuItem>
                                <MenuItem value="BREAKDOWN">Поломка оборудования</MenuItem>
                                <MenuItem value="QTY_CHANGE">Изменение объёма</MenuItem>
                                <MenuItem value="MANUAL">Ручное изменение</MenuItem>
                            </Select>
                        </FormControl>
                        <TextField label="Заморозить до (frozen_before)" type="datetime-local" fullWidth value={rescheduleForm.frozen_before} onChange={(e) => setRescheduleForm({ ...rescheduleForm, frozen_before: e.target.value })} slotProps={{ inputLabel: { shrink: true } }} helperText="Задачи, начавшиеся до этого момента, не будут двигаться" />
                        <TextField label="Комментарий" fullWidth multiline rows={2} value={rescheduleForm.comment} onChange={(e) => setRescheduleForm({ ...rescheduleForm, comment: e.target.value })} />
                    </Box>
                ) : (
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                        <Alert severity="success">{rescheduleResult.message}</Alert>
                        {rescheduleResult.replace_blocked && <Alert severity="warning"><Typography variant="body2" sx={{ fontWeight: 600, mb: 0.5 }}>Старая версия не была архивирована</Typography><Typography variant="body2">{rescheduleResult.replace_blocked_reason || 'Версия используется в what-if сценариях.'}</Typography>{rescheduleResult.used_by_whatif.length > 0 && <Typography variant="caption" sx={{ display: 'block', mt: 0.5 }}>Сценарии: {rescheduleResult.used_by_whatif.join(', ')}</Typography>}</Alert>}
                        {rescheduleResult.replace_archived && <Alert severity="info" icon={<ArchiveIcon />}><Typography variant="body2">Старая версия перемещена в архив. Разархивировать можно через чекбокс «Показать архивные».</Typography></Alert>}
                        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}><Chip label={`Затронуто задач: ${rescheduleResult.affected_tasks}`} color="warning" /><Chip label={`Перенесено: ${rescheduleResult.moved_tasks}`} color="primary" /><Chip label={`Заморожено: ${rescheduleResult.frozen_tasks}`} variant="outlined" /></Box>
                        <Typography variant="caption" color="text.secondary">Новая версия: {rescheduleResult.to_version_id}</Typography>
                    </Box>
                )}
            </DraggableDialog>

            <DraggableDialog
                open={shiftHistoryOpen}
                onClose={() => setShiftHistoryOpen(false)}
                title="История сдвигов"
                initialWidth={1100}
                initialHeight={600}
                minWidth={800}
                minHeight={400}
                contentSx={{ p: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}
                actions={<Button onClick={() => setShiftHistoryOpen(false)}>Закрыть</Button>}
            >
                {shiftHistoryData ? (
                    <Box sx={{ flexGrow: 1, minHeight: 0, height: '100%', width: '100%', display: 'flex', flexDirection: 'column' }}>
                        <AppAgGrid
                            rowData={(shiftHistoryData.details?.sample || []).map((row: any, index: number) => ({ ...row, _rowIndex: index }))}
                            columnDefs={shiftHistoryColDefs}
                            defaultColDef={{ sortable: true, filter: true, resizable: true }}
                            getRowId={(params: any) => `row_${params.data._rowIndex}`}
                            pagination={true}
                            paginationPageSize={20}
                            paginationPageSizeSelector={[20, 50, 100]}
                            onGridReady={(params: any) => {
                                setTimeout(() => { try { params.api.sizeColumnsToFit(); } catch {} }, 150);
                            }}
                        />
                    </Box>
                ) : null}
            </DraggableDialog>
            
            <RecalcProgressDialog
                open={isCalculating}
                operationLabel="Построение плана (Solver)"
                operationHint="Solver рассчитывает расписание с учётом ограничений."
                timeoutSeconds={solverTimeout}
            />

            <ConfirmDialog
                open={confirmState.open}
                title={confirmState.title}
                message={confirmState.message}
                severity={confirmState.severity}
                confirmText={confirmState.confirmText}
                onConfirm={confirmState.onConfirm}
                onCancel={hideConfirm}
            />
        </Box>
    );
};

function formatDateTimeShort(iso?: string | null): string {
    if (!iso) return '—';
    const d = new Date(iso);
    if (isNaN(d.getTime())) return '—';
    return d.toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
}

export default SchedulePage;