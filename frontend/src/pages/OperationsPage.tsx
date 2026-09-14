// src/pages/OperationsPage.tsx
import React, { useState, useEffect } from 'react';
import {
    Box, Button, Card, CardContent, Dialog, DialogActions,
    DialogContent, DialogTitle, FormControl, InputLabel,
    MenuItem, Select, TextField, Typography, IconButton,
    CircularProgress, Alert, Chip, FormControlLabel, Checkbox,
} from '@mui/material';
import { Add as AddIcon, Delete as DeleteIcon, Lock as LockIcon } from '@mui/icons-material';
import { AgGridReact } from 'ag-grid-react';
import { ModuleRegistry, AllCommunityModule } from 'ag-grid-community';
import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-alpine.css';
import type { ColDef, GridReadyEvent } from 'ag-grid-community';
import type { Operation, ProductOption } from '../types';
import axios from 'axios';
import { API_BASE_URL } from '../config';
import { usePlan } from '../context/PlainContext';

ModuleRegistry.registerModules([AllCommunityModule]);

const OperationsPage: React.FC = () => {
    // ✅ Получаем версию плана из контекста
    const { currentVersionId, currentPlanName } = usePlan();
    const isReadOnly = currentVersionId !== null;

    const [operations, setOperations] = useState<Operation[]>([]);
    const [products, setProducts] = useState<ProductOption[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [dialogOpen, setDialogOpen] = useState(false);
    const [filterProduct, setFilterProduct] = useState<string>('ALL');
    const [formData, setFormData] = useState<Partial<Operation>>({
        product_id: '', stage_order: 1, name: '', base_duration_mins: 60,
        is_setup: false, is_parallel_group: false, parallel_group_id: '',
        needs_boiler: false, needs_cooling_zone: false, needs_operator: true,
        needs_lab: false, duration_formula: '', comment: '',
    });

    useEffect(() => {
        loadData();
    }, [currentVersionId]); // ✅ Перезагружаем при смене версии

    const loadData = async () => {
        setLoading(true);
        setError(null);
        try {
            // ✅ Передаем version_id если выбран план
            const params = currentVersionId ? { version_id: currentVersionId } : {};
            const [opsRes, prodRes] = await Promise.all([
                axios.get(`${API_BASE_URL}/api/v1/operations/`, { params }),
                axios.get(`${API_BASE_URL}/api/v1/operations/products`),
            ]);
            setOperations(opsRes.data);
            setProducts(prodRes.data);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Ошибка загрузки данных');
        } finally {
            setLoading(false);
        }
    };

    const filteredOperations = filterProduct === 'ALL'
        ? operations : operations.filter(op => op.product_id === filterProduct);

    const columnDefs: ColDef<Operation>[] = [
        {
            headerName: 'ID', field: 'id', width: 120, editable: false,
            valueFormatter: (params) => params.value ? params.value.substring(0, 8) : '',
            cellStyle: { fontFamily: 'monospace', fontSize: '11px', color: '#7f8c8d' },
        },
        { headerName: 'Продукт', field: 'product_name', width: 180, editable: false },
        { headerName: '№ этапа', field: 'stage_order', width: 100, editable: !isReadOnly, type: 'numericColumn' },
        { headerName: 'Наименование операции', field: 'name', flex: 2, minWidth: 200, editable: !isReadOnly },
        { headerName: 'Длительность (мин)', field: 'base_duration_mins', width: 140, editable: !isReadOnly, type: 'numericColumn' },
        {
            headerName: 'Формула', field: 'duration_formula', width: 150, editable: !isReadOnly,
            cellEditor: 'agSelectCellEditor',
            cellEditorParams: { values: ['', 'water_loading', 'heating', 'mixing', 'cooling', 'pumping', 'washing'] },
            valueFormatter: (params) => {
                const labels: Record<string, string> = {
                    '': '—', 'water_loading': 'Загрузка воды', 'heating': 'Нагрев',
                    'mixing': 'Перемешивание', 'cooling': 'Охлаждение', 'pumping': 'Перекачка', 'washing': 'Промывка',
                };
                return labels[params.value] || params.value;
            },
        },
        { headerName: 'Бойлер', field: 'needs_boiler', width: 90, editable: !isReadOnly, cellEditor: 'agCheckboxCellEditor' },
        { headerName: 'Охлаждение', field: 'needs_cooling_zone', width: 110, editable: !isReadOnly, cellEditor: 'agCheckboxCellEditor' },
        { headerName: 'Оператор', field: 'needs_operator', width: 100, editable: !isReadOnly, cellEditor: 'agCheckboxCellEditor' },
        { headerName: 'Лаборант', field: 'needs_lab', width: 100, editable: !isReadOnly, cellEditor: 'agCheckboxCellEditor' },
        { headerName: 'Паралл. группа', field: 'parallel_group_id', width: 130, editable: !isReadOnly, valueFormatter: (params) => params.value || '—' },
        {
            headerName: 'Действия', width: 100, editable: false,
            cellRenderer: (params: any) => isReadOnly ? null : (
                <IconButton color="error" size="small" onClick={() => handleDelete(params.data.id)}>
                    <DeleteIcon fontSize="small" />
                </IconButton>
            ),
        },
    ];

    const defaultColDef: ColDef = {
        sortable: true, filter: true, resizable: true,
        editable: !isReadOnly, singleClickEdit: true,
    };

    const getRowId = (params: any) => params.data.id;

    const handleCellValueChanged = async (params: any) => {
        if (isReadOnly) return;
        const { data, colDef, newValue } = params;
        const field = colDef.field;
        if (!field || field === 'id' || field === 'product_name') return;
        const oldValue = data[field];
        try {
            await axios.put(`${API_BASE_URL}/api/v1/operations/${data.id}`, { [field]: newValue });
            setOperations((prev) => prev.map((op) => op.id === data.id ? { ...op, [field]: newValue } : op));
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Ошибка сохранения');
            setOperations((prev) => prev.map((op) => op.id === data.id ? { ...op, [field]: oldValue } : op));
        }
    };

    const handleDelete = async (id: string) => {
        if (isReadOnly) return;
        if (!window.confirm('Удалить операцию?')) return;
        try {
            await axios.delete(`${API_BASE_URL}/api/v1/operations/${id}`);
            setOperations((prev) => prev.filter((op) => op.id !== id));
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Ошибка удаления');
        }
    };

    const handleAdd = () => {
        if (isReadOnly) return;
        setFormData({
            product_id: products[0]?.id || '', stage_order: 1, name: '', base_duration_mins: 60,
            is_setup: false, is_parallel_group: false, parallel_group_id: '',
            needs_boiler: false, needs_cooling_zone: false, needs_operator: true,
            needs_lab: false, duration_formula: '', comment: '',
        });
        setDialogOpen(true);
    };

    const handleSave = async () => {
        if (isReadOnly) return;
        try {
            const response = await axios.post(`${API_BASE_URL}/api/v1/operations/`, {
                ...formData, organization_id: '00000000-0000-0000-0000-000000000001',
            });
            setOperations((prev) => [...prev, response.data]);
            setDialogOpen(false);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Ошибка создания');
        }
    };

    if (loading) {
        return <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}><CircularProgress /></Box>;
    }

    return (
        <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
                <Typography variant="h4" component="h1" sx={{ fontWeight: 600, color: '#2c3e50' }}>
                    Технологические карты
                </Typography>
                <Box sx={{ display: 'flex', gap: 2 }}>
                    <FormControl size="small" sx={{ minWidth: 250 }}>
                        <InputLabel>Фильтр по продукту</InputLabel>
                        <Select value={filterProduct} label="Фильтр по продукту" onChange={(e) => setFilterProduct(e.target.value)}>
                            <MenuItem value="ALL">Все продукты</MenuItem>
                            {products.map((p) => (
                                <MenuItem key={p.id} value={p.id}>{p.code} - {p.name}</MenuItem>
                            ))}
                        </Select>
                    </FormControl>
                    {!isReadOnly && (
                        <Button variant="contained" startIcon={<AddIcon />} onClick={handleAdd} sx={{ textTransform: 'none', fontWeight: 600 }}>
                            Добавить операцию
                        </Button>
                    )}
                </Box>
            </Box>

            {/* ✅ Индикатор режима просмотра */}
            {isReadOnly && (
                <Alert severity="info" sx={{ mb: 2 }} icon={<LockIcon fontSize="inherit" />}>
                    Режим просмотра: <b>{currentPlanName}</b>. Редактирование недоступно.
                </Alert>
            )}

            {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>{error}</Alert>}

            <Box sx={{ display: 'flex', gap: 1, mb: 2, flexWrap: 'wrap' }}>
                <Chip label={`Всего операций: ${operations.length}`} color="primary" variant="outlined" />
                <Chip label={`Продуктов: ${products.length}`} variant="outlined" />
                {products.map((p) => {
                    const count = operations.filter((op) => op.product_id === p.id).length;
                    return count > 0 ? <Chip key={p.id} label={`${p.code}: ${count} опер.`} variant="outlined" /> : null;
                })}
            </Box>

            <Card sx={{ boxShadow: '0 2px 8px rgba(0,0,0,0.1)', flexGrow: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
                <CardContent sx={{ p: 2, flexGrow: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
                    <Box className="ag-theme-alpine" sx={{ flexGrow: 1, width: '100%', minHeight: 0 }}>
                        <AgGridReact
                            rowData={filteredOperations}
                            columnDefs={columnDefs}
                            defaultColDef={defaultColDef}
                            getRowId={getRowId}
                            pagination={true}
                            paginationPageSize={20}
                            paginationPageSizeSelector={[20, 50, 100]}
                            onCellValueChanged={handleCellValueChanged}
                            suppressPropertyNamesCheck={true}
                            onGridReady={(params: GridReadyEvent) => params.api.sizeColumnsToFit()}
                        />
                    </Box>
                </CardContent>
            </Card>

            {/* Диалог добавления (только для режима редактирования) */}
            {!isReadOnly && (
                <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="md" fullWidth>
                    <DialogTitle sx={{ fontWeight: 600 }}>Добавить операцию</DialogTitle>
                    <DialogContent>
                        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
                            <Box sx={{ display: 'flex', gap: 2 }}>
                                <FormControl fullWidth>
                                    <InputLabel>Продукт (ПФ)</InputLabel>
                                    <Select value={formData.product_id} label="Продукт (ПФ)" onChange={(e) => setFormData({ ...formData, product_id: e.target.value })}>
                                        {products.map((p) => (
                                            <MenuItem key={p.id} value={p.id}>{p.code} - {p.name}</MenuItem>
                                        ))}
                                    </Select>
                                </FormControl>
                                <TextField label="№ этапа" type="number" fullWidth value={formData.stage_order} onChange={(e) => setFormData({ ...formData, stage_order: Number(e.target.value) })} />
                            </Box>
                            <TextField label="Наименование операции" fullWidth value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} />
                            <Box sx={{ display: 'flex', gap: 2 }}>
                                <TextField label="Длительность (мин)" type="number" fullWidth value={formData.base_duration_mins} onChange={(e) => setFormData({ ...formData, base_duration_mins: Number(e.target.value) })} />
                                <FormControl fullWidth>
                                    <InputLabel>Формула расчёта</InputLabel>
                                    <Select value={formData.duration_formula || ''} label="Формула расчёта" onChange={(e) => setFormData({ ...formData, duration_formula: e.target.value })}>
                                        <MenuItem value="">— Не выбрана —</MenuItem>
                                        <MenuItem value="water_loading">Загрузка воды</MenuItem>
                                        <MenuItem value="heating">Нагрев</MenuItem>
                                        <MenuItem value="mixing">Перемешивание</MenuItem>
                                        <MenuItem value="cooling">Охлаждение</MenuItem>
                                        <MenuItem value="pumping">Перекачка</MenuItem>
                                        <MenuItem value="washing">Промывка</MenuItem>
                                    </Select>
                                </FormControl>
                            </Box>
                            <Typography variant="subtitle2" sx={{ mt: 1 }}>Ресурсы:</Typography>
                            <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                                <FormControlLabel control={<Checkbox checked={formData.needs_boiler || false} onChange={(e) => setFormData({ ...formData, needs_boiler: e.target.checked })} />} label="Бойлер" />
                                <FormControlLabel control={<Checkbox checked={formData.needs_cooling_zone || false} onChange={(e) => setFormData({ ...formData, needs_cooling_zone: e.target.checked })} />} label="Зона охлаждения" />
                                <FormControlLabel control={<Checkbox checked={formData.needs_operator || false} onChange={(e) => setFormData({ ...formData, needs_operator: e.target.checked })} />} label="Оператор" />
                                <FormControlLabel control={<Checkbox checked={formData.needs_lab || false} onChange={(e) => setFormData({ ...formData, needs_lab: e.target.checked })} />} label="Лаборант" />
                            </Box>
                            <Box sx={{ display: 'flex', gap: 2 }}>
                                <FormControlLabel control={<Checkbox checked={formData.is_setup || false} onChange={(e) => setFormData({ ...formData, is_setup: e.target.checked })} />} label="Это замывка/переналадка" />
                                <FormControlLabel control={<Checkbox checked={formData.is_parallel_group || false} onChange={(e) => setFormData({ ...formData, is_parallel_group: e.target.checked })} />} label="Параллельная группа" />
                            </Box>
                            {formData.is_parallel_group && (
                                <TextField label="ID параллельной группы" fullWidth value={formData.parallel_group_id || ''} onChange={(e) => setFormData({ ...formData, parallel_group_id: e.target.value })} helperText="Например: GROUP1, GROUP2" />
                            )}
                            <TextField label="Комментарий" fullWidth multiline rows={2} value={formData.comment || ''} onChange={(e) => setFormData({ ...formData, comment: e.target.value })} />
                        </Box>
                    </DialogContent>
                    <DialogActions>
                        <Button onClick={() => setDialogOpen(false)}>Отмена</Button>
                        <Button onClick={handleSave} variant="contained">Сохранить</Button>
                    </DialogActions>
                </Dialog>
            )}
        </Box>
    );
};

export default OperationsPage;