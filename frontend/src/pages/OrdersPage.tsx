// frontend/src/pages/OrdersPage.tsx
import React, {useCallback, useEffect, useState} from 'react';
import {
    Alert,
    Box,
    Button,
    Card,
    CardContent,
    Chip,
    CircularProgress,
    FormControl,
    IconButton,
    InputLabel,
    MenuItem,
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
import {Add as AddIcon, Autorenew as AutoSplitIcon, Delete as DeleteIcon, Edit as EditIcon,} from '@mui/icons-material';
import type {ColDef, GridReadyEvent} from 'ag-grid-community';
import {AllCommunityModule, ModuleRegistry} from 'ag-grid-community';
import {ordersApi, productsApi} from '../services/api';
import type {ProductionOrder} from '../types';
import DraggableDialog from '../components/common/DraggableDialog';
import AppAgGrid from '../components/common/AppAgGrid';

ModuleRegistry.registerModules([AllCommunityModule]);

const OrdersPage: React.FC = () => {
    const [orders, setOrders] = useState<ProductionOrder[]>([]);
    const [products, setProducts] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);

    // Модалка создания/редактирования заказа
    const [dialogOpen, setDialogOpen] = useState(false);
    const [editOrder, setEditOrder] = useState<ProductionOrder | null>(null);
    const [formData, setFormData] = useState({
        product_id: '',
        target_qty: 0,
        due_date: '',
        priority: 5,
        comment: '',
    });
    const [saving, setSaving] = useState(false);

    // Итерация 33: Модалка оптимального распределения
    const [splitDialogOpen, setSplitDialogOpen] = useState(false);
    const [splitOrder, setSplitOrder] = useState<ProductionOrder | null>(null);
    const [splitStrategy, setSplitStrategy] = useState('greedy_makespan');
    const [splitMaxFill, setSplitMaxFill] = useState(0.70);
    const [splitLoading, setSplitLoading] = useState(false);
    const [splitResult, setSplitResult] = useState<any>(null);

    const loadData = useCallback(async () => {
        setLoading(true);
        try {
            const [ordersData, productsData] = await Promise.all([
                ordersApi.getAll(),
                productsApi.getAll(),
            ]);
            setOrders(ordersData);
            // Берем только ГП для выпадающего списка
            setProducts(productsData.filter((p: any) => p.type === 'GP'));
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Ошибка загрузки данных');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        loadData();
    }, [loadData]);

    const handleOpenCreate = () => {
        setEditOrder(null);
        setFormData({
            product_id: products[0]?.id || '',
            target_qty: 0,
            due_date: new Date().toISOString().slice(0, 16),
            priority: 5,
            comment: '',
        });
        setDialogOpen(true);
    };

    const handleOpenEdit = (order: ProductionOrder) => {
        setEditOrder(order);
        setFormData({
            product_id: order.product_id,
            target_qty: order.target_qty,
            due_date: order.due_date ? new Date(order.due_date).toISOString().slice(0, 16) : '',
            priority: order.priority,
            comment: order.comment || '',
        });
        setDialogOpen(true);
    };

    const handleSave = async () => {
        setSaving(true);
        try {
            if (editOrder) {
                await ordersApi.update(editOrder.id, formData);
                setSuccess('Заказ обновлен');
            } else {
                await ordersApi.create(formData);
                setSuccess('Заказ создан');
            }
            setDialogOpen(false);
            await loadData();
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Ошибка сохранения');
        } finally {
            setSaving(false);
        }
    };

    const handleDelete = async (id: string) => {
        if (!window.confirm('Удалить заказ? Партии также будут удалены.')) return;
        try {
            await ordersApi.delete(id);
            setSuccess('Заказ удален');
            await loadData();
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Ошибка удаления');
        }
    };

    // Итерация 33: Запуск авто-распределения
    const handleAutoSplit = async () => {
        if (!splitOrder) return;
        setSplitLoading(true);
        setSplitResult(null);
        try {
            const res = await ordersApi.autoSplitOptimized(splitOrder.id, {
                strategy: splitStrategy,
                max_fill_percent: splitMaxFill,
            });
            setSplitResult(res);
            await loadData();
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Ошибка распределения');
            setSplitDialogOpen(false);
        } finally {
            setSplitLoading(false);
        }
    };

    const columnDefs: ColDef<ProductionOrder>[] = [
        { field: 'product_name', headerName: 'Продукт', flex: 1, minWidth: 200 },
        { field: 'target_qty', headerName: 'Объем', width: 120 },
        {
            field: 'batches_count',
            headerName: 'Партий',
            width: 100,
            cellRenderer: (params: any) => (
                <Chip
                    label={params.value}
                    size="small"
                    color={params.value > 0 ? 'primary' : 'default'}
                    variant="outlined"
                />
            ),
        },
        {
            field: 'due_date',
            headerName: 'Срок',
            width: 160,
            valueFormatter: (p) => p.value ? new Date(p.value).toLocaleDateString('ru-RU') : '—',
        },
        { field: 'priority', headerName: 'Приоритет', width: 100 },
        {
            field: 'status',
            headerName: 'Статус',
            width: 130,
            cellRenderer: (params: any) => {
                const colors: any = { NEW: 'info', IN_PROGRESS: 'warning', DONE: 'success' };
                return <Chip label={params.value} color={colors[params.value] || 'default'} size="small" />;
            },
        },
        {
            headerName: 'Действия',
            width: 180,
            sortable: false,
            filter: false,
            cellRenderer: (params: any) => {
                const order = params.data as ProductionOrder;
                return (
                    <Box sx={{ display: 'flex', gap: 0.5, alignItems: 'center' }}>
                        <Tooltip title="Редактировать">
                            <IconButton size="small" onClick={() => handleOpenEdit(order)}>
                                <EditIcon fontSize="small" />
                            </IconButton>
                        </Tooltip>
                        <Tooltip title="Оптимально распределить партии">
                            <IconButton
                                size="small"
                                color="info"
                                onClick={() => {
                                    setSplitOrder(order);
                                    setSplitResult(null);
                                    setSplitDialogOpen(true);
                                }}
                            >
                                <AutoSplitIcon fontSize="small" />
                            </IconButton>
                        </Tooltip>
                        <Tooltip title="Удалить">
                            <IconButton size="small" color="error" onClick={() => handleDelete(order.id)}>
                                <DeleteIcon fontSize="small" />
                            </IconButton>
                        </Tooltip>
                    </Box>
                );
            },
        },
    ];

    if (loading) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', mt: 8 }}>
                <CircularProgress />
            </Box>
        );
    }

    return (
        <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Typography variant="h4" component="h1" sx={{ fontWeight: 600, color: '#2c3e50' }}>
                    Заказы
                </Typography>
                <Button variant="contained" startIcon={<AddIcon />} onClick={handleOpenCreate}>
                    Новый заказ
                </Button>
            </Box>

            {error && (
                <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
                    {error}
                </Alert>
            )}

            {success && (
                <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess(null)}>
                    {success}
                </Alert>
            )}

            <Card sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
                <CardContent sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', p: 1 }}>
                    <Box sx={{ flexGrow: 1, width: '100%', minHeight: 0 }}>
                        <AppAgGrid
                            rowData={orders}
                            columnDefs={columnDefs}
                            defaultColDef={{ sortable: true, filter: true, resizable: true }}
                            onGridReady={(params: GridReadyEvent) => params.api.sizeColumnsToFit()}
                            getRowId={(params: any) => params.data.id}
                        />
                    </Box>
                </CardContent>
            </Card>

            {/* Диалог создания/редактирования */}
            <DraggableDialog
                open={dialogOpen}
                onClose={() => setDialogOpen(false)}
                title={editOrder ? 'Редактировать заказ' : 'Новый заказ'}
                initialWidth={500}
                initialHeight="auto"
                minWidth={400}
                minHeight={300}
                actions={
                    <>
                        <Button onClick={() => setDialogOpen(false)}>Отмена</Button>
                        <Button onClick={handleSave} variant="contained" disabled={saving}>
                            {saving ? 'Сохранение...' : 'Сохранить'}
                        </Button>
                    </>
                }
            >
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
                    <FormControl fullWidth>
                        <InputLabel>Продукт (ГП)</InputLabel>
                        <Select
                            value={formData.product_id}
                            label="Продукт (ГП)"
                            onChange={(e) => setFormData({ ...formData, product_id: e.target.value })}
                        >
                            {products.map((p) => (
                                <MenuItem key={p.id} value={p.id}>
                                    {p.name}
                                </MenuItem>
                            ))}
                        </Select>
                    </FormControl>
                    <TextField
                        label="Целевой объем (шт)"
                        type="number"
                        fullWidth
                        value={formData.target_qty}
                        onChange={(e) => setFormData({ ...formData, target_qty: Number(e.target.value) })}
                    />
                    <TextField
                        label="Срок исполнения"
                        type="datetime-local"
                        fullWidth
                        value={formData.due_date}
                        onChange={(e) => setFormData({ ...formData, due_date: e.target.value })}
                        slotProps={{ inputLabel: { shrink: true } }}
                    />
                    <TextField
                        label="Приоритет (1-10)"
                        type="number"
                        fullWidth
                        value={formData.priority}
                        onChange={(e) => setFormData({ ...formData, priority: Number(e.target.value) })}
                    />
                    <TextField
                        label="Комментарий"
                        multiline
                        rows={2}
                        fullWidth
                        value={formData.comment}
                        onChange={(e) => setFormData({ ...formData, comment: e.target.value })}
                    />
                </Box>
            </DraggableDialog>

            {/* Итерация 33: Диалог оптимального распределения */}
            <DraggableDialog
                open={splitDialogOpen}
                onClose={() => setSplitDialogOpen(false)}
                title="Оптимальное распределение заказа"
                initialWidth={700}
                initialHeight="auto"
                minWidth={500}
                minHeight={300}
                actions={
                    <>
                        <Button onClick={() => setSplitDialogOpen(false)}>
                            {splitResult ? 'Закрыть' : 'Отмена'}
                        </Button>
                        {!splitResult && (
                            <Button
                                onClick={handleAutoSplit}
                                variant="contained"
                                disabled={splitLoading}
                                startIcon={splitLoading ? <CircularProgress size={20} /> : <AutoSplitIcon />}
                            >
                                {splitLoading ? 'Распределение...' : 'Распределить'}
                            </Button>
                        )}
                    </>
                }
            >
                {!splitResult ? (
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
                        <Alert severity="info">
                            Заказ «{splitOrder?.product_name}» ({splitOrder?.target_qty} шт) будет разбит на партии
                            и распределен между реакторами, способными варить этот продукт.
                        </Alert>

                        <FormControl fullWidth>
                            <InputLabel>Стратегия</InputLabel>
                            <Select
                                value={splitStrategy}
                                label="Стратегия"
                                onChange={(e) => setSplitStrategy(e.target.value)}
                            >
                                <MenuItem value="greedy_makespan">Greedy Makespan (балансировка)</MenuItem>
                                <MenuItem value="proportional">Proportional (пропорционально)</MenuItem>
                                <MenuItem value="round_robin">Round Robin (по очереди)</MenuItem>
                                <MenuItem value="equal_split">Equal Split (равные партии)</MenuItem>
                            </Select>
                        </FormControl>

                        <TextField
                            label="Максимальная загрузка реактора"
                            type="number"
                            value={splitMaxFill}
                            onChange={(e) => setSplitMaxFill(Number(e.target.value))}
                            slotProps={{ htmlInput: { step: 0.05, min: 0.1, max: 1.0 } }}
                            helperText="По ТЗ обычно 0.70 (70%)"
                        />

                        {splitOrder?.batches_count && splitOrder.batches_count > 0 ? (
                            <Alert severity="warning">
                                У заказа уже есть {splitOrder.batches_count} партий.
                                Удалите их перед созданием новых, иначе сервер вернет ошибку 409.
                            </Alert>
                        ) : null}
                    </Box>
                ) : (
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
                        <Alert severity="success">
                            {splitResult.message}
                        </Alert>

                        <Typography variant="subtitle2">Распределение по реакторам:</Typography>
                        <TableContainer component={Box} sx={{ border: '1px solid #e0e0e0', borderRadius: 1 }}>
                            <Table size="small">
                                <TableHead>
                                    <TableRow sx={{ bgcolor: '#f5f5f5' }}>
                                        <TableCell>Реактор</TableCell>
                                        <TableCell align="right">Партий</TableCell>
                                        <TableCell align="right">Всего, кг</TableCell>
                                        <TableCell align="right">Макс. партия</TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {splitResult.per_reactor.map((r: any) => (
                                        <TableRow key={r.equipment_id}>
                                            <TableCell>{r.equipment_name}</TableCell>
                                            <TableCell align="right">{r.batches_count}</TableCell>
                                            <TableCell align="right">{r.total_volume_kg.toFixed(0)}</TableCell>
                                            <TableCell align="right">{r.max_batch_volume.toFixed(0)}</TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </TableContainer>
                    </Box>
                )}
            </DraggableDialog>
        </Box>
    );
};

export default OrdersPage;