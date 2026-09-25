// frontend/src/pages/SchedulePage.tsx
import React, {useCallback, useEffect, useState} from 'react';
import {useNavigate} from 'react-router-dom';
import {type PlanVersion, usePlan} from '../context/PlainContext';
import {AgGridReact} from 'ag-grid-react';
import type {ColDef, GridReadyEvent, RowStyle} from 'ag-grid-community';
import {AllCommunityModule, ModuleRegistry} from 'ag-grid-community';
import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-alpine.css';
import {
    Accordion,
    AccordionDetails,
    AccordionSummary,
    Alert,
    Box,
    Button,
    Card,
    CardContent,
    Chip,
    CircularProgress,
    Divider,
    FormControl,
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
    Visibility as ViewIcon,
    Warning as WarningIcon,
} from '@mui/icons-material';
import {Allotment} from 'allotment';
import 'allotment/dist/style.css';
import {advisorApi, rescheduleApi, scheduleApi, settingsApi} from '../services/api';
import type {AdvisorResponse, AdvisorSeverity, RescheduleReason, RescheduleResponse,} from '../types';
import PlanSettingsWizard, {type WizardMode} from './PlanSettingsWizard';
import DraggableDialog from '../components/common/DraggableDialog';

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

const SchedulePage: React.FC = () => {
    const { versions, setPlan, clearPlan, loadVersions, currentVersionId } = usePlan();
    const navigate = useNavigate();

    // Параметры расчёта — читаются из app_settings
    const [horizonHours, setHorizonHours] = useState<number>(DEFAULT_HORIZON_HOURS);
    const [solverTimeout, setSolverTimeout] = useState<number>(DEFAULT_TIMEOUT_SECONDS);
    const [settingsLoaded, setSettingsLoaded] = useState(false);
    const [settingsSaving, setSettingsSaving] = useState(false);

    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState<any>(null);
    const [error, setError] = useState<string | null>(null);

    // Advisor
    const [advisorData, setAdvisorData] = useState<AdvisorResponse | null>(null);
    const [advisorLoading, setAdvisorLoading] = useState(false);
    const [advisorError, setAdvisorError] = useState<string | null>(null);

    // Мастер настроек плана
    const [wizardOpen, setWizardOpen] = useState(false);
    const [wizardMode, setWizardMode] = useState<WizardMode>('edit');
    const [wizardVersionId, setWizardVersionId] = useState<string | null>(null);

    // Перепланирование
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

    // ==========================================
    // Загрузка настроек планирования из app_settings
    // ==========================================
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

    // ==========================================
    // Сохранение настроек в app_settings
    // ==========================================
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

    // ---------- Перепланирование ----------
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
            const payload = {
                from_version_id: currentVersionId,
                reason: rescheduleForm.reason,
                changes: {},
                frozen_before: rescheduleForm.frozen_before || null,
                comment: rescheduleForm.comment || null,
            };
            const res = await rescheduleApi.reschedule(payload);
            setRescheduleResult(res);
            await loadVersions();
            if (res.to_version_id) {
                setPlan(res.to_version_id, `Перепланировано от ${new Date().toLocaleString('ru-RU')}`, true);
            }
        } catch (err: any) {
            const detail = err.response?.data?.detail;
            setError(typeof detail === 'string' ? detail : 'Ошибка перепланирования');
        } finally {
            setRescheduling(false);
        }
    };

    const columnDefs: ColDef[] = [
        { headerName: 'Наименование', field: 'name', flex: 2 },
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
            valueFormatter: (p) => p.value ? new Date(p.value).toLocaleString('ru-RU') : '—',
        },
        {
            headerName: 'Комментарий',
            field: 'comment',
            flex: 1,
            valueFormatter: (p) => p.value || '—',
        },
        {
            headerName: 'Действия',
            width: 240,
            editable: false,
            cellRenderer: (params: any) => {
                const version = params.data as PlanVersion;
                const isCurrent = version.id === currentVersionId;
                const hasSnapshot = version.has_snapshot !== false;

                return (
                    <Box sx={{ display: 'flex', gap: 0.5, alignItems: 'center' }}>
                        {!hasSnapshot && (
                            <Tooltip title="План создан до Итерации 13.15, снапшоты пусты. Пересоздайте план или пересчитайте.">
                                <WarningIcon
                                    fontSize="small"
                                    sx={{ color: '#e67e22' }}
                                />
                            </Tooltip>
                        )}
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
    ];

    const renderAdvisorPanel = () => {
        return (
            <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column', m: 0.5 }}>
                <CardContent sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', minHeight: 0, p: 2 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.5, flexShrink: 0 }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <Typography variant="h6" sx={{ fontWeight: 600, fontSize: '1rem' }}>
                                Подсказки Advisor
                            </Typography>
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
        return (
            <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column', m: 0.5 }}>
                <CardContent sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', minHeight: 0, p: 2 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1, flexShrink: 0 }}>
                        <HistoryIcon color="primary" />
                        <Typography variant="h6" sx={{ fontWeight: 600, fontSize: '1rem' }}>
                            История планов ({versions.length})
                        </Typography>
                        {currentVersionId && (
                            <Chip
                                icon={<TimelineIcon />}
                                label="Один из планов открыт"
                                size="small"
                                color="info"
                                variant="outlined"
                                sx={{ ml: 'auto' }}
                            />
                        )}
                    </Box>
                    <Box className="ag-theme-alpine" sx={{ flexGrow: 1, width: '100%', minHeight: 0 }}>
                        <AgGridReact
                            rowData={versions}
                            columnDefs={columnDefs}
                            defaultColDef={{ sortable: true, filter: true, resizable: true }}
                            onGridReady={(params: GridReadyEvent) => params.api.sizeColumnsToFit()}
                            getRowStyle={(params: any): RowStyle | undefined => {
                                const isCurrent = params.data?.id === currentVersionId;
                                const isActive = params.data?.is_active;
                                const hasSnapshot = params.data?.has_snapshot !== false;
                                if (isCurrent) {
                                    return {
                                        backgroundColor: '#e3f2fd',
                                        fontWeight: 'bold',
                                        borderLeft: '4px solid #1976d2',
                                        color: '#0d47a1',
                                    } as RowStyle;
                                }
                                if (isActive) {
                                    return {
                                        backgroundColor: '#f1f8e9',
                                        color: '#33691e',
                                    } as RowStyle;
                                }
                                if (!hasSnapshot) {
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
            {/* Заголовок */}
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

            {/* Параметры расчёта */}
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
                            variant="contained"
                            startIcon={loading ? <CircularProgress size={20} /> : <PlayIcon />}
                            onClick={handleBuildSchedule}
                            disabled={loading}
                            sx={{ textTransform: 'none' }}
                        >
                            {loading ? 'Расчёт...' : 'Построить план'}
                        </Button>
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

            {/* Allotment: Advisor сверху, планы снизу */}
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

            {/* Мастер настроек плана */}
            <PlanSettingsWizard
                open={wizardOpen}
                onClose={() => setWizardOpen(false)}
                mode={wizardMode}
                versionId={wizardVersionId}
                onSaved={handleWizardSaved}
            />

            {/* ---------- Диалог перепланирования (DraggableDialog) ---------- */}
            <DraggableDialog
                open={rescheduleDialogOpen}
                onClose={() => setRescheduleDialogOpen(false)}
                title="Перепланирование"
                initialWidth={600}
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