// frontend/src/pages/ShiftPage.tsx
import React, { useState, useEffect, useCallback } from 'react';
import {
    Box, Typography, Card, CardContent, Alert, CircularProgress,
    TextField, Button, Chip, Divider, Dialog, DialogTitle,
    DialogContent, DialogActions, IconButton, Tooltip,
    Accordion, AccordionSummary, AccordionDetails, FormControl,
    InputLabel, Select, MenuItem,
} from '@mui/material';
import {
    Refresh as RefreshIcon,
    ExpandMore as ExpandMoreIcon,
    Schedule as ScheduleIcon,
    PlayArrow as PlayIcon,
    CheckCircle as CheckCircleIcon,
    History as HistoryIcon,
    Save as SaveIcon,
} from '@mui/icons-material';
import { shiftApi } from '../services/api';
import type {
    Shift,
    ShiftTasksResponse,
    ShiftTask,
    ShiftTaskStatus,
    TaskFactRequest,
} from '../types';

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
};

const ShiftPage: React.FC = () => {
    const [selectedDate, setSelectedDate] = useState<string>(
        new Date().toISOString().split('T')[0]
    );
    const [currentShift, setCurrentShift] = useState<Shift | null>(null);
    const [tasksData, setTasksData] = useState<ShiftTasksResponse | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const [editDialogOpen, setEditDialogOpen] = useState(false);
    const [selectedTask, setSelectedTask] = useState<ShiftTask | null>(null);
    const [factForm, setFactForm] = useState<TaskFactRequest>({});

    const loadShift = useCallback(async (dateStr: string) => {
        setLoading(true);
        setError(null);
        try {
            const shift = await shiftApi.getByDate(dateStr);
            setCurrentShift(shift);

            const tasks = await shiftApi.getTasks(shift.id);
            setTasksData(tasks);
        } catch (err: any) {
            const detail = err.response?.data?.detail;
            setError(typeof detail === 'string' ? detail : 'Ошибка загрузки смены');
            setCurrentShift(null);
            setTasksData(null);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        loadShift(selectedDate);
    }, [selectedDate, loadShift]);

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
            }
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Ошибка');
        }
    };

    const renderTask = (task: ShiftTask) => {
        const startTime = new Date(task.planned_start).toLocaleTimeString('ru-RU', {
            hour: '2-digit', minute: '2-digit',
        });
        const endTime = new Date(task.planned_end).toLocaleTimeString('ru-RU', {
            hour: '2-digit', minute: '2-digit',
        });

        const isDone = task.status === 'DONE';
        const isInProgress = task.status === 'IN_PROGRESS';

        return (
            <Card
                key={task.id}
                variant="outlined"
                sx={{
                    mb: 1,
                    borderLeft: isDone ? '4px solid #4caf50'
                        : isInProgress ? '4px solid #2196f3'
                            : task.is_carryover ? '4px solid #ff9800'
                                : '1px solid #e0e0e0',
                    bgcolor: task.is_carryover ? '#fff8e1' : 'white',
                }}
            >
                <CardContent sx={{ py: 1.5, px: 2, '&:last-child': { pb: 1.5 } }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 1 }}>
                        <Box sx={{ flexGrow: 1 }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                                <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
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
                                        icon={<HistoryIcon />}
                                        label="Переходящее"
                                        size="small"
                                        color="warning"
                                    />
                                )}
                            </Box>

                            <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                                {task.product_code} — {task.product_name}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                                {startTime} — {endTime} • {task.duration_minutes} мин
                            </Typography>

                            {task.linked_equipment_name && (
                                <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                                    + {task.linked_equipment_name}
                                </Typography>
                            )}

                            {task.material_load_at && (
                                <Chip
                                    label={`Сырьё загружено: ${new Date(task.material_load_at).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}`}
                                    size="small"
                                    color="info"
                                    variant="outlined"
                                    sx={{ mt: 0.5 }}
                                />
                            )}

                            {task.actual_qty && (
                                <Typography variant="caption" sx={{ display: 'block', mt: 0.5 }}>
                                    Факт: {task.actual_qty}
                                </Typography>
                            )}
                        </Box>

                        <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 0.5 }}>
                            <Chip
                                label={STATUS_LABELS[task.status]}
                                color={STATUS_COLORS[task.status]}
                                size="small"
                            />

                            <Box sx={{ display: 'flex', gap: 0.5, mt: 0.5 }}>
                                {task.task_role === 'REACTOR_OP' && !task.material_load_at && (
                                    <Tooltip title="Отметить загрузку сырья">
                                        <IconButton
                                            size="small"
                                            color="info"
                                            onClick={() => handleMaterialLoad(task)}
                                        >
                                            <PlayIcon fontSize="small" />
                                        </IconButton>
                                    </Tooltip>
                                )}
                                {task.status !== 'DONE' && (
                                    <Tooltip title="Отметить выполнение">
                                        <IconButton
                                            size="small"
                                            color="success"
                                            onClick={() => handleComplete(task)}
                                        >
                                            <CheckCircleIcon fontSize="small" />
                                        </IconButton>
                                    </Tooltip>
                                )}
                                <Tooltip title="Подробнее / изменить">
                                    <IconButton
                                        size="small"
                                        onClick={() => handleOpenFactDialog(task)}
                                    >
                                        <SaveIcon fontSize="small" />
                                    </IconButton>
                                </Tooltip>
                            </Box>
                        </Box>
                    </Box>
                </CardContent>
            </Card>
        );
    };

    return (
        <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2, flexWrap: 'wrap', gap: 2 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                    <ScheduleIcon color="primary" sx={{ fontSize: 32 }} />
                    <Typography variant="h4" component="h1" sx={{ fontWeight: 600, color: '#2c3e50' }}>
                        Рабочее место мастера
                    </Typography>
                </Box>
                <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                    <TextField
                        type="date"
                        size="small"
                        label="Дата смены"
                        value={selectedDate}
                        onChange={(e) => setSelectedDate(e.target.value)}
                        slotProps={{ inputLabel: { shrink: true } }}
                    />
                    <Button
                        variant="outlined"
                        startIcon={<RefreshIcon />}
                        onClick={() => loadShift(selectedDate)}
                    >
                        Обновить
                    </Button>
                </Box>
            </Box>

            {error && (
                <Alert severity="warning" sx={{ mb: 2 }} onClose={() => setError(null)}>
                    {error}
                </Alert>
            )}

            {loading && (
                <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
                    <CircularProgress />
                </Box>
            )}

            {!loading && currentShift && tasksData && (
                <>
                    <Card sx={{ mb: 2, bgcolor: '#f8f9fa' }}>
                        <CardContent sx={{ py: 1.5 }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
                                <Typography variant="h6" sx={{ fontWeight: 600 }}>
                                    {currentShift.name}
                                </Typography>
                                <Chip
                                    label={`${new Date(currentShift.starts_at).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })} — ${new Date(currentShift.ends_at).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}`}
                                    variant="outlined"
                                />
                                {!currentShift.is_working && (
                                    <Chip label="Нерабочая смена" color="default" />
                                )}
                                <Chip
                                    label={`Всего задач: ${tasksData.total_tasks}`}
                                    color="primary"
                                    variant="outlined"
                                />
                                {tasksData.carryover_count > 0 && (
                                    <Chip
                                        icon={<HistoryIcon />}
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

                    {tasksData.groups.length === 0 ? (
                        <Card>
                            <CardContent>
                                <Typography color="text.secondary" align="center">
                                    На эту смену нет заданий
                                </Typography>
                            </CardContent>
                        </Card>
                    ) : (
                        <Box sx={{ flexGrow: 1, overflow: 'auto' }}>
                            {tasksData.groups.map((group) => (
                                <Accordion
                                    key={group.equipment_id}
                                    defaultExpanded
                                    sx={{ mb: 1, boxShadow: '0 2px 6px rgba(0,0,0,0.08)' }}
                                >
                                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, width: '100%' }}>
                                            <Typography sx={{ fontWeight: 600 }}>
                                                {group.equipment_name}
                                            </Typography>
                                            {group.equipment_code && (
                                                <Chip
                                                    label={group.equipment_code}
                                                    size="small"
                                                    variant="outlined"
                                                />
                                            )}
                                            <Chip
                                                label={`${group.tasks.length} задач`}
                                                size="small"
                                                color="primary"
                                                variant="outlined"
                                                sx={{ ml: 'auto' }}
                                            />
                                        </Box>
                                    </AccordionSummary>
                                    <AccordionDetails>
                                        {group.tasks.map(renderTask)}
                                    </AccordionDetails>
                                </Accordion>
                            ))}
                        </Box>
                    )}
                </>
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

            <Dialog open={editDialogOpen} onClose={() => setEditDialogOpen(false)} maxWidth="sm" fullWidth>
                <DialogTitle sx={{ fontWeight: 600 }}>
                    {selectedTask && `${selectedTask.operation_name} — внести факт`}
                </DialogTitle>
                <DialogContent>
                    {selectedTask && (
                        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
                            <Box>
                                <Typography variant="body2" color="text.secondary">
                                    <b>Продукт:</b> {selectedTask.product_code} — {selectedTask.product_name}<br />
                                    <b>Оборудование:</b> {selectedTask.equipment_name}
                                    {selectedTask.linked_equipment_name && ` + ${selectedTask.linked_equipment_name}`}<br />
                                    <b>План:</b> {new Date(selectedTask.planned_start).toLocaleString('ru-RU')} — {new Date(selectedTask.planned_end).toLocaleString('ru-RU')}
                                </Typography>
                            </Box>

                            <Divider />

                            <TextField
                                label="Факт. начало"
                                type="datetime-local"
                                fullWidth
                                value={factForm.actual_start?.slice(0, 16) || ''}
                                onChange={(e) => setFactForm({ ...factForm, actual_start: e.target.value ? new Date(e.target.value).toISOString() : undefined })}
                                slotProps={{ inputLabel: { shrink: true } }}
                            />

                            <TextField
                                label="Факт. окончание"
                                type="datetime-local"
                                fullWidth
                                value={factForm.actual_end?.slice(0, 16) || ''}
                                onChange={(e) => setFactForm({ ...factForm, actual_end: e.target.value ? new Date(e.target.value).toISOString() : undefined })}
                                slotProps={{ inputLabel: { shrink: true } }}
                            />

                            <TextField
                                label="Загрузка сырья в реактор"
                                type="datetime-local"
                                fullWidth
                                value={factForm.material_load_at?.slice(0, 16) || ''}
                                onChange={(e) => setFactForm({ ...factForm, material_load_at: e.target.value ? new Date(e.target.value).toISOString() : undefined })}
                                slotProps={{ inputLabel: { shrink: true } }}
                            />

                            <TextField
                                label="Факт. количество (бутылок)"
                                type="number"
                                fullWidth
                                value={factForm.actual_qty || ''}
                                onChange={(e) => setFactForm({ ...factForm, actual_qty: e.target.value ? Number(e.target.value) : undefined })}
                            />

                            <FormControl fullWidth>
                                <InputLabel>Статус</InputLabel>
                                <Select
                                    value={factForm.status || 'PLANNED'}
                                    label="Статус"
                                    onChange={(e) => setFactForm({ ...factForm, status: e.target.value as ShiftTaskStatus })}
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
                    <Button onClick={handleSaveFact} variant="contained" startIcon={<SaveIcon />}>
                        Сохранить
                    </Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
};

export default ShiftPage;