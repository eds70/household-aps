// src/pages/SchedulePage.tsx
import React, { useState, useEffect } from 'react';
import { usePlan, type PlanVersion } from '../context/PlainContext';
import { AgGridReact } from 'ag-grid-react';
import { ModuleRegistry, AllCommunityModule } from 'ag-grid-community';
import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-alpine.css';
import type { ColDef, GridReadyEvent } from 'ag-grid-community';
import {
    Box, Button, Card, CardContent, TextField, Typography, Alert,
    CircularProgress, Dialog, DialogTitle, DialogContent, DialogActions,
    FormControl, InputLabel, Select, MenuItem, IconButton, Tooltip
} from '@mui/material';
import {
    PlayArrow as PlayIcon, Add as AddIcon,
    Delete as DeleteIcon, Visibility as ViewIcon, History as HistoryIcon
} from '@mui/icons-material';
import { scheduleApi } from '../services/api';
import axios from 'axios';
import { API_BASE_URL } from '../config';

ModuleRegistry.registerModules([AllCommunityModule]);

const VERSION_TYPE_LABELS: Record<string, string> = {
    MONTHLY: 'Месячный (ОКП)',
    SHIFT: 'Посменный',
    WHAT_IF: 'Сценарий "что если"',
};

const SchedulePage: React.FC = () => {
    const { versions, setPlan, loadVersions, currentVersionId } = usePlan();

    const [horizonHours, setHorizonHours] = useState(2160);
    const [solverTimeout, setSolverTimeout] = useState(120);
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState<any>(null);
    const [error, setError] = useState<string | null>(null);

    // Диалог нового плана
    const [newPlanDialogOpen, setNewPlanDialogOpen] = useState(false);
    const [newPlanForm, setNewPlanForm] = useState({
        name: '',
        version_type: 'MONTHLY',
        comment: '',
    });
    const [creatingPlan, setCreatingPlan] = useState(false);

    useEffect(() => {
        loadVersions();
    }, []);

    const handleBuildSchedule = async () => {
        setLoading(true);
        setError(null);
        setResult(null);
        try {
            const data = await scheduleApi.build({
                horizon_hours: horizonHours,
                timeout_seconds: solverTimeout
            });
            setResult(data);
            await loadVersions(); // Обновляем список после построения
        } catch (err: any) {
            // ✅ Безопасное извлечение сообщения об ошибке
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

    const handleSavePlan = async () => {
        setError(null);
        try {
            const res = await axios.post(`${API_BASE_URL}/api/v1/schedule/save`);
            await loadVersions();
            setPlan(res.data.version_id, res.data.message.replace("План '", "").replace("' успешно сохранен", ""));
            alert("План успешно сохранен!");
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Ошибка сохранения плана');
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
        if (!window.confirm(`Удалить план "${version.name}"? Это действие необратимо и удалит все связанные задачи.`)) return;
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
            valueFormatter: (p) => p.value ? new Date(p.value).toLocaleString('ru-RU') : '—'
        },
        {
            headerName: 'Комментарий',
            field: 'comment',
            flex: 1,
            valueFormatter: (p) => p.value || '—'
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

    return (
        <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Typography variant="h4" component="h1" sx={{ fontWeight: 600, color: '#2c3e50' }}>
                    Планирование производства
                </Typography>
                <Box sx={{ display: 'flex', gap: 1 }}>
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

            {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>{error}</Alert>}

            <Card sx={{ mb: 2 }}>
                <CardContent>
                    <Typography variant="h6" gutterBottom sx={{ fontWeight: 600 }}>
                        Параметры расчёта
                    </Typography>
                    <Box sx={{ display: 'flex', gap: 2, mb: 2, flexWrap: 'wrap' }}>
                        <TextField
                            label="Горизонт (часы)"
                            type="number"
                            value={horizonHours}
                            onChange={(e) => setHorizonHours(Number(e.target.value))}
                            size="small"
                        />
                        <TextField
                            label="Таймаут solver (сек)"
                            type="number"
                            value={solverTimeout}
                            onChange={(e) => setSolverTimeout(Number(e.target.value))}
                            size="small"
                        />
                    </Box>
                    <Box sx={{ display: 'flex', gap: 2 }}>
                        <Button
                            variant="contained"
                            size="large"
                            startIcon={loading ? <CircularProgress size={20} /> : <PlayIcon />}
                            onClick={handleBuildSchedule}
                            disabled={loading}
                        >
                            {loading ? 'Расчёт...' : 'Построить план'}
                        </Button>
                        {result && (
                            <Button
                                variant="outlined"
                                color="success"
                                size="large"
                                onClick={handleSavePlan}
                            >
                                Сохранить как версию
                            </Button>
                        )}
                    </Box>
                </CardContent>
            </Card>

            {result && (
                <Alert severity="success" sx={{ mb: 2 }}>
                    ✅ Расчёт завершён: {result.total_tasks} задач, Makespan: {result.makespan_hours.toFixed(1)} ч
                </Alert>
            )}

            <Card sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
                <CardContent sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', p: 2 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                        <HistoryIcon color="primary" />
                        <Typography variant="h6" sx={{ fontWeight: 600 }}>
                            История планов ({versions.length})
                        </Typography>
                    </Box>
                    <Box className="ag-theme-alpine" sx={{ flexGrow: 1, width: '100%' }}>
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

            {/* Диалог нового плана */}
            <Dialog open={newPlanDialogOpen} onClose={() => setNewPlanDialogOpen(false)} maxWidth="sm" fullWidth>
                <DialogTitle sx={{ fontWeight: 600 }}>Создать новый план</DialogTitle>
                <DialogContent>
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
                        <TextField
                            label="Название плана"
                            fullWidth
                            value={newPlanForm.name}
                            onChange={(e) => setNewPlanForm({ ...newPlanForm, name: e.target.value })}
                            placeholder="Например: План на октябрь 2026"
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
        </Box>
    );
};

export default SchedulePage;