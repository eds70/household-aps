// frontend/src/pages/ShiftPage.tsx
import React, {useCallback, useEffect, useState} from 'react';
import {
    Accordion,
    AccordionDetails,
    AccordionSummary,
    Alert,
    Badge,
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
    LinearProgress,
    MenuItem,
    Select,
    TextField,
    Tooltip,
    Typography,
} from '@mui/material';
import {
    AcUnit as AcUnitIcon,
    CheckCircle as CheckCircleIcon,
    ExpandMore as ExpandMoreIcon,
    History as HistoryIcon,
    HourglassEmpty as HourglassIcon,
    Lock as LockIcon,
    LockOpen as LockOpenIcon,
    PlayArrow as PlayIcon,
    QrCodeScanner as QrCodeScannerIcon,
    Refresh as RefreshIcon,
    Save as SaveIcon,
    Schedule as ScheduleIcon,
    Science as ScienceIcon,
    Warning as WarningIcon,
} from '@mui/icons-material';
import {czApi, labApi, shiftApi} from '../services/api';
import type {
    CoolingMode,
    CzProgress,
    CzStatus,
    LabStatus,
    Shift,
    ShiftTask,
    ShiftTasksResponse,
    ShiftTaskStatus,
    TaskFactRequest,
} from '../types';

// ==========================================
// КОНСТАНТЫ
// ==========================================

const STATUS_LABELS: Record<ShiftTaskStatus, string> = {
    PLANNED: 'Запланировано',
    IN_PROGRESS: 'В работе',
    DONE: 'Выполнено',
    CANCELLED: 'Отменено',
};

const STATUS_COLORS: Record<ShiftTaskStatus, 'default' | 'primary' | 'success' | 'error'> = {
    PLANNED: 'default',
    IN_PROGRESS: 'primary',
    DONE: 'success',
    CANCELLED: 'error',
};

const ROLE_LABELS: Record<string, string> = {
    REACTOR_OP: 'Варка',
    TANK_TRANSFER: 'Перекачка',
    LINE_FILL: 'Слив',
    WASH: 'Замыв',
    SETUP: 'Переналадка',
    LAB_BLOCK: 'Лаборатория',
};

const LAB_STATUS_LABELS: Record<LabStatus, string> = {
    NOT_REQUIRED: 'Не требуется',
    PENDING_LAB: 'Ожидает лабу',
    APPROVED: 'Одобрено',
    BLOCKED: 'Заблокировано',
};

const LAB_STATUS_COLORS: Record<LabStatus, 'default' | 'info' | 'success' | 'error' | 'warning'> = {
    NOT_REQUIRED: 'default',
    PENDING_LAB: 'info',
    APPROVED: 'success',
    BLOCKED: 'error',
};

const CZ_STATUS_LABELS: Record<CzStatus, string> = {
    NOT_APPLICABLE: 'Без ЧЗ',
    PENDING: 'ЧЗ: ожидает',
    IN_PROGRESS: 'ЧЗ: в работе',
    COMPLETED: 'ЧЗ: завершено',
};

const CZ_STATUS_COLORS: Record<CzStatus, 'default' | 'warning' | 'info' | 'success'> = {
    NOT_APPLICABLE: 'default',
    PENDING: 'warning',
    IN_PROGRESS: 'info',
    COMPLETED: 'success',
};

// ==========================================
// КОМПОНЕНТ
// ==========================================

const ShiftPage: React.FC = () => {
    const [selectedDate, setSelectedDate] = useState<string>(
        new Date().toISOString().split('T')[0]
    );

    // ==========================================
    // Итерация 11: список смен дня + выбранная смена
    // ==========================================
    const [shiftsOfDay, setShiftsOfDay] = useState<Shift[]>([]);
    const [selectedShiftId, setSelectedShiftId] = useState<string | null>(null);
    const [currentShift, setCurrentShift] = useState<Shift | null>(null);

    const [tasksData, setTasksData] = useState<ShiftTasksResponse | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const [editDialogOpen, setEditDialogOpen] = useState(false);
    const [selectedTask, setSelectedTask] = useState<ShiftTask | null>(null);
    const [factForm, setFactForm] = useState<TaskFactRequest>({});

    // Итерация 5: диалог блокировки
    const [blockDialogOpen, setBlockDialogOpen] = useState(false);
    const [blockingTask, setBlockingTask] = useState<ShiftTask | null>(null);
    const [blockReason, setBlockReason] = useState('');
    const [blockComment, setBlockComment] = useState('');
    const [blockBusy, setBlockBusy] = useState(false);

    // Итерация 5: диалог разблокировки
    const [unblockDialogOpen, setUnblockDialogOpen] = useState(false);
    const [unblockingTask, setUnblockingTask] = useState<ShiftTask | null>(null);
    const [unblockComment, setUnblockComment] = useState('');

    // Итерация 8: прогресс ЧЗ
    const [czProgress, setCzProgress] = useState<Record<string, CzProgress>>({});
    const [czLoading, setCzLoading] = useState(false);

    // ==========================================
    // Загрузка данных смены
    // ==========================================
    const loadShift = useCallback(async (
        dateStr: string,
        shiftIdToSelect?: string | null,
    ) => {
        setLoading(true);
        setError(null);
        try {
            // 1. Загружаем ВСЕ смены за день
            const shifts = await shiftApi.getByDate(dateStr);

            if (!shifts || shifts.length === 0) {
                setShiftsOfDay([]);
                setSelectedShiftId(null);
                setCurrentShift(null);
                setTasksData(null);
                setError(`Смены на ${dateStr} не найдены`);
                return;
            }

            setShiftsOfDay(shifts);

            // 2. Выбираем смену:
            //    - если передан shiftIdToSelect — его
            //    - иначе — первую рабочую, либо первую из списка
            let shift: Shift;
            if (shiftIdToSelect) {
                shift = shifts.find((s) => s.id === shiftIdToSelect) || shifts[0];
            } else {
                shift = shifts.find((s) => s.is_working) || shifts[0];
            }

            setSelectedShiftId(shift.id);
            setCurrentShift(shift);

            // 3. Загружаем задачи выбранной смены
            const tasks = await shiftApi.getTasks(shift.id);
            setTasksData(tasks);

            // 4. Итерация 8: подгружаем прогресс ЧЗ
            await loadCzProgressForTasks(tasks);
        } catch (err: any) {
            const detail = err.response?.data?.detail;
            setError(typeof detail === 'string' ? detail : 'Ошибка загрузки смены');
            setShiftsOfDay([]);
            setSelectedShiftId(null);
            setCurrentShift(null);
            setTasksData(null);
            setCzProgress({});
        } finally {
            setLoading(false);
        }
    }, []);

    // ==========================================
    // Итерация 8: прогресс ЧЗ по задачам
    // ==========================================
    const loadCzProgressForTasks = useCallback(async (tasks: ShiftTasksResponse) => {
        const batchIds = new Set<string>();
        tasks.groups.forEach((g) =>
            g.tasks.forEach((t) => {
                if (t.batch_id) batchIds.add(t.batch_id);
            })
        );

        if (batchIds.size === 0) {
            setCzProgress({});
            return;
        }

        setCzLoading(true);
        const result: Record<string, CzProgress> = {};
        await Promise.all(
            Array.from(batchIds).map(async (bid) => {
                try {
                    const p = await czApi.getBatchProgress(bid);
                    result[bid] = p;
                } catch {
                    // партия может быть без ЧЗ — игнорируем
                }
            })
        );
        setCzProgress(result);
        setCzLoading(false);
    }, []);

    const reloadCzProgress = async () => {
        if (tasksData) {
            await loadCzProgressForTasks(tasksData);
        }
    };

    // ==========================================
    // Первичная загрузка и загрузка при смене даты
    // ==========================================
    useEffect(() => {
        loadShift(selectedDate);
    }, [selectedDate, loadShift]);

    // ==========================================
    // Итерация 11: смена выбранной смены
    // ==========================================
    const handleShiftChange = async (newShiftId: string) => {
        setSelectedShiftId(newShiftId);
        const shift = shiftsOfDay.find((s) => s.id === newShiftId);
        if (shift) {
            setCurrentShift(shift);
            try {
                const tasks = await shiftApi.getTasks(shift.id);
                setTasksData(tasks);
                await loadCzProgressForTasks(tasks);
            } catch (err: any) {
                const detail = err.response?.data?.detail;
                setError(typeof detail === 'string' ? detail : 'Ошибка загрузки заданий');
            }
        }
    };

    // ==========================================
    // Обработчики задач
    // ==========================================
    const handleOpenFactDialog = (task: ShiftTask) => {
        setSelectedTask(task);
        setFactForm({
            actual_start: task.actual_start || undefined,
            actual_end: task.actual_end || undefined,
            actual_qty: task.actual_qty || undefined,
            material_load_at: task.material_load_at || undefined,
            status: task.status,
        });
        setEditDialogOpen(true);
    };

    const handleSaveFact = async () => {
        if (!selectedTask) return;
        try {
            await shiftApi.updateTaskFact(selectedTask.id, factForm);
            setEditDialogOpen(false);
            if (currentShift) {
                const tasks = await shiftApi.getTasks(currentShift.id);
                setTasksData(tasks);
                await loadCzProgressForTasks(tasks);
            }
        } catch (err: any) {
            const detail = err.response?.data?.detail;
            setError(typeof detail === 'string' ? detail : 'Ошибка сохранения факта');
        }
    };

    const handleMaterialLoad = async (task: ShiftTask) => {
        try {
            await shiftApi.updateTaskFact(task.id, {
                material_load_at: new Date().toISOString(),
                status: 'IN_PROGRESS',
            });
            if (currentShift) {
                const tasks = await shiftApi.getTasks(currentShift.id);
                setTasksData(tasks);
            }
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Ошибка');
        }
    };

    const handleComplete = async (task: ShiftTask) => {
        try {
            await shiftApi.updateTaskFact(task.id, {
                actual_end: new Date().toISOString(),
                status: 'DONE',
            });
            if (currentShift) {
                const tasks = await shiftApi.getTasks(currentShift.id);
                setTasksData(tasks);
                await loadCzProgressForTasks(tasks);
            }
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Ошибка');
        }
    };

    // ==========================================
    // Итерация 5: блокировка
    // ==========================================
    const handleOpenBlockDialog = (task: ShiftTask) => {
        if (!task.batch_id) {
            setError('Задача не привязана к партии');
            return;
        }
        setBlockingTask(task);
        setBlockReason('');
        setBlockComment('');
        setBlockDialogOpen(true);
    };

    const handleDoBlock = async () => {
        if (!blockingTask || !blockingTask.batch_id) return;
        if (blockReason.trim().length < 3) {
            setError('Укажите причину блокировки (минимум 3 символа)');
            return;
        }
        setBlockBusy(true);
        try {
            await labApi.blockBatch(blockingTask.batch_id, {
                reason: blockReason,
                scheduled_task_id: blockingTask.id,
                comment: blockComment || null,
            });
            setBlockDialogOpen(false);
            if (currentShift) {
                const tasks = await shiftApi.getTasks(currentShift.id);
                setTasksData(tasks);
            }
        } catch (err: any) {
            const detail = err.response?.data?.detail;
            setError(typeof detail === 'string' ? detail : 'Ошибка блокировки');
        } finally {
            setBlockBusy(false);
        }
    };

    const handleOpenUnblockDialog = (task: ShiftTask) => {
        if (!task.batch_id) return;
        setUnblockingTask(task);
        setUnblockComment('');
        setUnblockDialogOpen(true);
    };

    const handleDoUnblock = async () => {
        if (!unblockingTask || !unblockingTask.batch_id) return;
        try {
            await labApi.unblockBatch(unblockingTask.batch_id, {
                comment: unblockComment || null,
            });
            setUnblockDialogOpen(false);
            if (currentShift) {
                const tasks = await shiftApi.getTasks(currentShift.id);
                setTasksData(tasks);
            }
        } catch (err: any) {
            const detail = err.response?.data?.detail;
            setError(typeof detail === 'string' ? detail : 'Ошибка разблокировки');
        }
    };

    // ==========================================
    // Итерация 8: рендер прогресса ЧЗ
    // ==========================================
    const renderCzProgress = (task: ShiftTask) => {
        if (task.task_role !== 'LINE_FILL' || !task.batch_id) return null;

        const progress = czProgress[task.batch_id];
        if (!progress) {
            return (
                <Chip
                    icon={<QrCodeScannerIcon/>}
                    label="ЧЗ: нет данных"
                    size="small"
                    variant="outlined"
                    color="default"
                />
            );
        }

        const status = progress.cz_status as CzStatus;
        const percent = Math.min(progress.progress_percent, 100);

        return (
            <Box sx={{mt: 0.5, width: '100%', maxWidth: 320}}>
                <Box sx={{display: 'flex', alignItems: 'center', gap: 1, mb: 0.25}}>
                    <Chip
                        icon={<QrCodeScannerIcon/>}
                        label={CZ_STATUS_LABELS[status]}
                        size="small"
                        color={CZ_STATUS_COLORS[status]}
                        variant={status === 'COMPLETED' ? 'filled' : 'outlined'}
                    />
                    <Typography variant="caption" color="text.secondary">
                        {progress.marked_qty.toFixed(0)}
                        {progress.planned_qty ? ` / ${progress.planned_qty.toFixed(0)}` : ''}
                        {' '}({percent.toFixed(0)}%)
                    </Typography>
                </Box>
                <LinearProgress
                    variant="determinate"
                    value={percent}
                    color={percent >= 95 ? 'success' : percent > 0 ? 'info' : 'warning'}
                    sx={{height: 6, borderRadius: 1}}
                />
            </Box>
        );
    };

    // ==========================================
    // Рендер задачи
    // ==========================================
    const renderTask = (task: ShiftTask) => {
        const startTime = new Date(task.planned_start).toLocaleTimeString('ru-RU', {
            hour: '2-digit', minute: '2-digit',
        });
        const endTime = new Date(task.planned_end).toLocaleTimeString('ru-RU', {
            hour: '2-digit', minute: '2-digit',
        });

        const isDone = task.status === 'DONE';
        const isInProgress = task.status === 'IN_PROGRESS';
        const isLabBlocked = task.is_lab_blocked === true;
        const labStatus: LabStatus = (task.lab_status as LabStatus) || 'NOT_REQUIRED';
        const coolingMode: CoolingMode = task.cooling_mode || null;
        const isSlowCooling = coolingMode === 'slow';

        let borderLeft = '1px solid #e0e0e0';
        let bgcolor = 'white';
        if (isLabBlocked) {
            borderLeft = '4px solid #e74c3c';
            bgcolor = '#ffebee';
        } else if (isSlowCooling) {
            borderLeft = '4px solid #e67e22';
            bgcolor = '#fff3e0';
        } else if (isDone) {
            borderLeft = '4px solid #4caf50';
        } else if (isInProgress) {
            borderLeft = '4px solid #2196f3';
        } else if (task.is_carryover) {
            borderLeft = '4px solid #ff9800';
            bgcolor = '#fff8e1';
        }

        return (
            <Card
                key={task.id}
                variant="outlined"
                sx={{mb: 1, borderLeft, bgcolor}}
            >
                <CardContent sx={{py: 1.5, px: 2, '&:last-child': {pb: 1.5}}}>
                    <Box sx={{display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 1}}>
                        <Box sx={{flexGrow: 1}}>
                            <Box sx={{display: 'flex', alignItems: 'center', gap: 1, mb: 0.5, flexWrap: 'wrap'}}>
                                {isLabBlocked && <LockIcon fontSize="small" sx={{color: '#e74c3c'}}/>}
                                {isSlowCooling && <HourglassIcon fontSize="small" sx={{color: '#e67e22'}}/>}
                                <Typography variant="subtitle2" sx={{fontWeight: 600}}>
                                    {task.operation_name}
                                </Typography>
                                {task.task_role && (
                                    <Chip
                                        label={ROLE_LABELS[task.task_role] || task.task_role}
                                        size="small"
                                        variant="outlined"
                                    />
                                )}
                                {task.is_carryover && (
                                    <Chip
                                        icon={<HistoryIcon/>}
                                        label="Переходящее"
                                        size="small"
                                        color="warning"
                                    />
                                )}
                                {labStatus !== 'NOT_REQUIRED' && (
                                    <Chip
                                        icon={<ScienceIcon/>}
                                        label={LAB_STATUS_LABELS[labStatus]}
                                        size="small"
                                        color={LAB_STATUS_COLORS[labStatus]}
                                        variant={isLabBlocked ? 'filled' : 'outlined'}
                                    />
                                )}
                                {coolingMode === 'slow' && (
                                    <Chip
                                        icon={<HourglassIcon/>}
                                        label="Замедленное охлаждение ×1.3"
                                        size="small"
                                        color="warning"
                                        variant="filled"
                                    />
                                )}
                                {coolingMode === 'fast' && (
                                    <Chip
                                        icon={<AcUnitIcon/>}
                                        label="Охлаждение (норма)"
                                        size="small"
                                        color="info"
                                        variant="outlined"
                                    />
                                )}
                            </Box>

                            <Typography variant="caption" color="text.secondary" sx={{display: 'block'}}>
                                {task.product_code} — {task.product_name}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                                {startTime} — {endTime} • {task.duration_minutes} мин
                            </Typography>

                            {task.linked_equipment_name && (
                                <Typography variant="caption" color="text.secondary" sx={{display: 'block'}}>
                                    + {task.linked_equipment_name}
                                </Typography>
                            )}

                            {renderCzProgress(task)}

                            {task.lab_block_reason && (
                                <Alert
                                    severity="error"
                                    icon={<WarningIcon fontSize="inherit"/>}
                                    sx={{mt: 0.5, py: 0}}
                                >
                                    <Typography variant="caption">{task.lab_block_reason}</Typography>
                                </Alert>
                            )}

                            {task.material_load_at && (
                                <Chip
                                    label={`Сырьё загружено: ${new Date(task.material_load_at).toLocaleTimeString('ru-RU', {hour: '2-digit', minute: '2-digit'})}`}
                                    size="small"
                                    color="info"
                                    variant="outlined"
                                    sx={{mt: 0.5}}
                                />
                            )}

                            {task.actual_qty && (
                                <Typography variant="caption" sx={{display: 'block', mt: 0.5}}>
                                    Факт: {task.actual_qty}
                                </Typography>
                            )}
                        </Box>

                        <Box sx={{display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 0.5}}>
                            <Chip
                                label={STATUS_LABELS[task.status]}
                                color={STATUS_COLORS[task.status]}
                                size="small"
                            />

                            <Box sx={{display: 'flex', gap: 0.5, mt: 0.5}}>
                                {task.batch_id && !isLabBlocked && (
                                    <Tooltip title="Заблокировать лабораторией">
                                        <IconButton
                                            size="small"
                                            color="error"
                                            onClick={() => handleOpenBlockDialog(task)}
                                        >
                                            <LockIcon fontSize="small"/>
                                        </IconButton>
                                    </Tooltip>
                                )}
                                {task.batch_id && isLabBlocked && (
                                    <Tooltip title="Разблокировать">
                                        <IconButton
                                            size="small"
                                            color="success"
                                            onClick={() => handleOpenUnblockDialog(task)}
                                        >
                                            <LockOpenIcon fontSize="small"/>
                                        </IconButton>
                                    </Tooltip>
                                )}

                                {task.task_role === 'REACTOR_OP' && !task.material_load_at && !isLabBlocked && (
                                    <Tooltip title="Отметить загрузку сырья">
                                        <IconButton
                                            size="small"
                                            color="info"
                                            onClick={() => handleMaterialLoad(task)}
                                        >
                                            <PlayIcon fontSize="small"/>
                                        </IconButton>
                                    </Tooltip>
                                )}
                                {task.status !== 'DONE' && !isLabBlocked && (
                                    <Tooltip title="Отметить выполнение">
                                        <IconButton
                                            size="small"
                                            color="success"
                                            onClick={() => handleComplete(task)}
                                        >
                                            <CheckCircleIcon fontSize="small"/>
                                        </IconButton>
                                    </Tooltip>
                                )}
                                <Tooltip title="Подробнее / изменить">
                                    <IconButton
                                        size="small"
                                        onClick={() => handleOpenFactDialog(task)}
                                    >
                                        <SaveIcon fontSize="small"/>
                                    </IconButton>
                                </Tooltip>
                            </Box>
                        </Box>
                    </Box>
                </CardContent>
            </Card>
        );
    };

    // ==========================================
    // Рендер
    // ==========================================
    return (
        <Box sx={{height: '100%', display: 'flex', flexDirection: 'column', minHeight: 0}}>
            {/* ====== ФИКСИРОВАННАЯ ШАПКА ====== */}
            <Box sx={{flexShrink: 0}}>
                <Box sx={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    mb: 2,
                    flexWrap: 'wrap',
                    gap: 2,
                }}>
                    <Box sx={{display: 'flex', alignItems: 'center', gap: 2}}>
                        <ScheduleIcon color="primary" sx={{fontSize: 32}}/>
                        <Typography variant="h4" component="h1" sx={{fontWeight: 600, color: '#2c3e50'}}>
                            Рабочее место мастера
                        </Typography>
                    </Box>
                    <Box sx={{display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap'}}>
                        {/* Итерация 11: селектор смены */}
                        {shiftsOfDay.length > 0 && (
                            <FormControl size="small" sx={{minWidth: 260}}>
                                <InputLabel>Смена</InputLabel>
                                <Select
                                    value={selectedShiftId || ''}
                                    label="Смена"
                                    onChange={(e) => handleShiftChange(e.target.value as string)}
                                >
                                    {shiftsOfDay.map((s) => (
                                        <MenuItem key={s.id} value={s.id}>
                                            {s.name} {s.is_working ? '' : '(выходной)'}
                                        </MenuItem>
                                    ))}
                                </Select>
                            </FormControl>
                        )}

                        <TextField
                            type="date"
                            size="small"
                            label="Дата смены"
                            value={selectedDate}
                            onChange={(e) => setSelectedDate(e.target.value)}
                            slotProps={{inputLabel: {shrink: true}}}
                        />
                        <Tooltip title="Обновить данные смены">
                            <Button
                                variant="outlined"
                                startIcon={<RefreshIcon/>}
                                onClick={() => loadShift(selectedDate, selectedShiftId)}
                            >
                                Обновить
                            </Button>
                        </Tooltip>
                        <Tooltip title="Обновить только прогресс ЧЗ">
                            <span>
                                <Button
                                    variant="outlined"
                                    color="secondary"
                                    startIcon={czLoading ? <CircularProgress size={16}/> : <QrCodeScannerIcon/>}
                                    onClick={reloadCzProgress}
                                    disabled={!tasksData || czLoading}
                                >
                                    ЧЗ
                                </Button>
                            </span>
                        </Tooltip>
                    </Box>
                </Box>

                {error && (
                    <Alert severity="warning" sx={{mb: 2}} onClose={() => setError(null)}>
                        {error}
                    </Alert>
                )}

                {loading && (
                    <Box sx={{display: 'flex', justifyContent: 'center', mt: 4}}>
                        <CircularProgress/>
                    </Box>
                )}

                {!loading && currentShift && tasksData && (
                    <Card sx={{mb: 2, bgcolor: '#f8f9fa'}}>
                        <CardContent sx={{py: 1.5}}>
                            <Box sx={{display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap'}}>
                                <Typography variant="h6" sx={{fontWeight: 600}}>
                                    {currentShift.name}
                                </Typography>
                                <Chip
                                    label={`${new Date(currentShift.starts_at).toLocaleTimeString('ru-RU', {hour: '2-digit', minute: '2-digit'})} — ${new Date(currentShift.ends_at).toLocaleTimeString('ru-RU', {hour: '2-digit', minute: '2-digit'})}`}
                                    variant="outlined"
                                />
                                {!currentShift.is_working && (
                                    <Chip label="Нерабочая смена" color="default"/>
                                )}
                                <Chip
                                    label={`Всего задач: ${tasksData.total_tasks}`}
                                    color="primary"
                                    variant="outlined"
                                />
                                {tasksData.carryover_count > 0 && (
                                    <Chip
                                        icon={<HistoryIcon/>}
                                        label={`Переходящих: ${tasksData.carryover_count}`}
                                        color="warning"
                                    />
                                )}
                                <Chip
                                    label={`Выполнено: ${tasksData.done_count} / ${tasksData.total_tasks}`}
                                    color="success"
                                    variant="outlined"
                                />
                            </Box>
                        </CardContent>
                    </Card>
                )}
            </Box>

            {/* ====== ПРОКРУЧИВАЕМЫЙ СПИСОК ЗАДАЧ ====== */}
            {!loading && currentShift && tasksData && (
                <Box sx={{flexGrow: 1, minHeight: 0, overflow: 'auto', pr: 1}}>
                    {tasksData.groups.length === 0 ? (
                        <Card>
                            <CardContent>
                                <Typography color="text.secondary" align="center">
                                    На эту смену нет заданий
                                </Typography>
                            </CardContent>
                        </Card>
                    ) : (
                        tasksData.groups.map((group) => {
                            const blockedCount = group.tasks.filter(t => t.is_lab_blocked).length;
                            return (
                                <Accordion
                                    key={group.equipment_id}
                                    defaultExpanded
                                    sx={{mb: 1, boxShadow: '0 2px 6px rgba(0,0,0,0.08)'}}
                                >
                                    <AccordionSummary expandIcon={<ExpandMoreIcon/>}>
                                        <Box sx={{display: 'flex', alignItems: 'center', gap: 1, width: '100%'}}>
                                            <Typography sx={{fontWeight: 600}}>
                                                {group.equipment_name}
                                            </Typography>
                                            {group.equipment_code && (
                                                <Chip label={group.equipment_code} size="small" variant="outlined"/>
                                            )}
                                            {blockedCount > 0 && (
                                                <Badge badgeContent={blockedCount} color="error">
                                                    <Chip
                                                        icon={<LockIcon/>}
                                                        label="Заблокировано"
                                                        size="small"
                                                        color="error"
                                                        variant="outlined"
                                                    />
                                                </Badge>
                                            )}
                                            <Chip
                                                label={`${group.tasks.length} задач`}
                                                size="small"
                                                color="primary"
                                                variant="outlined"
                                                sx={{ml: 'auto'}}
                                            />
                                        </Box>
                                    </AccordionSummary>
                                    <AccordionDetails>
                                        {group.tasks.map(renderTask)}
                                    </AccordionDetails>
                                </Accordion>
                            );
                        })
                    )}
                </Box>
            )}

            {!loading && !currentShift && !error && (
                <Card>
                    <CardContent>
                        <Typography color="text.secondary" align="center">
                            Смена на {selectedDate} не найдена
                        </Typography>
                    </CardContent>
                </Card>
            )}

            {/* ====== ДИАЛОГИ ====== */}

            {/* Диалог внесения факта */}
            <Dialog open={editDialogOpen} onClose={() => setEditDialogOpen(false)} maxWidth="sm" fullWidth>
                <DialogTitle sx={{fontWeight: 600}}>
                    {selectedTask && `${selectedTask.operation_name} — внести факт`}
                </DialogTitle>
                <DialogContent>
                    {selectedTask && (
                        <Box sx={{display: 'flex', flexDirection: 'column', gap: 2, mt: 1}}>
                            <Box>
                                <Typography variant="body2" color="text.secondary">
                                    <b>Продукт:</b> {selectedTask.product_code} — {selectedTask.product_name}<br/>
                                    <b>Оборудование:</b> {selectedTask.equipment_name}
                                    {selectedTask.linked_equipment_name && ` + ${selectedTask.linked_equipment_name}`}<br/>
                                    <b>План:</b> {new Date(selectedTask.planned_start).toLocaleString('ru-RU')} — {new Date(selectedTask.planned_end).toLocaleString('ru-RU')}
                                </Typography>
                                {selectedTask.cooling_mode && (
                                    <Alert
                                        severity={selectedTask.cooling_mode === 'slow' ? 'warning' : 'info'}
                                        sx={{mt: 1}}
                                        icon={selectedTask.cooling_mode === 'slow' ? <HourglassIcon/> : <AcUnitIcon/>}
                                    >
                                        <Typography variant="caption">
                                            {selectedTask.cooling_mode === 'slow'
                                                ? 'Режим охлаждения: замедленный (×1.3) — зона охлаждения была перегружена.'
                                                : 'Режим охлаждения: обычный.'}
                                        </Typography>
                                    </Alert>
                                )}
                                {selectedTask.task_role === 'LINE_FILL' && selectedTask.batch_id && czProgress[selectedTask.batch_id] && (
                                    <Alert severity="info" sx={{mt: 1}} icon={<QrCodeScannerIcon/>}>
                                        <Typography variant="caption">
                                            <b>ЧЗ:</b> {CZ_STATUS_LABELS[czProgress[selectedTask.batch_id].cz_status]}
                                            {' — '}
                                            {czProgress[selectedTask.batch_id].marked_qty.toFixed(0)}
                                            {czProgress[selectedTask.batch_id].planned_qty
                                                ? ` из ${czProgress[selectedTask.batch_id].planned_qty!.toFixed(0)}`
                                                : ''}
                                            {' '}({czProgress[selectedTask.batch_id].progress_percent.toFixed(0)}%)
                                        </Typography>
                                    </Alert>
                                )}
                            </Box>

                            <Divider/>

                            <TextField
                                label="Факт. начало"
                                type="datetime-local"
                                fullWidth
                                value={factForm.actual_start?.slice(0, 16) || ''}
                                onChange={(e) => setFactForm({...factForm, actual_start: e.target.value ? new Date(e.target.value).toISOString() : undefined})}
                                slotProps={{inputLabel: {shrink: true}}}
                            />

                            <TextField
                                label="Факт. окончание"
                                type="datetime-local"
                                fullWidth
                                value={factForm.actual_end?.slice(0, 16) || ''}
                                onChange={(e) => setFactForm({...factForm, actual_end: e.target.value ? new Date(e.target.value).toISOString() : undefined})}
                                slotProps={{inputLabel: {shrink: true}}}
                            />

                            <TextField
                                label="Загрузка сырья в реактор"
                                type="datetime-local"
                                fullWidth
                                value={factForm.material_load_at?.slice(0, 16) || ''}
                                onChange={(e) => setFactForm({...factForm, material_load_at: e.target.value ? new Date(e.target.value).toISOString() : undefined})}
                                slotProps={{inputLabel: {shrink: true}}}
                            />

                            <TextField
                                label="Факт. количество (бутылок)"
                                type="number"
                                fullWidth
                                value={factForm.actual_qty || ''}
                                onChange={(e) => setFactForm({...factForm, actual_qty: e.target.value ? Number(e.target.value) : undefined})}
                            />

                            <FormControl fullWidth variant="outlined">
                                <InputLabel>Статус</InputLabel>
                                <Select
                                    value={factForm.status || 'PLANNED'}
                                    label="Статус"
                                    variant="outlined"
                                    onChange={(e) => setFactForm({...factForm, status: e.target.value as ShiftTaskStatus})}
                                >
                                    <MenuItem value="PLANNED">Запланировано</MenuItem>
                                    <MenuItem value="IN_PROGRESS">В работе</MenuItem>
                                    <MenuItem value="DONE">Выполнено</MenuItem>
                                    <MenuItem value="CANCELLED">Отменено</MenuItem>
                                </Select>
                            </FormControl>
                        </Box>
                    )}
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setEditDialogOpen(false)}>Отмена</Button>
                    <Button onClick={handleSaveFact} variant="contained" startIcon={<SaveIcon/>}>
                        Сохранить
                    </Button>
                </DialogActions>
            </Dialog>

            {/* Диалог блокировки */}
            <Dialog open={blockDialogOpen} onClose={() => setBlockDialogOpen(false)} maxWidth="sm" fullWidth>
                <DialogTitle sx={{fontWeight: 600, display: 'flex', alignItems: 'center', gap: 1}}>
                    <LockIcon color="error"/>
                    Заблокировать партию лабораторией
                </DialogTitle>
                <DialogContent>
                    {blockingTask && (
                        <Box sx={{display: 'flex', flexDirection: 'column', gap: 2, mt: 1}}>
                            <Alert severity="warning">
                                Партия <b>{blockingTask.batch_name || blockingTask.batch_id?.substring(0, 8)}</b>{' '}
                                ({blockingTask.product_name}) не будет участвовать в дальнейшем
                                планировании до разблокировки.
                            </Alert>

                            <TextField
                                label="Причина блокировки"
                                fullWidth
                                required
                                multiline
                                rows={2}
                                value={blockReason}
                                onChange={(e) => setBlockReason(e.target.value)}
                                placeholder="Например: не соответствует вязкость, pH вне нормы..."
                            />

                            <TextField
                                label="Комментарий (опционально)"
                                fullWidth
                                multiline
                                rows={2}
                                value={blockComment}
                                onChange={(e) => setBlockComment(e.target.value)}
                            />
                        </Box>
                    )}
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setBlockDialogOpen(false)}>Отмена</Button>
                    <Button
                        onClick={handleDoBlock}
                        variant="contained"
                        color="error"
                        disabled={blockBusy || blockReason.trim().length < 3}
                        startIcon={<LockIcon/>}
                    >
                        {blockBusy ? 'Блокировка...' : 'Заблокировать'}
                    </Button>
                </DialogActions>
            </Dialog>

            {/* Диалог разблокировки */}
            <Dialog open={unblockDialogOpen} onClose={() => setUnblockDialogOpen(false)} maxWidth="sm" fullWidth>
                <DialogTitle sx={{fontWeight: 600, display: 'flex', alignItems: 'center', gap: 1}}>
                    <LockOpenIcon color="success"/>
                    Разблокировать партию
                </DialogTitle>
                <DialogContent>
                    {unblockingTask && (
                        <Box sx={{display: 'flex', flexDirection: 'column', gap: 2, mt: 1}}>
                            <Alert severity="info">
                                Партия <b>{unblockingTask.batch_name || unblockingTask.batch_id?.substring(0, 8)}</b>{' '}
                                будет снова участвовать в планировании.
                            </Alert>

                            {unblockingTask.lab_block_reason && (
                                <Alert severity="error">
                                    <b>Причина блокировки:</b> {unblockingTask.lab_block_reason}
                                </Alert>
                            )}

                            <TextField
                                label="Комментарий (опционально)"
                                fullWidth
                                multiline
                                rows={2}
                                value={unblockComment}
                                onChange={(e) => setUnblockComment(e.target.value)}
                            />
                        </Box>
                    )}
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setUnblockDialogOpen(false)}>Отмена</Button>
                    <Button
                        onClick={handleDoUnblock}
                        variant="contained"
                        color="success"
                        startIcon={<LockOpenIcon/>}
                    >
                        Разблокировать
                    </Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
};

export default ShiftPage;