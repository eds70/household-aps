// frontend/src/pages/OrdersPage.tsx
import React, { useState, useEffect } from 'react';
import {
    Box,
    Button,
    Card,
    CardContent,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    FormControl,
    InputLabel,
    MenuItem,
    Select,
    TextField,
    Typography,
    IconButton,
    CircularProgress,
    Alert,
    Chip,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Paper,
} from '@mui/material';
import {
    Add as AddIcon,
    Delete as DeleteIcon,
    ShoppingCart as CartIcon,
    ExpandMore as ExpandMoreIcon,
    ExpandLess as ExpandLessIcon,
    AutoFixHigh as AutoSplitIcon,
} from '@mui/icons-material';
import { AgGridReact } from 'ag-grid-react';
import { ModuleRegistry, AllCommunityModule } from 'ag-grid-community';
import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-alpine.css';
import type { ColDef, GridReadyEvent } from 'ag-grid-community';
import type { ProductionOrder, Batch, OrderStatus } from '../types';
import { ordersApi, productsApi, equipmentApi } from '../services/api';

ModuleRegistry.registerModules([AllCommunityModule]);

const STATUS_LABELS: Record<OrderStatus, string> = {
    PLANNED: 'Запланирован',
    IN_PROGRESS: 'В производстве',
    DONE: 'Выполнен',
    CANCELLED: 'Отменён',
};

const STATUS_COLORS: Record<OrderStatus, 'default' | 'primary' | 'success' | 'error'> = {
    PLANNED: 'primary',
    IN_PROGRESS: 'default',
    DONE: 'success',
    CANCELLED: 'error',
};

const OrdersPage: React.FC = () => {
    const [orders, setOrders] = useState<ProductionOrder[]>([]);
    const [products, setProducts] = useState<any[]>([]);
    const [equipment, setEquipment] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [dialogOpen, setDialogOpen] = useState(false);
    const [expandedOrderId, setExpandedOrderId] = useState<string | null>(null);
    const [orderBatches, setOrderBatches] = useState<Record<string, Batch[]>>({});

    const [formData, setFormData] = useState({
        product_id: '',
        target_qty: 0,
        due_date: '',
        priority: 5,
        comment: '',
    });

    const [splitDialogOpen, setSplitDialogOpen] = useState(false);
    const [splitOrderId, setSplitOrderId] = useState<string | null>(null);
    const [splitEquipmentId, setSplitEquipmentId] = useState('');
    const [splitMaxFill, setSplitMaxFill] = useState(0.70);

    useEffect(() => {
        loadData();
    }, []);

    const loadData = async () => {
        setLoading(true);
        setError(null);
        try {
            const [ordersData, productsData, equipmentData] = await Promise.all([
                ordersApi.getAll(),
                productsApi.getAll(),
                equipmentApi.getAll(),
            ]);
            setOrders(ordersData);
            setProducts(productsData);
            setEquipment(equipmentData);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Ошибка загрузки данных');
        } finally {
            setLoading(false);
        }
    };

    const columnDefs: ColDef<ProductionOrder>[] = [
        {
            headerName: 'Код продукта',
            field: 'product_code',
            width: 130,
        },
        {
            headerName: 'Продукт',
            field: 'product_name',
            flex: 2,
            minWidth: 200,
        },
        {
            headerName: 'Целевое кол-во',
            field: 'target_qty',
            width: 130,
            type: 'numericColumn',
        },
        {
            headerName: 'Дедлайн',
            field: 'due_date',
            width: 170,
            valueFormatter: (params) =>
                params.value ? new Date(params.value).toLocaleString('ru-RU') : '—',
        },
        {
            headerName: 'Приоритет',
            field: 'priority',
            width: 100,
            type: 'numericColumn',
        },
        {
            headerName: 'Статус',
            field: 'status',
            width: 150,
            cellRenderer: (params: any) => {
                const status = params.value as OrderStatus;
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
            headerName: 'Партий',
            field: 'batches_count',
            width: 90,
            type: 'numericColumn',
        },
        {
            headerName: 'Действия',
            width: 220,
            cellRenderer: (params: any) => (
                <Box sx={{ display: 'flex', gap: 0.5 }}>
                    <IconButton
                        size="small"
                        onClick={() => handleToggleExpand(params.data.id)}
                    >
                        {expandedOrderId === params.data.id ? (
                            <ExpandLessIcon />
                        ) : (
                            <ExpandMoreIcon />
                        )}
                    </IconButton>
                    <Button
                        size="small"
                        variant="outlined"
                        startIcon={<AutoSplitIcon />}
                        onClick={() => handleOpenSplit(params.data.id)}
                    >
                        Разбить
                    </Button>
                    <IconButton
                        color="error"
                        size="small"
                        onClick={() => handleDelete(params.data.id)}
                    >
                        <DeleteIcon fontSize="small" />
                    </IconButton>
                </Box>
            ),
        },
    ];

    const defaultColDef: ColDef = {
        sortable: true,
        filter: true,
        resizable: true,
    };

    const getRowId = (params: any) => params.data.id;

    const handleToggleExpand = async (orderId: string) => {
        if (expandedOrderId === orderId) {
            setExpandedOrderId(null);
            return;
        }
        setExpandedOrderId(orderId);
        if (!orderBatches[orderId]) {
            try {
                const batches = await ordersApi.getBatches(orderId);
                setOrderBatches((prev) => ({ ...prev, [orderId]: batches }));
            } catch (err: any) {
                setError(err.response?.data?.detail || 'Ошибка загрузки партий');
            }
        }
    };

    const handleOpenSplit = (orderId: string) => {
        setSplitOrderId(orderId);
        setSplitEquipmentId('');
        setSplitMaxFill(0.70);
        setSplitDialogOpen(true);
    };

    const handleAutoSplit = async () => {
        if (!splitOrderId || !splitEquipmentId) {
            setError('Выберите оборудование');
            return;
        }
        try {
            const result = await ordersApi.autoSplit(
                splitOrderId,
                splitEquipmentId,
                splitMaxFill
            );
            await loadData();
            setSplitDialogOpen(false);
            alert(`Создано партий: ${result.batches_created}`);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Ошибка разбиения');
        }
    };

    const handleDelete = async (id: string) => {
        if (!window.confirm('Удалить заказ и все его партии?')) return;
        try {
            await ordersApi.delete(id);
            setOrders((prev) => prev.filter((o) => o.id !== id));
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Ошибка удаления');
        }
    };

    const handleAdd = () => {
        setFormData({
            product_id: '',
            target_qty: 0,
            due_date: '',
            priority: 5,
            comment: '',
        });
        setDialogOpen(true);
    };

    const handleSave = async () => {
        try {
            const response = await ordersApi.create({
                ...formData,
                due_date: new Date(formData.due_date).toISOString(),
                organization_id: '00000000-0000-0000-0000-000000000001',
            });
            setOrders((prev) => [...prev, response]);
            setDialogOpen(false);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Ошибка создания');
        }
    };

    if (loading) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
                <CircularProgress />
            </Box>
        );
    }

    return (
        <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            <Box
                sx={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    mb: 3,
                }}
            >
                <Typography variant="h4" component="h1" sx={{ fontWeight: 600, color: '#2c3e50' }}>
                    Производственные заказы
                </Typography>
                <Button
                    variant="contained"
                    startIcon={<AddIcon />}
                    onClick={handleAdd}
                    sx={{ textTransform: 'none', fontWeight: 600 }}
                >
                    Новый заказ
                </Button>
            </Box>

            {error && (
                <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
                    {error}
                </Alert>
            )}

            <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
                <Chip
                    label={`Всего заказов: ${orders.length}`}
                    color="primary"
                    variant="outlined"
                    icon={<CartIcon />}
                />
                <Chip
                    label={`Партий: ${orders.reduce((sum, o) => sum + o.batches_count, 0)}`}
                    variant="outlined"
                />
            </Box>

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
                    <Box className="ag-theme-alpine" sx={{ flexGrow: 1, width: '100%', minHeight: 0 }}>
                        <AgGridReact
                            rowData={orders}
                            columnDefs={columnDefs}
                            defaultColDef={defaultColDef}
                            getRowId={getRowId}
                            pagination={true}
                            paginationPageSize={20}
                            paginationPageSizeSelector={[20, 50, 100]}
                            suppressPropertyNamesCheck={true}
                            onGridReady={(params: GridReadyEvent) => params.api.sizeColumnsToFit()}
                        />
                    </Box>

                    {/* Раскрывающаяся панель с партиями */}
                    {expandedOrderId && orderBatches[expandedOrderId] && (
                        <Box sx={{ mt: 2, borderTop: '2px solid #e0e0e0', pt: 2 }}>
                            <Typography variant="h6" gutterBottom>
                                Партии заказа
                            </Typography>
                            <TableContainer component={Paper} variant="outlined">
                                <Table size="small">
                                    <TableHead>
                                        <TableRow>
                                            <TableCell>Объём (кг)</TableCell>
                                            <TableCell>Оборудование</TableCell>
                                            <TableCell>Статус</TableCell>
                                            <TableCell>План. начало</TableCell>
                                            <TableCell>План. окончание</TableCell>
                                            <TableCell>Комментарий</TableCell>
                                        </TableRow>
                                    </TableHead>
                                    <TableBody>
                                        {orderBatches[expandedOrderId].map((batch) => (
                                            <TableRow key={batch.id}>
                                                <TableCell>{batch.volume_kg}</TableCell>
                                                <TableCell>{batch.equipment_name || '—'}</TableCell>
                                                <TableCell>{batch.status}</TableCell>
                                                <TableCell>
                                                    {batch.planned_start
                                                        ? new Date(batch.planned_start).toLocaleString('ru-RU')
                                                        : '—'}
                                                </TableCell>
                                                <TableCell>
                                                    {batch.planned_end
                                                        ? new Date(batch.planned_end).toLocaleString('ru-RU')
                                                        : '—'}
                                                </TableCell>
                                                <TableCell>{batch.comment || '—'}</TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </TableContainer>
                        </Box>
                    )}
                </CardContent>
            </Card>

            {/* Диалог создания заказа */}
            <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
                <DialogTitle sx={{ fontWeight: 600 }}>Новый производственный заказ</DialogTitle>
                <DialogContent>
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
                        <FormControl fullWidth>
                            <InputLabel>Продукт (ГП)</InputLabel>
                            <Select
                                value={formData.product_id}
                                label="Продукт (ГП)"
                                onChange={(e) => setFormData({ ...formData, product_id: e.target.value })}
                            >
                                <MenuItem value="">— Выберите продукт —</MenuItem>
                                {products
                                    .filter((p: any) => p.type === 'GP')
                                    .map((p: any) => (
                                        <MenuItem key={p.id} value={p.id}>
                                            {p.code} - {p.name}
                                        </MenuItem>
                                    ))}
                            </Select>
                        </FormControl>
                        <TextField
                            label="Целевое количество"
                            type="number"
                            fullWidth
                            value={formData.target_qty}
                            onChange={(e) =>
                                setFormData({ ...formData, target_qty: Number(e.target.value) })
                            }
                        />
                        <TextField
                            label="Дедлайн"
                            type="datetime-local"
                            fullWidth
                            value={formData.due_date}
                            onChange={(e) => setFormData({ ...formData, due_date: e.target.value })}
                            slotProps={{ inputLabel: { shrink: true } }}
                        />
                        <TextField
                            label="Приоритет (1 - высший, 10 - низший)"
                            type="number"
                            fullWidth
                            value={formData.priority}
                            onChange={(e) =>
                                setFormData({ ...formData, priority: Number(e.target.value) })
                            }
                            slotProps={{
                                htmlInput: {
                                    min: 1,
                                    max: 10,
                                    step: 1,
                                },
                            }}
                        />
                        <TextField
                            label="Комментарий"
                            fullWidth
                            multiline
                            rows={2}
                            value={formData.comment}
                            onChange={(e) => setFormData({ ...formData, comment: e.target.value })}
                        />
                    </Box>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setDialogOpen(false)}>Отмена</Button>
                    <Button onClick={handleSave} variant="contained">
                        Создать
                    </Button>
                </DialogActions>
            </Dialog>

            {/* Диалог автоматического разбиения */}
            <Dialog
                open={splitDialogOpen}
                onClose={() => setSplitDialogOpen(false)}
                maxWidth="sm"
                fullWidth
            >
                <DialogTitle sx={{ fontWeight: 600 }}>Автоматическое разбиение на партии</DialogTitle>
                <DialogContent>
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
                        <FormControl fullWidth>
                            <InputLabel>Оборудование (реактор)</InputLabel>
                            <Select
                                value={splitEquipmentId}
                                label="Оборудование (реактор)"
                                onChange={(e) => setSplitEquipmentId(e.target.value)}
                            >
                                <MenuItem value="">— Выберите оборудование —</MenuItem>
                                {equipment
                                    .filter((e: any) => e.type === 'REACTOR')
                                    .map((e: any) => (
                                        <MenuItem key={e.id} value={e.id}>
                                            {e.name} ({e.volume_kg} кг)
                                        </MenuItem>
                                    ))}
                            </Select>
                        </FormControl>
                        <TextField
                            label="Максимальный % загрузки"
                            type="number"
                            fullWidth
                            value={splitMaxFill}
                            onChange={(e) => setSplitMaxFill(Number(e.target.value))}
                            slotProps={{
                                htmlInput: {
                                    min: 0.1,
                                    max: 1.0,
                                    step: 0.05,
                                },
                            }}
                            helperText="Обычно 0.70 (70%)"
                        />
                    </Box>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setSplitDialogOpen(false)}>Отмена</Button>
                    <Button onClick={handleAutoSplit} variant="contained">
                        Разбить
                    </Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
};

export default OrdersPage;