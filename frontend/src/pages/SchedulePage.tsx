// frontend/src/pages/SchedulePage.tsx
// Итерация 13.21: «История планов» — собственная группировка (Вариант B).
// Итерация 13.22 (fix): renderNameCell — единый слот иконки 28×28.
// Итерация 15.2: добавлены контекстные подсказки <Hint/>:
//   - planning.recalc  — рядом с кнопкой «Построить план»
//   - planning.advisor — в заголовке панели Advisor
//   - planning.plan_dirty — в заголовке «История планов»
// Итерация 15.3: добавлены data-tour-id для интерактивного тура:
//   - build-plan-button — кнопка «Построить план»
//   - advisor-panel — панель Advisor
//   - plans-history — панель «История планов»
//   - open-gantt-button — иконка 👁 в строке плана

import React, {useCallback, useEffect, useMemo, useState} from 'react';
import {useNavigate} from 'react-router-dom';
import {type PlanVersion, usePlan} from '../context/PlainContext';
import type {ColDef, GridReadyEvent, RowStyle} from 'ag-grid-community';
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
    Error as ErrorIcon,
    ExpandMore as ExpandMoreIcon,
    History as HistoryIcon,
    Info as InfoIcon,
    PlayArrow as PlayIcon,
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
import {advisorApi, rescheduleApi, scheduleApi, settingsApi} from '../services/api';
import type {AdvisorResponse, AdvisorSeverity, RescheduleReason, RescheduleResponse} from '../types';
import PlanSettingsWizard, {type WizardMode} from './PlanSettingsWizard';
import DraggableDialog from '../components/common/DraggableDialog';
import Hint from '../components/help/Hint';
import {useExpandedRoots} from '../hooks/useExpandedRoots';
import AppAgGrid from '../components/common/AppAgGrid';

ModuleRegistry.registerModules([AllCommunityModule]);

const VERSION_TYPE_LABELS: Record<string, string> = {
    MONTHLY: 'Месячный (ОКП)',
    SHIFT: 'Посменный',
    WHAT_IF: 'Сценарий "что если"',
};

const SEVERITY_COLORS: Record<AdvisorSeverity, 'error' | 'warning' | 'info'> = {
    CRITICAL: 'error',
    WARNING: 'warning',
    INFO: 'info',
};

const SEVERITY_LABELS: Record<AdvisorSeverity, string> = {
    CRITICAL: 'Критично',
    WARNING: 'Внимание',
    INFO: 'Инфо',
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
        const parentId =
            v.parent_version_id && byId.has(v.parent_version_id)
                ? v.parent_version_id
                : '__root__';
        if (!childrenMap.has(parentId)) childrenMap.set(parentId, []);
        childrenMap.get(parentId)!.push(v);
    }

    for (const children of childrenMap.values()) {
        children.sort((a, b) => {
            const at = new Date(a.created_at).getTime();
            const bt = new Date(b.created_at).getTime();
            return bt - at;
        });
    }

    const result: PlanVersionWithPath[] = [];

    const visit = (
        version: PlanVersion,
        path: string[],
        depth: number,
        rootId: string,
    ) => {
        const newPath = [...path, version.id];
        const children = childrenMap.get(version.id) || [];
        const hasChildren = children.length > 0;
        result.push({...version, path: newPath, depth, rootId, hasChildren});
        for (const child of children) {
            visit(child, newPath, depth + 1, rootId);
        }
    };

    const roots = childrenMap.get('__root__') || [];
    for (const root of roots) {
        visit(root, [], 0, root.id);
    }

    return result;
};

const SchedulePage: React.FC = () => {
    const {
        versions,
        setPlan,
        clearPlan,
        loadVersions,
        currentVersionId,
        includeArchived,
        setIncludeArchived,
        unarchiveVersion,
    } = usePlan();
    const navigate = useNavigate();

    const [horizonHours, setHorizonHours] = useState<number>(DEFAULT_HORIZON_HOURS);
    const [solverTimeout, setSolverTimeout] = useState<number>(DEFAULT_TIMEOUT_SECONDS);
    const [settingsLoaded, setSettingsLoaded] = useState(false);
    const [settingsSaving, setSettingsSaving] = useState(false);

    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState<any>(null);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);

    const [advisorData, setAdvisorData] = useState<AdvisorResponse | null>(null);
    const [advisorLoading, setAdvisorLoading] = useState(false);
    const [advisorError, setAdvisorError] = useState<string | null>(null);

    const [wizardOpen, setWizardOpen] = useState(false);
    const [wizardMode, setWizardMode] = useState<WizardMode>('edit');
    const [wizardVersionId, setWizardVersionId] = useState<string | null>(null);

    const [rescheduleDialogOpen, setRescheduleDialogOpen] = useState(false);
    const [rescheduleForm, setRescheduleForm] = useState<{
        reason: RescheduleReason;
        frozen_before: string;
        comment: string;
    }>({
        reason: 'DELAY',
        frozen_before: '',
        comment: '',
    });
    const [rescheduling, setRescheduling] = useState(false);
    const [rescheduleResult, setRescheduleResult] = useState<RescheduleResponse | null>(null);

    const expandedRoots = useExpandedRoots();

    const loadPlanningSettings = useCallback(async () => {
        try {
            const settings = await settingsApi.getCategory('planning');
            if (typeof settings.horizon_hours === 'number') {
                setHorizonHours(settings.horizon_hours);
            }
            if (typeof settings.timeout_seconds === 'number') {
                setSolverTimeout(settings.timeout_seconds);
            }
        } catch (err: any) {
            console.warn('[SchedulePage] Не удалось загрузить настройки planning:', err);
        } finally {
            setSettingsLoaded(true);
        }
    }, []);

    const savePlanningSettings = useCallback(async (
        horizon: number,
        timeout: number,
    ): Promise<boolean> => {
        setSettingsSaving(true);
        try {
            await settingsApi.updateBulk({
                horizon_hours: horizon,
                timeout_seconds: timeout,
            });
            return true;
        } catch (err: any) {
            const detail = err.response?.data?.detail;
            setError(typeof detail === 'string' ? detail : 'Ошибка сохранения настроек');
            return false;
        } finally {
            setSettingsSaving(false);
        }
    }, []);

    useEffect(() => {
        loadVersions();
        loadPlanningSettings();
        loadAdvisor();
    }, [loadVersions, loadPlanningSettings]);

    const loadAdvisor = async () => {
        setAdvisorLoading(true);
        setAdvisorError(null);
        try {
            const data = await advisorApi.getAdvice(currentVersionId || undefined);
            setAdvisorData(data);
        } catch (err: any) {
            const detail = err.response?.data?.detail;
            setAdvisorError(typeof detail === 'string' ? detail : 'Ошибка загрузки подсказок');
        } finally {
            setAdvisorLoading(false);
        }
    };

    const handleBuildSchedule = async () => {
        setLoading(true);
        setError(null);
        setResult(null);
        try {
            await savePlanningSettings(horizonHours, solverTimeout);
            const data = await scheduleApi.build({
                horizon_hours: horizonHours,
                timeout_seconds: solverTimeout,
            });
            setResult(data);
            await loadVersions();
            await loadAdvisor();
        } catch (err: any) {
            const detail = err.response?.data?.detail;
            const errorMsg = typeof detail === 'string'
                ? detail
                : Array.isArray(detail)
                    ? detail.map((d: any) => d.msg).join('; ')
                    : 'Ошибка при построении плана';
            setError(errorMsg);
        } finally {
            setLoading(false);
        }
    };

    const handleSaveSettings = async () => {
        const ok = await savePlanningSettings(horizonHours, solverTimeout);
        if (ok) setError(null);
    };

    const handleDeletePlan = async (version: PlanVersion) => {
        if (!window.confirm(`Удалить план "${version.name}"?`)) return;
        try {
            await scheduleApi.deleteVersion(version.id);
            if (currentVersionId === version.id) {
                clearPlan();
            }
            await loadVersions();
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Ошибка удаления плана');
        }
    };

    const handleUnarchivePlan = async (version: PlanVersion) => {
        if (!window.confirm(`Разархивировать план "${version.name}"?`)) return;
        try {
            await unarchiveVersion(version.id);
            setSuccess(`План «${version.name}» разархивирован`);
        } catch (err: any) {
            setError(
                err.response?.data?.detail
                || 'Ошибка разархивации плана',
            );
        }
    };

    const handleOpenPlan = (version: PlanVersion) => {
        setPlan(
            version.id,
            version.name,
            version.has_snapshot !== false,
        );
        navigate('/gantt');
    };

    const handleClosePlan = () => {
        clearPlan();
    };

    const handleOpenWizardEdit = (versionId: string) => {
        setWizardMode('edit');
        setWizardVersionId(versionId);
        setWizardOpen(true);
    };

    const handleOpenWizardCreate = () => {
        setWizardMode('create');
        setWizardVersionId(null);
        setWizardOpen(true);
    };

    const handleWizardSaved = async (
        versionId: string,
        action: 'save' | 'save-and-build' | 'create-and-build',
    ) => {
        await loadVersions();
        if (action === 'create-and-build' || action === 'save-and-build') {
            setWizardOpen(false);
            navigate(`/gantt?version_id=${versionId}`);
        }
        if (action === 'create-and-build') {
            await loadVersions();
        }
    };

    const handleOpenReschedule = () => {
        if (!currentVersionId) {
            setError('Сначала откройте сохранённую версию плана');
            return;
        }
        setRescheduleForm({
            reason: 'DELAY',
            frozen_before: '',
            comment: '',
        });
        setRescheduleResult(null);
        setRescheduleDialogOpen(true);
    };

    const handleDoReschedule = async () => {
        if (!currentVersionId) return;
        setRescheduling(true);
        setError(null);
        try {
            let autoArchive = true;
            try {
                const planningSettings = await settingsApi.getCategory('planning');
                if (typeof planningSettings.auto_archive_on_recalc === 'boolean') {
                    autoArchive = planningSettings.auto_archive_on_recalc;
                }
            } catch {
                autoArchive = true;
            }

            const payload = {
                from_version_id: currentVersionId,
                reason: rescheduleForm.reason,
                changes: {},
                frozen_before: rescheduleForm.frozen_before || null,
                comment: rescheduleForm.comment || null,
                replace_version_id: autoArchive ? currentVersionId : null,
            };
            const res = await rescheduleApi.reschedule(payload);
            setRescheduleResult(res);
            await loadVersions();
            if (res.to_version_id) {
                setPlan(
                    res.to_version_id,
                    `Перепланировано от ${new Date().toLocaleString('ru-RU')}`,
                    true,
                );
            }
        } catch (err: any) {
            const detail = err.response?.data?.detail;
            setError(typeof detail === 'string' ? detail : 'Ошибка перепланирования');
        } finally {
            setRescheduling(false);
        }
    };

    const versionsForTree = useMemo<PlanVersion[]>(() => {
        if (includeArchived) return versions;

        const byId = new Map(versions.map((v) => [v.id, v]));
        const toKeep = new Set<string>();

        const addWithParents = (v: PlanVersion) => {
            if (toKeep.has(v.id)) return;
            toKeep.add(v.id);
            if (v.parent_version_id && byId.has(v.parent_version_id)) {
                addWithParents(byId.get(v.parent_version_id)!);
            }
        };

        for (const v of versions) {
            if (!v.is_archived) addWithParents(v);
        }

        return versions.filter((v) => toKeep.has(v.id));
    }, [versions, includeArchived]);

    const treeData = useMemo(
        () => buildVersionTree(versionsForTree),
        [versionsForTree],
    );

    const visibleRows = useMemo(() => {
        return treeData.filter((node) => {
            if (node.depth === 0) return true;
            return expandedRoots.isExpanded(node.rootId);
        });
    }, [treeData, expandedRoots]);

    const renderNameCell = useCallback((params: any) => {
        const v = params.data as PlanVersionWithPath | undefined;
        if (!v) return null;

        const isRoot = v.depth === 0;
        const isExpanded = isRoot && expandedRoots.isExpanded(v.id);
        const isActive = v.is_active;
        const isArchived = v.is_archived;
        const hasSnapshot = v.has_snapshot !== false;

        return (
            <div
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    width: '100%',
                    height: '100%',
                    minWidth: 0,
                }}
            >
                <div
                    style={{
                        width: 28,
                        height: 28,
                        flexShrink: 0,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                    }}
                >
                    {isRoot && v.hasChildren && (
                        <IconButton
                            size="small"
                            onClick={(e) => {
                                e.stopPropagation();
                                expandedRoots.toggle(v.id);
                            }}
                            sx={{ p: 0.25 }}
                        >
                            {isExpanded
                                ? <ArrowDropDownIcon fontSize="small"/>
                                : <ArrowRightIcon fontSize="small"/>}
                        </IconButton>
                    )}
                </div>

                {!hasSnapshot && (
                    <WarningIcon
                        fontSize="small"
                        sx={{ color: '#e67e22', flexShrink: 0 }}
                    />
                )}

                <div
                    style={{
                        flex: '1 1 200px',
                        minWidth: '150px',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                        fontWeight: isActive ? 700 : 400,
                        color: isArchived ? '#95a5a6' : 'inherit',
                        fontSize: '0.875rem',
                    }}
                >
                    {v.name}
                </div>

                {isActive && (
                    <Chip
                        label="активный"
                        color="success"
                        size="small"
                        sx={{
                            height: 18,
                            fontSize: '0.65rem',
                            flexShrink: 0,
                        }}
                    />
                )}
            </div>
        );
    }, [expandedRoots]);

    const columnDefs: ColDef<PlanVersionWithPath>[] = useMemo(() => [
        {
            headerName: 'Наименование',
            field: 'name',
            flex: 2,
            minWidth: 400,
            cellRenderer: renderNameCell,
            sortable: false,
            filter: false,
            cellStyle: (params: any) => {
                const v = params.data as PlanVersionWithPath | undefined;
                if (!v) return undefined;
                return {
                    paddingLeft: 12 + v.depth * 24,
                };
            },
        },
        {
            headerName: 'Тип',
            field: 'version_type',
            width: 160,
            valueFormatter: (p) => VERSION_TYPE_LABELS[p.value] || p.value,
        },
        {
            headerName: 'Дата создания',
            field: 'created_at',
            width: 180,
            valueFormatter: (p) => p.value
                ? new Date(p.value).toLocaleString('ru-RU')
                : '—',
        },
        {
            headerName: 'Комментарий',
            field: 'comment',
            flex: 1,
            valueFormatter: (p) => p.value || '—',
        },
        {
            headerName: 'Действия',
            width: 260,
            editable: false,
            sortable: false,
            filter: false,
            cellRenderer: (params: any) => {
                const version = params.data as PlanVersionWithPath;
                const isCurrent = version.id === currentVersionId;
                const hasSnapshot = version.has_snapshot !== false;
                const isArchived = version.is_archived === true;

                return (
                    <Box sx={{ display: 'flex', gap: 0.5, alignItems: 'center' }}>
                        {isCurrent ? (
                            <Tooltip title="Закрыть план (вернуться в режим редактирования)">
                                <IconButton
                                    size="small"
                                    color="warning"
                                    onClick={handleClosePlan}
                                >
                                    <CloseIcon fontSize="small" />
                                </IconButton>
                            </Tooltip>
                        ) : (
                            <Tooltip title={
                                hasSnapshot
                                    ? "Открыть план (перейти на диаграмму Ганта)"
                                    : "Открыть план (нет снапшотов — справочники будут пусты)"
                            }>
                                <IconButton
                                    data-tour-id="open-gantt-button"
                                    size="small"
                                    color={hasSnapshot ? 'primary' : 'warning'}
                                    onClick={() => handleOpenPlan(version)}
                                >
                                    <ViewIcon fontSize="small" />
                                </IconButton>
                            </Tooltip>
                        )}
                        <Tooltip title="Открыть диаграмму Ганта (без смены активного плана)">
                            <IconButton
                                size="small"
                                onClick={() => navigate(`/gantt?version_id=${version.id}`)}
                            >
                                <TimelineIcon fontSize="small" />
                            </IconButton>
                        </Tooltip>
                        <Tooltip title="Мастер настроек плана">
                            <IconButton
                                size="small"
                                color="info"
                                onClick={() => handleOpenWizardEdit(version.id)}
                            >
                                <SettingsIcon fontSize="small" />
                            </IconButton>
                        </Tooltip>
                        {isArchived && (
                            <Tooltip title="Разархивировать (вернуть в список)">
                                <IconButton
                                    size="small"
                                    color="success"
                                    onClick={() => handleUnarchivePlan(version)}
                                >
                                    <UnarchiveIcon fontSize="small" />
                                </IconButton>
                            </Tooltip>
                        )}
                        <Tooltip title="Удалить план">
                            <IconButton
                                size="small"
                                color="error"
                                onClick={() => handleDeletePlan(version)}
                            >
                                <DeleteIcon fontSize="small" />
                            </IconButton>
                        </Tooltip>
                    </Box>
                );
            },
        },
    ], [currentVersionId, includeArchived, unarchiveVersion, renderNameCell, expandedRoots, navigate, setPlan, clearPlan, handleUnarchivePlan, handleDeletePlan, handleOpenPlan, handleOpenWizardEdit, handleClosePlan]);

    const renderAdvisorPanel = () => {
        return (
            <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column', m: 0.5 }}>
                <CardContent
                    data-tour-id="advisor-panel"
                    sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', minHeight: 0, p: 2 }}
                >
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.5, flexShrink: 0 }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <Typography variant="h6" sx={{ fontWeight: 600, fontSize: '1rem' }}>
                                Подсказки Advisor
                            </Typography>
                            {/* Итерация 15.2: подсказка про Advisor */}
                            <Hint id="planning.advisor" size="small"/>
                            {advisorData && advisorData.critical_count > 0 && (
                                <Chip label={`Критично: ${advisorData.critical_count}`} color="error" size="small" />
                            )}
                            {advisorData && advisorData.warning_count > 0 && (
                                <Chip label={`Внимание: ${advisorData.warning_count}`} color="warning" size="small" />
                            )}
                            {advisorData && advisorData.info_count > 0 && (
                                <Chip label={`Инфо: ${advisorData.info_count}`} color="info" size="small" variant="outlined" />
                            )}
                        </Box>
                        <Button
                            size="small"
                            startIcon={<RefreshIcon />}
                            onClick={loadAdvisor}
                            sx={{ textTransform: 'none' }}
                        >
                            Обновить
                        </Button>
                    </Box>

                    <Divider sx={{ mb: 1.5, flexShrink: 0 }} />

                    <Box sx={{ flexGrow: 1, overflow: 'auto', minHeight: 0 }}>
                        {advisorLoading && (
                            <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}>
                                <CircularProgress size={24} />
                            </Box>
                        )}

                        {!advisorLoading && advisorError && (
                            <Alert severity="error" onClose={() => setAdvisorError(null)}>
                                {advisorError}
                            </Alert>
                        )}

                        {!advisorLoading && !advisorError && (!advisorData || advisorData.tips.length === 0) && (
                            <Alert severity="success">
                                Подсказок нет. Все проверки пройдены.
                            </Alert>
                        )}

                        {!advisorLoading && !advisorError && advisorData && advisorData.tips.length > 0 && (
                            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                                {advisorData.tips.map((tip, index) => (
                                    <Accordion
                                        key={`${tip.code}-${index}`}
                                        sx={{
                                            boxShadow: 'none',
                                            border: '1px solid #e0e0e0',
                                            '&:before': { display: 'none' },
                                            '&.Mui-expanded': { margin: 0 },
                                        }}
                                    >
                                        <AccordionSummary
                                            expandIcon={<ExpandMoreIcon />}
                                            sx={{ minHeight: 40, '& .MuiAccordionSummary-content': { my: 0.5 } }}
                                        >
                                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, width: '100%' }}>
                                                <Chip
                                                    icon={SEVERITY_ICONS[tip.severity] as any}
                                                    label={SEVERITY_LABELS[tip.severity]}
                                                    color={SEVERITY_COLORS[tip.severity]}
                                                    size="small"
                                                />
                                                <Typography variant="body2" sx={{ fontWeight: 600, flexGrow: 1 }}>
                                                    {tip.title}
                                                </Typography>
                                            </Box>
                                        </AccordionSummary>
                                        <AccordionDetails sx={{ pt: 0 }}>
                                            <Typography variant="body2">{tip.message}</Typography>
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
        const expandedCount = treeData.filter(
            (n) => n.depth === 0 && expandedRoots.isExpanded(n.id)
        ).length;

        return (
            <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column', m: 0.5 }}>
                <CardContent
                    data-tour-id="plans-history"
                    sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', minHeight: 0, p: 2 }}
                >
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1, flexShrink: 0, flexWrap: 'wrap' }}>
                        <HistoryIcon color="primary" />
                        <Typography variant="h6" sx={{ fontWeight: 600, fontSize: '1rem' }}>
                            История планов ({visibleRows.length}/{treeData.length})
                        </Typography>
                        {/* Итерация 15.2: подсказка про planDirty */}
                        <Hint id="planning.plan_dirty" size="small"/>
                        {archivedCount > 0 && !includeArchived && (
                            <Chip
                                icon={<ArchiveIcon />}
                                label={`Архив: ${archivedCount}`}
                                size="small"
                                color="default"
                                variant="outlined"
                            />
                        )}

                        <Box sx={{ display: 'flex', gap: 0.5, ml: 1 }}>
                            <Tooltip title="Развернуть все корни">
                                <Button
                                    size="small"
                                    variant="text"
                                    startIcon={<ArrowDropDownIcon />}
                                    onClick={() => expandedRoots.expandAll(
                                        treeData.filter(n => n.depth === 0).map(n => n.id)
                                    )}
                                    disabled={expandedCount === totalRoots}
                                    sx={{ textTransform: 'none', fontSize: '0.75rem' }}
                                >
                                    Развернуть
                                </Button>
                            </Tooltip>

                            <Tooltip title="Свернуть все корни">
                                <Button
                                    size="small"
                                    variant="text"
                                    startIcon={<ArrowRightIcon />}
                                    onClick={() => expandedRoots.collapseAll(
                                        treeData.filter(n => n.depth === 0).map(n => n.id)
                                    )}
                                    disabled={expandedCount === 0}
                                    sx={{ textTransform: 'none', fontSize: '0.75rem' }}
                                >
                                    Свернуть
                                </Button>
                            </Tooltip>
                        </Box>

                        <FormControlLabel
                            control={
                                <Checkbox
                                    size="small"
                                    checked={includeArchived}
                                    onChange={(e) => setIncludeArchived(e.target.checked)}
                                />
                            }
                            label={
                                <Typography variant="caption">
                                    Показать архивные
                                </Typography>
                            }
                            sx={{ ml: 'auto' }}
                        />
                        {currentVersionId && (
                            <Chip
                                icon={<TimelineIcon />}
                                label="Один из планов открыт"
                                size="small"
                                color="info"
                                variant="outlined"
                            />
                        )}
                    </Box>
                    <Box sx={{ flexGrow: 1, width: '100%', minHeight: 0 }}>
                        <AppAgGrid
                            rowData={visibleRows}
                            columnDefs={columnDefs}
                            defaultColDef={{ sortable: true, filter: true, resizable: true }}
                            onGridReady={(params: GridReadyEvent) => params.api.sizeColumnsToFit()}
                            getRowId={(params: any) => params.data.id}
                            getRowStyle={(params: any): RowStyle | undefined => {
                                const v = params.data as PlanVersionWithPath | undefined;
                                if (!v) return undefined;

                                if (v.is_active) {
                                    return {
                                        backgroundColor: '#e3f2fd',
                                        boxShadow: 'inset 4px 0 0 0 #1976d2',
                                        color: '#0d47a1',
                                    } as RowStyle;
                                }

                                if (v.is_archived) {
                                    return {
                                        backgroundColor: '#f5f5f5',
                                        color: '#7f8c8d',
                                    } as RowStyle;
                                }

                                if (v.has_snapshot === false) {
                                    return {
                                        backgroundColor: '#fff8e1',
                                        color: '#7f6000',
                                    } as RowStyle;
                                }

                                return undefined;
                            }}
                        />
                    </Box>
                </CardContent>
            </Card>
        );
    };

    return (
        <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <Box
                sx={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    mb: 2,
                    flexShrink: 0,
                }}
            >
                <Typography variant="h4" component="h1" sx={{ fontWeight: 600, color: '#2c3e50' }}>
                    Планирование производства
                </Typography>
                <Box sx={{ display: 'flex', gap: 1 }}>
                    <Button
                        variant="outlined"
                        startIcon={<RescheduleIcon />}
                        onClick={handleOpenReschedule}
                        disabled={!currentVersionId}
                        sx={{ textTransform: 'none' }}
                    >
                        Перепланировать
                    </Button>
                    <Button
                        variant="outlined"
                        startIcon={<AddIcon />}
                        onClick={handleOpenWizardCreate}
                        sx={{ textTransform: 'none' }}
                    >
                        Новый план
                    </Button>
                </Box>
            </Box>

            {error && (
                <Alert severity="error" sx={{ mb: 2, flexShrink: 0 }} onClose={() => setError(null)}>
                    {error}
                </Alert>
            )}

            {success && (
                <Alert severity="success" sx={{ mb: 2, flexShrink: 0 }} onClose={() => setSuccess(null)}>
                    {success}
                </Alert>
            )}

            <Card sx={{ mb: 2, flexShrink: 0 }}>
                <CardContent sx={{ py: 2, '&:last-child': { pb: 2 } }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                        <Typography variant="h6" sx={{ fontWeight: 600, fontSize: '1rem' }}>
                            Параметры расчёта
                        </Typography>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            {settingsLoaded && (
                                <Chip label="Из настроек" size="small" color="info" variant="outlined" />
                            )}
                            <Button
                                size="small"
                                variant="outlined"
                                startIcon={<SaveIcon />}
                                onClick={handleSaveSettings}
                                disabled={settingsSaving}
                                sx={{ textTransform: 'none' }}
                            >
                                {settingsSaving ? 'Сохранение...' : 'Сохранить настройки'}
                            </Button>
                        </Box>
                    </Box>
                    <Box sx={{ display: 'flex', gap: 2, mb: 1.5, flexWrap: 'wrap', alignItems: 'center' }}>
                        <TextField
                            label="Горизонт (часы)"
                            type="number"
                            value={horizonHours}
                            onChange={(e) => setHorizonHours(Number(e.target.value))}
                            size="small"
                            sx={{ width: 160 }}
                            helperText="Сохраняется в app_settings"
                        />
                        <TextField
                            label="Таймаут solver (сек)"
                            type="number"
                            value={solverTimeout}
                            onChange={(e) => setSolverTimeout(Number(e.target.value))}
                            size="small"
                            sx={{ width: 180 }}
                            helperText="Сохраняется в app_settings"
                        />
                        <Button
                            data-tour-id="build-plan-button"
                            variant="contained"
                            startIcon={loading ? <CircularProgress size={20} /> : <PlayIcon />}
                            onClick={handleBuildSchedule}
                            disabled={loading}
                            sx={{ textTransform: 'none' }}
                        >
                            {loading ? 'Расчёт...' : 'Построить план'}
                        </Button>
                        {/* Итерация 15.2: подсказка про пересчёт */}
                        <Hint id="planning.recalc" size="medium"/>
                    </Box>
                    <Typography variant="caption" color="text.secondary">
                        💡 Параметры автоматически сохраняются в app_settings при построении плана
                    </Typography>
                    {result && (
                        <Alert severity="success" sx={{ mt: 1 }}>
                            Расчёт завершён: {result.total_tasks} задач, Makespan: {result.makespan_hours.toFixed(1)} ч
                        </Alert>
                    )}
                </CardContent>
            </Card>

            <Box sx={{ flexGrow: 1, minHeight: 0, mx: -0.5 }}>
                <Allotment vertical defaultSizes={[30, 70]}>
                    <Allotment.Pane minSize={180} preferredSize="30%">
                        {renderAdvisorPanel()}
                    </Allotment.Pane>
                    <Allotment.Pane minSize={200}>
                        {renderPlansGrid()}
                    </Allotment.Pane>
                </Allotment>
            </Box>

            <PlanSettingsWizard
                open={wizardOpen}
                onClose={() => setWizardOpen(false)}
                mode={wizardMode}
                versionId={wizardVersionId}
                onSaved={handleWizardSaved}
            />

            <DraggableDialog
                open={rescheduleDialogOpen}
                onClose={() => setRescheduleDialogOpen(false)}
                title="Перепланирование"
                initialWidth={640}
                initialHeight="auto"
                minWidth={480}
                minHeight={320}
                actions={
                    <>
                        <Button onClick={() => setRescheduleDialogOpen(false)}>
                            {rescheduleResult ? 'Закрыть' : 'Отмена'}
                        </Button>
                        {!rescheduleResult && (
                            <Button
                                onClick={handleDoReschedule}
                                variant="contained"
                                disabled={rescheduling}
                                startIcon={rescheduling ? <CircularProgress size={20} /> : <RescheduleIcon />}
                            >
                                {rescheduling ? 'Перепланирование...' : 'Перепланировать'}
                            </Button>
                        )}
                    </>
                }
            >
                {!rescheduleResult ? (
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                        <Alert severity="info">
                            Перепланирование создаст новую версию плана. Задачи до <b>frozen_before</b> и
                            задачи с флагом <b>is_pinned</b> не будут двигаться.
                        </Alert>
                        <FormControl fullWidth variant="outlined">
                            <InputLabel>Причина перепланирования</InputLabel>
                            <Select
                                value={rescheduleForm.reason}
                                label="Причина перепланирования"
                                variant="outlined"
                                onChange={(e) =>
                                    setRescheduleForm({ ...rescheduleForm, reason: e.target.value as RescheduleReason })
                                }
                            >
                                <MenuItem value="DELAY">Задержка операции</MenuItem>
                                <MenuItem value="BREAKDOWN">Поломка оборудования</MenuItem>
                                <MenuItem value="QTY_CHANGE">Изменение объёма</MenuItem>
                                <MenuItem value="MANUAL">Ручное изменение</MenuItem>
                            </Select>
                        </FormControl>
                        <TextField
                            label="Заморозить до (frozen_before)"
                            type="datetime-local"
                            fullWidth
                            value={rescheduleForm.frozen_before}
                            onChange={(e) =>
                                setRescheduleForm({ ...rescheduleForm, frozen_before: e.target.value })
                            }
                            slotProps={{ inputLabel: { shrink: true } }}
                            helperText="Задачи, начавшиеся до этого момента, не будут двигаться"
                        />
                        <TextField
                            label="Комментарий"
                            fullWidth
                            multiline
                            rows={2}
                            value={rescheduleForm.comment}
                            onChange={(e) =>
                                setRescheduleForm({ ...rescheduleForm, comment: e.target.value })
                            }
                        />
                    </Box>
                ) : (
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                        <Alert severity="success">{rescheduleResult.message}</Alert>

                        {rescheduleResult.replace_blocked && (
                            <Alert severity="warning">
                                <Typography variant="body2" sx={{ fontWeight: 600, mb: 0.5 }}>
                                    Старая версия не была архивирована
                                </Typography>
                                <Typography variant="body2">
                                    {rescheduleResult.replace_blocked_reason
                                        || 'Версия используется в what-if сценариях.'}
                                </Typography>
                                {rescheduleResult.used_by_whatif.length > 0 && (
                                    <Typography variant="caption" sx={{ display: 'block', mt: 0.5 }}>
                                        Сценарии: {rescheduleResult.used_by_whatif.join(', ')}
                                    </Typography>
                                )}
                            </Alert>
                        )}

                        {rescheduleResult.replace_archived && (
                            <Alert severity="info" icon={<ArchiveIcon />}>
                                <Typography variant="body2">
                                    Старая версия перемещена в архив.
                                    Разархивировать можно через чекбокс «Показать архивные».
                                </Typography>
                            </Alert>
                        )}

                        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                            <Chip
                                label={`Затронуто задач: ${rescheduleResult.affected_tasks}`}
                                color="warning"
                            />
                            <Chip
                                label={`Перенесено: ${rescheduleResult.moved_tasks}`}
                                color="primary"
                            />
                            <Chip
                                label={`Заморожено: ${rescheduleResult.frozen_tasks}`}
                                variant="outlined"
                            />
                        </Box>
                        <Typography variant="caption" color="text.secondary">
                            Новая версия: {rescheduleResult.to_version_id}
                        </Typography>
                    </Box>
                )}
            </DraggableDialog>
        </Box>
    );
};

export default SchedulePage;