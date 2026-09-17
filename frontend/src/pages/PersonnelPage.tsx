// frontend/src/pages/PersonnelPage.tsx
import React, {useCallback, useEffect, useState} from 'react';
import {
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
    IconButton,
    LinearProgress,
    Paper,
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
    AcUnit as AcUnitIcon,
    Cancel as CancelIcon,
    Edit as EditIcon,
    Factory as FactoryIcon,
    LocalFireDepartment as LocalFireDepartmentIcon,
    Lock as LockIcon,
    Person as PersonIcon,
    PrecisionManufacturing as PrecisionManufacturingIcon,
    Refresh as RefreshIcon,
    Save as SaveIcon,
    Science as ScienceIcon,
} from '@mui/icons-material';
import {personnelApi} from '../services/api';
import {usePlan} from '../context/PlainContext';
import type {PersonnelPool, PersonnelPoolList, PersonnelPoolType} from '../types';

// ==========================================
// КОНСТАНТЫ
// ==========================================

const POOL_TYPE_LABELS: Record<PersonnelPoolType, string> = {
    REACTOR_OPERATOR: 'Аппаратчики реакторов',
    LINE_OPERATOR: 'Операторы линий розлива',
    MANUAL_OPERATOR: 'Операторы ручной станции',
    LAB: 'Лаборатория',
    COOLING_ZONE: 'Зона охлаждения',
    BOILER: 'Бойлер',
};

const POOL_TYPE_COLORS: Record<PersonnelPoolType, string> = {
    REACTOR_OPERATOR: '#3498db',
    LINE_OPERATOR: '#2ecc71',
    MANUAL_OPERATOR: '#e67e22',
    LAB: '#9b59b6',
    COOLING_ZONE: '#00bcd4',
    BOILER: '#795548',
};

const POOL_TYPE_ICONS: Record<PersonnelPoolType, React.ReactNode> = {
    REACTOR_OPERATOR: <FactoryIcon fontSize="small" />,
    LINE_OPERATOR: <PrecisionManufacturingIcon fontSize="small" />,
    MANUAL_OPERATOR: <PrecisionManufacturingIcon fontSize="small" />,
    LAB: <ScienceIcon fontSize="small" />,
    COOLING_ZONE: <AcUnitIcon fontSize="small" />,
    BOILER: <LocalFireDepartmentIcon fontSize="small" />,
};

// ==========================================
// КОМПОНЕНТ
// ==========================================

const PersonnelPage: React.FC = () => {
    const { currentVersionId, currentPlanName } = usePlan();
    const isReadOnly = currentVersionId !== null;

    const [data, setData] = useState<PersonnelPoolList | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Диалог редактирования
    const [editDialogOpen, setEditDialogOpen] = useState(false);
    const [editingPool, setEditingPool] = useState<PersonnelPool | null>(null);
    const [editCapacity, setEditCapacity] = useState<number>(0);
    const [editName, setEditName] = useState<string>('');
    const [editComment, setEditComment] = useState<string>('');
    const [saving, setSaving] = useState(false);

    const loadData = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const result = await personnelApi.listPools(currentVersionId || undefined);
            setData(result);
        } catch (err: any) {
            const detail = err.response?.data?.detail;
            setError(typeof detail === 'string' ? detail : 'Ошибка загрузки пулов');
        } finally {
            setLoading(false);
        }
    }, [currentVersionId]);

    useEffect(() => {
        loadData();
    }, [loadData]);

    const handleOpenEdit = (pool: PersonnelPool) => {
        if (isReadOnly) return;
        setEditingPool(pool);
        setEditCapacity(pool.capacity);
        setEditName(pool.name);
        setEditComment(pool.comment || '');
        setEditDialogOpen(true);
    };

    const handleSave = async () => {
        if (!editingPool) return;
        setSaving(true);
        try {
            await personnelApi.updatePool(editingPool.id, {
                capacity: editCapacity,
                name: editName,
                comment: editComment,
            });
            setEditDialogOpen(false);
            await loadData();
        } catch (err: any) {
            const detail = err.response?.data?.detail;
            setError(typeof detail === 'string' ? detail : 'Ошибка сохранения');
        } finally {
            setSaving(false);
        }
    };

    const getLoadColor = (loadPercent: number): 'success' | 'warning' | 'error' => {
        if (loadPercent >= 100) return 'error';
        if (loadPercent >= 75) return 'warning';
        return 'success';
    };

    if (loading) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', mt: 8 }}>
                <CircularProgress />
            </Box>
        );
    }

    return (
        <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            {/* Заголовок */}
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2, flexWrap: 'wrap', gap: 2 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                    <PersonIcon color="primary" sx={{ fontSize: 32 }} />
                    <Typography variant="h4" component="h1" sx={{ fontWeight: 600, color: '#2c3e50' }}>
                        Персонал
                    </Typography>
                    {isReadOnly && (
                        <Chip
                            icon={<LockIcon />}
                            label={`Просмотр: ${currentPlanName}`}
                            color="info"
                            variant="filled"
                        />
                    )}
                </Box>
                <Button
                    variant="outlined"
                    startIcon={<RefreshIcon />}
                    onClick={loadData}
                >
                    Обновить
                </Button>
            </Box>

            {error && (
                <Alert severity="warning" sx={{ mb: 2 }} onClose={() => setError(null)}>
                    {error}
                </Alert>
            )}

            {/* Сводка */}
            {data && (
                <Card sx={{ mb: 2, bgcolor: '#f8f9fa' }}>
                    <CardContent sx={{ py: 1.5 }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
                            <Chip
                                icon={<PersonIcon />}
                                label={`Пулов: ${data.pools.length}`}
                                color="primary"
                                variant="outlined"
                            />
                            <Chip
                                label={`Всего операторов: ${data.total_capacity}`}
                                color="secondary"
                                variant="outlined"
                            />
                            <Chip
                                label={`Задач в плане: ${data.total_scheduled}`}
                                variant="outlined"
                            />
                            {data.version_name && (
                                <Chip
                                    label={`Версия: ${data.version_name}`}
                                    color="info"
                                    variant="outlined"
                                />
                            )}
                        </Box>
                    </CardContent>
                </Card>
            )}

            {/* Таблица пулов */}
            <TableContainer component={Paper} sx={{ flexGrow: 1 }}>
                <Table>
                    <TableHead>
                        <TableRow sx={{ bgcolor: '#2c3e50' }}>
                            <TableCell sx={{ color: 'white', fontWeight: 600 }}>Тип</TableCell>
                            <TableCell sx={{ color: 'white', fontWeight: 600 }}>Наименование</TableCell>
                            <TableCell sx={{ color: 'white', fontWeight: 600 }} align="right">
                                Capacity
                            </TableCell>
                            <TableCell sx={{ color: 'white', fontWeight: 600 }} align="right">
                                Задач в плане
                            </TableCell>
                            <TableCell sx={{ color: 'white', fontWeight: 600 }} align="right">
                                Пик
                            </TableCell>
                            <TableCell sx={{ color: 'white', fontWeight: 600 }} align="center">
                                Загрузка
                            </TableCell>
                            <TableCell sx={{ color: 'white', fontWeight: 600 }} align="center">
                                Действия
                            </TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {data?.pools.map((pool) => {
                            const color = POOL_TYPE_COLORS[pool.type] || '#95a5a6';
                            const loadColor = getLoadColor(pool.load_percent);

                            return (
                                <TableRow key={pool.id} hover>
                                    <TableCell>
                                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                            <Box
                                                sx={{
                                                    width: 32,
                                                    height: 32,
                                                    borderRadius: '50%',
                                                    bgcolor: color,
                                                    color: 'white',
                                                    display: 'flex',
                                                    alignItems: 'center',
                                                    justifyContent: 'center',
                                                }}
                                            >
                                                {POOL_TYPE_ICONS[pool.type]}
                                            </Box>
                                            <Chip
                                                label={pool.type}
                                                size="small"
                                                variant="outlined"
                                                sx={{ fontFamily: 'monospace', fontSize: '0.7rem' }}
                                            />
                                        </Box>
                                    </TableCell>
                                    <TableCell>
                                        <Typography variant="body2" sx={{ fontWeight: 600 }}>
                                            {pool.name}
                                        </Typography>
                                        {pool.comment && (
                                            <Typography variant="caption" color="text.secondary">
                                                {pool.comment}
                                            </Typography>
                                        )}
                                    </TableCell>
                                    <TableCell align="right">
                                        <Typography variant="h6" sx={{ fontWeight: 700, color }}>
                                            {pool.capacity}
                                        </Typography>
                                    </TableCell>
                                    <TableCell align="right">
                                        <Typography variant="body2">
                                            {pool.scheduled_count}
                                        </Typography>
                                    </TableCell>
                                    <TableCell align="right">
                                        <Typography
                                            variant="body2"
                                            sx={{
                                                fontWeight: 600,
                                                color: pool.peak_concurrent > pool.capacity ? 'error.main' : 'inherit',
                                            }}
                                        >
                                            {pool.peak_concurrent}
                                        </Typography>
                                    </TableCell>
                                    <TableCell align="center" sx={{ minWidth: 200 }}>
                                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                            <Box sx={{ flexGrow: 1 }}>
                                                <LinearProgress
                                                    variant="determinate"
                                                    value={Math.min(pool.load_percent, 100)}
                                                    color={loadColor}
                                                    sx={{ height: 8, borderRadius: 1 }}
                                                />
                                            </Box>
                                            <Typography
                                                variant="caption"
                                                sx={{ minWidth: 50, textAlign: 'right', fontWeight: 600 }}
                                            >
                                                {pool.load_percent.toFixed(0)}%
                                            </Typography>
                                        </Box>
                                    </TableCell>
                                    <TableCell align="center">
                                        {!isReadOnly && (
                                            <Tooltip title="Редактировать">
                                                <IconButton
                                                    size="small"
                                                    color="primary"
                                                    onClick={() => handleOpenEdit(pool)}
                                                >
                                                    <EditIcon fontSize="small" />
                                                </IconButton>
                                            </Tooltip>
                                        )}
                                    </TableCell>
                                </TableRow>
                            );
                        })}
                    </TableBody>
                </Table>
            </TableContainer>

            <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block', textAlign: 'center' }}>
                💡 «Пик» — максимальное одновременное использование пула. Не должен превышать Capacity.
                {isReadOnly ? ' Режим просмотра — редактирование недоступно.' : ' Нажмите ✏ для изменения capacity.'}
            </Typography>

            {/* Диалог редактирования */}
            <Dialog open={editDialogOpen} onClose={() => setEditDialogOpen(false)} maxWidth="sm" fullWidth>
                <DialogTitle sx={{ fontWeight: 600 }}>
                    {editingPool && `Редактировать: ${POOL_TYPE_LABELS[editingPool.type]}`}
                </DialogTitle>
                <DialogContent>
                    {editingPool && (
                        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
                            <Alert severity="info">
                                <Box>
                                    <b>Текущая загрузка:</b> {editingPool.scheduled_count} задач,
                                    пик {editingPool.peak_concurrent} из {editingPool.capacity}.
                                </Box>
                                {editingPool.peak_concurrent > editCapacity && (
                                    <Box sx={{ mt: 1, color: 'error.main' }}>
                                        ⚠️ Новый capacity ({editCapacity}) меньше пика ({editingPool.peak_concurrent}).
                                        Возможно, потребуется перепланирование.
                                    </Box>
                                )}
                            </Alert>

                            <TextField
                                label="Наименование"
                                fullWidth
                                value={editName}
                                onChange={(e) => setEditName(e.target.value)}
                            />

                            <TextField
                                label="Capacity (количество операторов)"
                                type="number"
                                fullWidth
                                value={editCapacity}
                                onChange={(e) => setEditCapacity(Number(e.target.value))}
                                slotProps={{
                                    htmlInput: { min: 0, step: 1 },
                                }}
                                helperText="Сколько операций может выполняться одновременно"
                            />

                            <TextField
                                label="Комментарий"
                                fullWidth
                                multiline
                                rows={2}
                                value={editComment}
                                onChange={(e) => setEditComment(e.target.value)}
                            />
                        </Box>
                    )}
                </DialogContent>
                <DialogActions>
                    <Button
                        onClick={() => setEditDialogOpen(false)}
                        startIcon={<CancelIcon />}
                        disabled={saving}
                    >
                        Отмена
                    </Button>
                    <Button
                        onClick={handleSave}
                        variant="contained"
                        startIcon={<SaveIcon />}
                        disabled={saving}
                    >
                        {saving ? 'Сохранение...' : 'Сохранить'}
                    </Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
};

export default PersonnelPage;