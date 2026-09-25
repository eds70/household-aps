// frontend/src/pages/WhatIfPage.tsx
import React, {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {
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
    Paper,
    Select,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    TextField,
    Tooltip,
    Typography,
} from '@mui/material';
import {
    Add as AddIcon,
    CheckCircle as CheckCircleIcon,
    Delete as DeleteIcon,
    Edit as EditIcon,
    Info as InfoIcon,
    PlayArrow as PlayIcon,
    Refresh as RefreshIcon,
    Save as SaveIcon,
    Science as ScienceIcon,
    Visibility as VisibilityIcon,
} from '@mui/icons-material';
import {AgGridReact} from 'ag-grid-react';
import type {ColDef, GridReadyEvent} from 'ag-grid-community';
import {AllCommunityModule, ModuleRegistry} from 'ag-grid-community';
import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-alpine.css';
import {usePlan} from '../context/PlainContext';
import {whatifApi} from '../services/api';
import type {
    WhatIfChanges,
    WhatIfCompareResponse,
    WhatIfScenario,
    WhatIfScenarioListItem,
    WhatIfStatus,
} from '../types';
import DraggableDialog from '../components/common/DraggableDialog';

ModuleRegistry.registerModules([AllCommunityModule]);

// ==========================================
// КОНСТАНТЫ
// ==========================================

const STATUS_LABELS: Record<WhatIfStatus, string> = {
    DRAFT: 'Черновик',
    RUNNING: 'Расчёт...',
    DONE: 'Готово',
    FAILED: 'Ошибка',
};

const STATUS_COLORS: Record<WhatIfStatus, 'default' | 'warning' | 'info' | 'success' | 'error'> = {
    DRAFT: 'default',
    RUNNING: 'info',
    DONE: 'success',
    FAILED: 'error',
};

const POLLING_INTERVAL_MS = 3000;
const POLLING_MAX_ATTEMPTS = 120;

// ==========================================
// JSON-ШАБЛОНЫ
// ==========================================

const JSON_TEMPLATE_EMPTY: WhatIfChanges = {};

const JSON_TEMPLATE_SHIFT_MODE: WhatIfChanges = {
    shift_mode: '3x8',
};

const JSON_TEMPLATE_ADD_ORDER: WhatIfChanges = {
    orders: [
        {
            action: 'add_order',
            product_code: 'GP_CREAM_1L',
            target_qty: 25000,
            due_date: '2026-10-15T23:59:59+03:00',
            priority: 5,
        },
    ],
};

const JSON_TEMPLATE_CAPACITY: WhatIfChanges = {
    resource_capacity: {
        REACTOR_OPERATOR: 4,
        LINE_OPERATOR: 3,
    },
};

const JSON_TEMPLATE_BREAKDOWN: WhatIfChanges = {
    calendar_events: [
        {
            action: 'add',
            event_type: 'BREAKDOWN',
            equipment_code: 'REACTOR_4',
            starts_at: '2026-09-25T00:00:00+03:00',
            ends_at: '2026-09-29T00:00:00+03:00',
            comment: 'Аварийная остановка Р4',
        },
    ],
};

const JSON_TEMPLATE_FULL: WhatIfChanges = {
    shift_mode: '3x8',
    orders: [
        {
            action: 'change_qty',
            order_id: '<ORDER_UUID>',
            new_qty: 30000,
        },
    ],
    resource_capacity: {
        REACTOR_OPERATOR: 4,
    },
};

// ==========================================
// КОМПОНЕНТ
// ==========================================

const WhatIfPage: React.FC = () => {
    const {currentVersionId, versions} = usePlan();

    const [scenarios, setScenarios] = useState<WhatIfScenarioListItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const [dialogOpen, setDialogOpen] = useState(false);
    const [editingScenario, setEditingScenario] = useState<WhatIfScenario | null>(null);
    const [formName, setFormName] = useState('');
    const [formBaseVersionId, setFormBaseVersionId] = useState<string>('');
    const [formComment, setFormComment] = useState('');
    const [formChangesJson, setFormChangesJson] = useState('{}');
    const [formJsonError, setFormJsonError] = useState<string | null>(null);
    const [saving, setSaving] = useState(false);

    const [runningScenarioId, setRunningScenarioId] = useState<string | null>(null);
    const [runResult, setRunResult] = useState<WhatIfCompareResponse | null>(null);
    const [resultDialogOpen, setResultDialogOpen] = useState(false);
    const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const pollingAttemptsRef = useRef<number>(0);

    // ==========================================
    // ЗАГРУЗКА СПИСКА
    // ==========================================
    const loadScenarios = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const data = await whatifApi.listScenarios();
            setScenarios(data);
        } catch (err: any) {
            const detail = err.response?.data?.detail;
            setError(typeof detail === 'string' ? detail : 'Ошибка загрузки сценариев');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        loadScenarios();
    }, [loadScenarios]);

    useEffect(() => {
        return () => {
            if (pollingRef.current) {
                clearInterval(pollingRef.current);
                pollingRef.current = null;
            }
        };
    }, []);

    // ==========================================
    // СОЗДАНИЕ / РЕДАКТИРОВАНИЕ
    // ==========================================
    const handleOpenCreate = () => {
        setEditingScenario(null);
        setFormName('');
        setFormBaseVersionId(currentVersionId || '');
        setFormComment('');
        setFormChangesJson(JSON.stringify(JSON_TEMPLATE_EMPTY, null, 2));
        setFormJsonError(null);
        setDialogOpen(true);
    };

    const handleOpenEdit = async (scenarioId: string) => {
        try {
            const scenario = await whatifApi.getScenario(scenarioId);
            setEditingScenario(scenario);
            setFormName(scenario.name);
            setFormBaseVersionId(scenario.base_version_id);
            setFormComment(scenario.comment || '');
            setFormChangesJson(JSON.stringify(scenario.changes, null, 2));
            setFormJsonError(null);
            setDialogOpen(true);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Ошибка загрузки сценария');
        }
    };

    const handleApplyTemplate = (template: WhatIfChanges) => {
        setFormChangesJson(JSON.stringify(template, null, 2));
        setFormJsonError(null);
    };

    const validateJson = (): any | null => {
        try {
            const parsed = JSON.parse(formChangesJson);
            setFormJsonError(null);
            return parsed;
        } catch (e: any) {
            setFormJsonError(`Невалидный JSON: ${e.message}`);
            return null;
        }
    };

    const handleSave = async () => {
        if (!formName.trim()) {
            setError('Введите название');
            return;
        }
        if (!formBaseVersionId) {
            setError('Выберите базовый план');
            return;
        }

        const changes = validateJson();
        if (changes === null) return;

        setSaving(true);
        setError(null);
        try {
            if (editingScenario) {
                await whatifApi.updateScenario(editingScenario.id, {
                    name: formName,
                    comment: formComment || null,
                    changes,
                });
            } else {
                await whatifApi.createScenario({
                    name: formName,
                    base_version_id: formBaseVersionId,
                    comment: formComment || null,
                    changes,
                });
            }
            setDialogOpen(false);
            await loadScenarios();
        } catch (err: any) {
            const detail = err.response?.data?.detail;
            setError(typeof detail === 'string' ? detail : 'Ошибка сохранения');
        } finally {
            setSaving(false);
        }
    };

    // ==========================================
    // УДАЛЕНИЕ
    // ==========================================
    const handleDelete = async (scenarioId: string) => {
        const scenario = scenarios.find((s) => s.id === scenarioId);
        const hasResult = !!scenario?.result_version_id;

        const message = hasResult
            ? 'Удалить сценарий?\n\n' +
            '⚠️ Результат расчёта (план) останется в истории планов.\n' +
            'Удаляется только сценарий и его настройки.'
            : 'Удалить сценарий? Это действие необратимо.';

        if (!window.confirm(message)) return;

        try {
            await whatifApi.deleteScenario(scenarioId);
            await loadScenarios();
        } catch (err: any) {
            const detail = err.response?.data?.detail;
            setError(typeof detail === 'string' ? detail : 'Ошибка удаления');
        }
    };

    // ==========================================
    // ЗАПУСК + POLLING
    // ==========================================
    const stopPolling = () => {
        if (pollingRef.current) {
            clearInterval(pollingRef.current);
            pollingRef.current = null;
        }
        pollingAttemptsRef.current = 0;
    };

    const handleRun = async (scenarioId: string) => {
        setError(null);
        setRunningScenarioId(scenarioId);
        stopPolling();

        try {
            await whatifApi.runScenario(scenarioId);
            pollingAttemptsRef.current = 0;
            pollingRef.current = setInterval(async () => {
                pollingAttemptsRef.current += 1;
                if (pollingAttemptsRef.current > POLLING_MAX_ATTEMPTS) {
                    stopPolling();
                    setRunningScenarioId(null);
                    setError('Превышено время ожидания расчёта');
                    return;
                }

                try {
                    const scenario = await whatifApi.getScenario(scenarioId);
                    if (scenario.status === 'DONE') {
                        stopPolling();
                        setRunningScenarioId(null);
                        await loadScenarios();
                        const compare = await whatifApi.compareScenario(scenarioId);
                        setRunResult(compare);
                        setResultDialogOpen(true);
                    } else if (scenario.status === 'FAILED') {
                        stopPolling();
                        setRunningScenarioId(null);
                        await loadScenarios();
                        setError('Расчёт не удался. См. детали в комментарии сценария.');
                    }
                } catch (err) {
                    console.warn('[whatif] polling error:', err);
                }
            }, POLLING_INTERVAL_MS);
        } catch (err: any) {
            setRunningScenarioId(null);
            const detail = err.response?.data?.detail;
            setError(typeof detail === 'string' ? detail : 'Ошибка запуска');
        }
    };

    const handleOpenResult = async (scenarioId: string) => {
        try {
            const compare = await whatifApi.compareScenario(scenarioId);
            setRunResult(compare);
            setResultDialogOpen(true);
        } catch (err: any) {
            const detail = err.response?.data?.detail;
            setError(typeof detail === 'string' ? detail : 'Ошибка загрузки сравнения');
        }
    };

    // ==========================================
    // AGGrid COLUMNS
    // ==========================================
    const columnDefs = useMemo<ColDef<WhatIfScenarioListItem>[]>(() => [
        {
            headerName: 'Название',
            field: 'name',
            flex: 2,
            minWidth: 200,
        },
        {
            headerName: 'Статус',
            field: 'status',
            width: 130,
            cellRenderer: (params: any) => {
                const status = params.value as WhatIfStatus;
                return (
                    <Chip
                        label={STATUS_LABELS[status] || status}
                        color={STATUS_COLORS[status] || 'default'}
                        size="small"
                    />
                );
            },
        },
        {
            headerName: 'Базовый план',
            field: 'base_version_id',
            width: 130,
            valueFormatter: (p) => p.value ? String(p.value).substring(0, 8) : '—',
        },
        {
            headerName: 'Результат',
            field: 'result_version_id',
            width: 130,
            valueFormatter: (p) => p.value ? String(p.value).substring(0, 8) : '—',
        },
        {
            headerName: 'Создан',
            field: 'created_at',
            width: 170,
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
            cellRenderer: (params: any) => {
                const scenario = params.data as WhatIfScenarioListItem;
                const isRunning = runningScenarioId === scenario.id;
                const isDraft = scenario.status === 'DRAFT';
                const isDone = scenario.status === 'DONE';
                const isFailed = scenario.status === 'FAILED';
                const hasResult = !!scenario.result_version_id;

                return (
                    <Box sx={{display: 'flex', gap: 0.5, alignItems: 'center'}}>
                        {isDraft && (
                            <Tooltip title="Запустить расчёт">
                                <span>
                                    <IconButton
                                        size="small"
                                        color="primary"
                                        onClick={() => handleRun(scenario.id)}
                                        disabled={isRunning}
                                    >
                                        <PlayIcon fontSize="small"/>
                                    </IconButton>
                                </span>
                            </Tooltip>
                        )}
                        {isRunning && (
                            <Tooltip title="Расчёт идёт...">
                                <CircularProgress size={20}/>
                            </Tooltip>
                        )}
                        {isDone && (
                            <Tooltip title="Открыть сравнение">
                                <IconButton
                                    size="small"
                                    color="success"
                                    onClick={() => handleOpenResult(scenario.id)}
                                >
                                    <VisibilityIcon fontSize="small"/>
                                </IconButton>
                            </Tooltip>
                        )}
                        {isFailed && (
                            <Tooltip title="Перезапустить">
                                <IconButton
                                    size="small"
                                    color="warning"
                                    onClick={() => handleRun(scenario.id)}
                                >
                                    <RefreshIcon fontSize="small"/>
                                </IconButton>
                            </Tooltip>
                        )}
                        {isDraft && (
                            <Tooltip title="Редактировать">
                                <IconButton
                                    size="small"
                                    onClick={() => handleOpenEdit(scenario.id)}
                                >
                                    <EditIcon fontSize="small"/>
                                </IconButton>
                            </Tooltip>
                        )}
                        {!isRunning && (
                            <Tooltip title={
                                hasResult
                                    ? "Удалить сценарий (план останется в истории)"
                                    : "Удалить сценарий"
                            }>
                                <IconButton
                                    size="small"
                                    color="error"
                                    onClick={() => handleDelete(scenario.id)}
                                >
                                    <DeleteIcon fontSize="small"/>
                                </IconButton>
                            </Tooltip>
                        )}
                    </Box>
                );
            },
        },
    ], [runningScenarioId, scenarios]);

    const defaultColDef = useMemo<ColDef>(() => ({
        sortable: true,
        filter: true,
        resizable: true,
    }), []);

    const getRowId = useCallback((params: any) => params.data.id, []);

    // ==========================================
    // РЕНДЕР
    // ==========================================
    if (loading && scenarios.length === 0) {
        return (
            <Box sx={{display: 'flex', justifyContent: 'center', mt: 8}}>
                <CircularProgress/>
            </Box>
        );
    }

    return (
        <Box sx={{height: '100%', display: 'flex', flexDirection: 'column'}}>
            {/* Заголовок */}
            <Box
                sx={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    mb: 2,
                    flexWrap: 'wrap',
                    gap: 2,
                }}
            >
                <Box sx={{display: 'flex', alignItems: 'center', gap: 2}}>
                    <ScienceIcon color="primary" sx={{fontSize: 32}}/>
                    <Typography variant="h4" component="h1" sx={{fontWeight: 600, color: '#2c3e50'}}>
                        What-if сценарии
                    </Typography>
                    <Chip label={`Всего: ${scenarios.length}`} variant="outlined"/>
                </Box>
                <Box sx={{display: 'flex', gap: 1}}>
                    <Button
                        variant="outlined"
                        startIcon={<RefreshIcon/>}
                        onClick={loadScenarios}
                        disabled={loading}
                    >
                        Обновить
                    </Button>
                    <Button
                        variant="contained"
                        startIcon={<AddIcon/>}
                        onClick={handleOpenCreate}
                    >
                        Создать сценарий
                    </Button>
                </Box>
            </Box>

            {/* Подсказка */}
            <Alert severity="info" icon={<InfoIcon/>} sx={{mb: 2}}>
                <Typography variant="body2">
                    <b>What-if</b> — сценарное планирование. Создайте сценарий с изменениями
                    (заказы, режим смен, capacity, календарь), запустите расчёт и сравните с базовым
                    планом. <b>Основная БД не изменяется</b> — результат сохраняется как отдельная
                    версия плана.
                </Typography>
            </Alert>

            {error && (
                <Alert severity="error" sx={{mb: 2}} onClose={() => setError(null)}>
                    {error}
                </Alert>
            )}

            {/* Таблица сценариев */}
            <Card
                sx={{
                    flexGrow: 1,
                    boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
                    display: 'flex',
                    flexDirection: 'column',
                    minHeight: 0,
                }}
            >
                <CardContent
                    sx={{
                        p: 2,
                        flexGrow: 1,
                        display: 'flex',
                        flexDirection: 'column',
                        minHeight: 0,
                    }}
                >
                    <Box className="ag-theme-alpine" sx={{flexGrow: 1, width: '100%', minHeight: 0}}>
                        <AgGridReact
                            rowData={scenarios}
                            columnDefs={columnDefs}
                            defaultColDef={defaultColDef}
                            getRowId={getRowId}
                            pagination
                            paginationPageSize={20}
                            paginationPageSizeSelector={[20, 50, 100]}
                            suppressPropertyNamesCheck
                            onGridReady={(params: GridReadyEvent) => params.api.sizeColumnsToFit()}
                        />
                    </Box>
                </CardContent>
            </Card>

            {/* Диалог создания/редактирования (DraggableDialog) */}
            <DraggableDialog
                open={dialogOpen}
                onClose={() => !saving && setDialogOpen(false)}
                title={editingScenario ? `Редактировать: ${editingScenario.name}` : 'Создать What-if сценарий'}
                initialWidth={900}
                initialHeight={700}
                minWidth={640}
                minHeight={500}
                actions={
                    <>
                        <Button onClick={() => setDialogOpen(false)} disabled={saving}>
                            Отмена
                        </Button>
                        <Button
                            variant="contained"
                            onClick={handleSave}
                            disabled={saving || !!formJsonError}
                            startIcon={saving ? <CircularProgress size={20}/> : <SaveIcon/>}
                        >
                            {saving ? 'Сохранение...' : 'Сохранить'}
                        </Button>
                    </>
                }
            >
                <Box sx={{display: 'flex', flexDirection: 'column', gap: 2}}>
                    <TextField
                        label="Название сценария"
                        fullWidth
                        required
                        value={formName}
                        onChange={(e) => setFormName(e.target.value)}
                        placeholder="Например: +20% крем-мыло 1л"
                    />

                    <FormControl fullWidth required disabled={!!editingScenario}>
                        <InputLabel>Базовый план</InputLabel>
                        <Select
                            value={formBaseVersionId}
                            label="Базовый план"
                            onChange={(e) => setFormBaseVersionId(e.target.value)}
                        >
                            {versions.map((v) => (
                                <MenuItem key={v.id} value={v.id}>
                                    {v.name}
                                    {v.is_active ? ' (активный)' : ''}
                                </MenuItem>
                            ))}
                        </Select>
                    </FormControl>

                    <TextField
                        label="Комментарий"
                        fullWidth
                        multiline
                        rows={2}
                        value={formComment}
                        onChange={(e) => setFormComment(e.target.value)}
                    />

                    <Divider/>

                    <Typography variant="subtitle2" sx={{fontWeight: 600}}>
                        Шаблоны изменений
                    </Typography>
                    <Box sx={{display: 'flex', gap: 1, flexWrap: 'wrap'}}>
                        <Button size="small" variant="outlined" onClick={() => handleApplyTemplate(JSON_TEMPLATE_SHIFT_MODE)}>
                            Режим смен 3x8
                        </Button>
                        <Button size="small" variant="outlined" onClick={() => handleApplyTemplate(JSON_TEMPLATE_ADD_ORDER)}>
                            + Заказ
                        </Button>
                        <Button size="small" variant="outlined" onClick={() => handleApplyTemplate(JSON_TEMPLATE_CAPACITY)}>
                            + Capacity
                        </Button>
                        <Button size="small" variant="outlined" onClick={() => handleApplyTemplate(JSON_TEMPLATE_BREAKDOWN)}>
                            Авария Р4
                        </Button>
                        <Button size="small" variant="outlined" onClick={() => handleApplyTemplate(JSON_TEMPLATE_FULL)}>
                            Полный пример
                        </Button>
                    </Box>

                    <Typography variant="subtitle2" sx={{fontWeight: 600}}>
                        Изменения (JSON)
                    </Typography>
                    <TextField
                        fullWidth
                        multiline
                        rows={14}
                        value={formChangesJson}
                        onChange={(e) => {
                            setFormChangesJson(e.target.value);
                            setFormJsonError(null);
                        }}
                        onBlur={validateJson}
                        error={!!formJsonError}
                        helperText={formJsonError || 'JSON должен быть валидным'}
                        slotProps={{
                            input: {
                                style: {
                                    fontFamily: 'monospace',
                                    fontSize: '0.85rem',
                                },
                            },
                        }}
                    />
                </Box>
            </DraggableDialog>

            {/* Диалог результата (DraggableDialog) */}
            <DraggableDialog
                open={resultDialogOpen}
                onClose={() => setResultDialogOpen(false)}
                title={
                    <Box sx={{display: 'flex', alignItems: 'center', gap: 1}}>
                        <CheckCircleIcon color="success"/>
                        <Typography variant="h6" component="div" sx={{fontWeight: 600}}>
                            Результат сценария
                        </Typography>
                    </Box>
                }
                initialWidth={800}
                initialHeight="auto"
                minWidth={640}
                minHeight={400}
                actions={
                    <>
                        <Button onClick={() => setResultDialogOpen(false)}>Закрыть</Button>
                        {runResult?.result_version_id && (
                            <Button
                                variant="contained"
                                onClick={() => {
                                    window.open(`/gantt?version_id=${runResult.result_version_id}`, '_blank');
                                }}
                            >
                                Открыть план
                            </Button>
                        )}
                    </>
                }
            >
                {runResult && (
                    <Box sx={{display: 'flex', flexDirection: 'column', gap: 2}}>
                        <Alert severity="info">
                            <b>{runResult.scenario_name}</b> — сравнение с базовым планом
                        </Alert>

                        <TableContainer component={Paper} variant="outlined">
                            <Table size="small">
                                <TableHead>
                                    <TableRow sx={{bgcolor: '#f5f7fa'}}>
                                        <TableCell><b>Метрика</b></TableCell>
                                        <TableCell align="right"><b>База</b></TableCell>
                                        <TableCell align="right"><b>Результат</b></TableCell>
                                        <TableCell align="right"><b>Δ</b></TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    <MetricRow
                                        label="Makespan (мин)"
                                        base={runResult.base_metrics.makespan_minutes}
                                        result={runResult.result_metrics?.makespan_minutes}
                                        delta={runResult.makespan_delta_minutes}
                                        deltaPercent={runResult.makespan_delta_percent}
                                        formatValue={(v) => v.toFixed(0)}
                                    />
                                    <MetricRow
                                        label="Всего задач"
                                        base={runResult.base_metrics.total_tasks}
                                        result={runResult.result_metrics?.total_tasks}
                                        delta={runResult.total_tasks_delta}
                                    />
                                    <MetricRow
                                        label="Заблокировано"
                                        base={runResult.base_metrics.blocked_tasks}
                                        result={runResult.result_metrics?.blocked_tasks}
                                        delta={runResult.blocked_tasks_delta}
                                    />
                                    <MetricRow
                                        label="Замедленное охлаждение"
                                        base={runResult.base_metrics.cooling_slow_tasks}
                                        result={runResult.result_metrics?.cooling_slow_tasks}
                                        delta={runResult.cooling_slow_tasks_delta}
                                    />
                                    <MetricRow
                                        label="ЧЗ не завершено"
                                        base={runResult.base_metrics.cz_incomplete_tasks}
                                        result={runResult.result_metrics?.cz_incomplete_tasks}
                                        delta={runResult.cz_incomplete_tasks_delta}
                                    />
                                </TableBody>
                            </Table>
                        </TableContainer>

                        {runResult.result_version_id && (
                            <Alert severity="success" icon={<CheckCircleIcon/>}>
                                Новая версия плана создана: <b>{runResult.result_version_id.substring(0, 8)}</b>.
                                Нажмите «Открыть план», чтобы увидеть его на диаграмме Ганта.
                            </Alert>
                        )}
                    </Box>
                )}
            </DraggableDialog>
        </Box>
    );
};

// ==========================================
// ВСПОМОГАТЕЛЬНЫЙ КОМПОНЕНТ
// ==========================================

interface MetricRowProps {
    label: string;
    base: number;
    result?: number | null;
    delta?: number | null;
    deltaPercent?: number | null;
    formatValue?: (v: number) => string;
}

const MetricRow: React.FC<MetricRowProps> = ({
                                                 label,
                                                 base,
                                                 result,
                                                 delta,
                                                 deltaPercent,
                                                 formatValue,
                                             }) => {
    const fmt = formatValue || ((v: number) => v.toString());
    const hasDelta = delta !== undefined && delta !== null;

    let deltaColor = '#7f8c8d';
    if (hasDelta) {
        if (delta < 0) deltaColor = '#2ecc71';
        else if (delta > 0) deltaColor = '#e74c3c';
    }

    return (
        <TableRow>
            <TableCell>{label}</TableCell>
            <TableCell align="right">{fmt(base)}</TableCell>
            <TableCell align="right">
                {result !== undefined && result !== null ? fmt(result) : '—'}
            </TableCell>
            <TableCell
                align="right"
                sx={{
                    color: deltaColor,
                    fontWeight: hasDelta && delta !== 0 ? 600 : 400,
                }}
            >
                {hasDelta ? (
                    <>
                        {delta > 0 ? '+' : ''}{fmt(delta)}
                        {deltaPercent !== undefined && deltaPercent !== null && (
                            <Typography
                                component="span"
                                variant="caption"
                                sx={{ml: 0.5, color: 'inherit'}}
                            >
                                ({deltaPercent > 0 ? '+' : ''}{deltaPercent.toFixed(1)}%)
                            </Typography>
                        )}
                    </>
                ) : '—'}
            </TableCell>
        </TableRow>
    );
};

export default WhatIfPage;