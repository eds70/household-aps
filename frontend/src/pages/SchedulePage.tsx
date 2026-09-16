// src/pages/SchedulePage.tsx
import React, {useEffect, useState} from 'react';
import {type PlanVersion, usePlan} from '../context/PlainContext';
import {AgGridReact} from 'ag-grid-react';
import type {ColDef, GridReadyEvent} from 'ag-grid-community';
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
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
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
    Delete as DeleteIcon,
    Error as ErrorIcon,
    ExpandMore as ExpandMoreIcon,
    History as HistoryIcon,
    Info as InfoIcon,
    PlayArrow as PlayIcon,
    Refresh as RefreshIcon,
    Visibility as ViewIcon,
    Warning as WarningIcon,
} from '@mui/icons-material';
import {Allotment} from 'allotment';
import 'allotment/dist/style.css';
import {advisorApi, rescheduleApi, scheduleApi} from '../services/api';
import type {AdvisorResponse, AdvisorSeverity, RescheduleReason, RescheduleResponse,} from '../types';

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

const SchedulePage: React.FC = () => {
    const { versions, setPlan, loadVersions, currentVersionId } = usePlan();

    const [horizonHours, setHorizonHours] = useState(2160);
    const [solverTimeout, setSolverTimeout] = useState(120);
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState<any>(null);
    const [error, setError] = useState<string | null>(null);

    // Advisor
    const [advisorData, setAdvisorData] = useState<AdvisorResponse | null>(null);
    const [advisorLoading, setAdvisorLoading] = useState(false);
    const [advisorError, setAdvisorError] = useState<string | null>(null);

    // Новый план
    const [newPlanDialogOpen, setNewPlanDialogOpen] = useState(false);
    const [newPlanForm, setNewPlanForm] = useState({
        name: '',
        version_type: 'MONTHLY',
        comment: '',
    });
    const [creatingPlan, setCreatingPlan] = useState(false);

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

    useEffect(() => {
        loadVersions();
    }, []);

    const loadAdvisor = async () => {
        setAdvisorLoading(true);
        setAdvisorError(null);
        try {
            const data = await advisorApi.getAdvice();
            setAdvisorData(data);
        } catch (err: any) {
            const detail = err.response?.data?.detail;
            const errorMsg = typeof detail === 'string' ? detail : 'Ошибка загрузки подсказок';
            setAdvisorError(errorMsg);
        } finally {
            setAdvisorLoading(false);
        }
    };

    useEffect(() => {
        loadAdvisor();
    }, []);

    const handleBuildSchedule = async () => {
        setLoading(true);
        setError(null);
        setResult(null);
        try {
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

    const handleCreatePlan = async () => {
        if (!newPlanForm.name.trim()) {
            setError('Введите название плана');
            return;
        }
        setCreatingPlan(true);
        setError(null);
        try {
            const newVersion = await scheduleApi.createVersion(newPlanForm);
            setPlan(newVersion.id, newVersion.name);
            setNewPlanDialogOpen(false);
            setNewPlanForm({ name: '', version_type: 'MONTHLY', comment: '' });
            await loadVersions();
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Ошибка создания плана');
        } finally {
            setCreatingPlan(false);
        }
    };

    const handleDeletePlan = async (version: PlanVersion) => {
        if (!window.confirm(`Удалить план "${version.name}"?`)) return;
        try {
            await scheduleApi.deleteVersion(version.id);
            if (currentVersionId === version.id) {
                setPlan(null, "Режим редактирования");
            }
            await loadVersions();
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Ошибка удаления плана');
        }
    };

    const handleOpenPlan = (version: PlanVersion) => {
        setPlan(version.id, version.name);
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
                setPlan(res.to_version_id, `Перепланировано от ${new Date().toLocaleString('ru-RU')}`);
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
            width: 140,
            editable: false,
            cellRenderer: (params: any) => {
                const version = params.data as PlanVersion;
                const isCurrent = version.id === currentVersionId;
                return (
                    <Box sx={{ display: 'flex', gap: 0.5 }}>
                        <Tooltip title={isCurrent ? 'Текущий план' : 'Открыть план'}>
                            <span>
                                <IconButton
                                    size="small"
                                    color={isCurrent ? 'success' : 'primary'}
                                    onClick={() => handleOpenPlan(version)}
                                    disabled={isCurrent}
                                >
                                    <ViewIcon fontSize="small" />
                                </IconButton>
                            </span>
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

    // ==========================================
    // Advisor Panel
    // ==========================================
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

    // ==========================================
    // AgGrid Panel
    // ==========================================
    const renderPlansGrid = () => {
        return (
            <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column', m: 0.5 }}>
                <CardContent sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', minHeight: 0, p: 2 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1, flexShrink: 0 }}>
                        <HistoryIcon color="primary" />
                        <Typography variant="h6" sx={{ fontWeight: 600, fontSize: '1rem' }}>
                            История планов ({versions.length})
                        </Typography>
                    </Box>
                    <Box className="ag-theme-alpine" sx={{ flexGrow: 1, width: '100%', minHeight: 0 }}>
                        <AgGridReact
                            rowData={versions}
                            columnDefs={columnDefs}
                            defaultColDef={{ sortable: true, filter: true, resizable: true }}
                            onGridReady={(params: GridReadyEvent) => params.api.sizeColumnsToFit()}
                            getRowStyle={(params: any) =>
                                params.data?.id === currentVersionId
                                    ? { backgroundColor: '#e3f2fd', fontWeight: 'bold' }
                                    : undefined
                            }
                        />
                    </Box>
                </CardContent>
            </Card>
        );
    };

    // ==========================================
    // Основной рендер
    // ==========================================
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
                        onClick={() => setNewPlanDialogOpen(true)}
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
                    <Typography variant="h6" gutterBottom sx={{ fontWeight: 600, fontSize: '1rem' }}>
                        Параметры расчёта
                    </Typography>
                    <Box sx={{ display: 'flex', gap: 2, mb: 1.5, flexWrap: 'wrap', alignItems: 'center' }}>
                        <TextField
                            label="Горизонт (часы)"
                            type="number"
                            value={horizonHours}
                            onChange={(e) => setHorizonHours(Number(e.target.value))}
                            size="small"
                            sx={{ width: 160 }}
                        />
                        <TextField
                            label="Таймаут solver (сек)"
                            type="number"
                            value={solverTimeout}
                            onChange={(e) => setSolverTimeout(Number(e.target.value))}
                            size="small"
                            sx={{ width: 180 }}
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

            {/* ---------- Диалог нового плана ---------- */}
            <Dialog open={newPlanDialogOpen} onClose={() => setNewPlanDialogOpen(false)} maxWidth="sm" fullWidth>
                <DialogTitle sx={{ fontWeight: 600 }}>Создать новый план</DialogTitle>
                <DialogContent>
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
                        <TextField
                            label="Название плана"
                            fullWidth
                            value={newPlanForm.name}
                            onChange={(e) => setNewPlanForm({ ...newPlanForm, name: e.target.value })}
                        />
                        <FormControl fullWidth>
                            <InputLabel>Тип плана</InputLabel>
                            <Select
                                value={newPlanForm.version_type}
                                label="Тип плана"
                                onChange={(e) => setNewPlanForm({ ...newPlanForm, version_type: e.target.value })}
                            >
                                <MenuItem value="MONTHLY">Месячный (ОКП)</MenuItem>
                                <MenuItem value="SHIFT">Посменный</MenuItem>
                                <MenuItem value="WHAT_IF">Сценарий "что если"</MenuItem>
                            </Select>
                        </FormControl>
                        <TextField
                            label="Комментарий"
                            fullWidth
                            multiline
                            rows={3}
                            value={newPlanForm.comment}
                            onChange={(e) => setNewPlanForm({ ...newPlanForm, comment: e.target.value })}
                        />
                    </Box>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setNewPlanDialogOpen(false)}>Отмена</Button>
                    <Button
                        onClick={handleCreatePlan}
                        variant="contained"
                        disabled={creatingPlan || !newPlanForm.name.trim()}
                    >
                        {creatingPlan ? 'Создание...' : 'Создать'}
                    </Button>
                </DialogActions>
            </Dialog>

            {/* ---------- Диалог перепланирования ---------- */}
            <Dialog
                open={rescheduleDialogOpen}
                onClose={() => setRescheduleDialogOpen(false)}
                maxWidth="sm"
                fullWidth
            >
                <DialogTitle sx={{ fontWeight: 600 }}>Перепланирование</DialogTitle>
                <DialogContent>
                    {!rescheduleResult ? (
                        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
                            <Alert severity="info">
                                Перепланирование создаст новую версию плана. Задачи до <b>frozen_before</b> и
                                задачи с флагом <b>is_pinned</b> не будут двигаться.
                            </Alert>
                            <FormControl fullWidth>
                                <InputLabel>Причина перепланирования</InputLabel>
                                <Select
                                    value={rescheduleForm.reason}
                                    label="Причина перепланирования"
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
                        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
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
                </DialogContent>
                <DialogActions>
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
                </DialogActions>
            </Dialog>
        </Box>
    );
};

export default SchedulePage;