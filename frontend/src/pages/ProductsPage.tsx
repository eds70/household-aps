// src/pages/ProductsPage.tsx
import React, { useState, useEffect } from 'react';
import {
    Box, Button, Card, CardContent, Dialog, DialogActions,
    DialogContent, DialogTitle, FormControl, InputLabel,
    MenuItem, Select, TextField, Typography, IconButton,
    CircularProgress, Alert, Chip,
} from '@mui/material';
import { Add as AddIcon, Delete as DeleteIcon, Lock as LockIcon } from '@mui/icons-material';
import { AgGridReact } from 'ag-grid-react';
import { ModuleRegistry, AllCommunityModule } from 'ag-grid-community';
import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-alpine.css';
import type { ColDef, GridReadyEvent } from 'ag-grid-community';
import type { Product } from '../types';
import axios from 'axios';
import { API_BASE_URL } from '../config';
import { usePlan } from '../context/PlainContext';

ModuleRegistry.registerModules([AllCommunityModule]);

const PRODUCT_TYPE_TRANSLATIONS: Record<string, string> = {
    'PF': 'Полуфабрикат',
    'GP': 'Готовая продукция',
};

const ProductsPage: React.FC = () => {
    // ✅ Получаем версию плана из контекста
    const { currentVersionId, currentPlanName } = usePlan();
    const isReadOnly = currentVersionId !== null;

    const [products, setProducts] = useState<Product[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [dialogOpen, setDialogOpen] = useState(false);
    const [filterType, setFilterType] = useState<string>('ALL');
    const [formData, setFormData] = useState<Partial<Product>>({
        code: '', name: '', type: 'PF', viscosity_coeff: 1.0,
        requires_heating: false, bottle_volume_l: undefined,
        fill_speed_per_min: undefined, parent_pf_id: undefined,
    });

    useEffect(() => {
        loadProducts();
    }, [currentVersionId]); // ✅ Перезагружаем при смене версии

    const loadProducts = async () => {
        setLoading(true);
        setError(null);
        try {
            // ✅ Передаем version_id если выбран план
            const params = currentVersionId ? { version_id: currentVersionId } : {};
            const response = await axios.get(`${API_BASE_URL}/api/v1/products/`, { params });
            setProducts(response.data);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Ошибка загрузки данных');
        } finally {
            setLoading(false);
        }
    };

    const filteredProducts = filterType === 'ALL'
        ? products : products.filter(p => p.type === filterType);

    const columnDefs: ColDef<Product>[] = [
        {
            headerName: 'ID', field: 'id', width: 120, editable: false,
            valueFormatter: (params) => params.value ? params.value.substring(0, 8) : '',
            cellStyle: { fontFamily: 'monospace', fontSize: '11px', color: '#7f8c8d' },
        },
        { headerName: 'Код', field: 'code', width: 150, editable: !isReadOnly },
        { headerName: 'Наименование', field: 'name', flex: 2, minWidth: 200, editable: !isReadOnly },
        {
            headerName: 'Тип', field: 'type', width: 180, editable: !isReadOnly,
            cellEditor: 'agSelectCellEditor',
            cellEditorParams: { values: ['PF', 'GP'] },
            valueFormatter: (params) => PRODUCT_TYPE_TRANSLATIONS[params.value] || params.value,
        },
        { headerName: 'Коэф. вязкости', field: 'viscosity_coeff', width: 130, editable: !isReadOnly, type: 'numericColumn' },
        { headerName: 'Требует нагрева', field: 'requires_heating', width: 150, editable: !isReadOnly, cellEditor: 'agCheckboxCellEditor' },
        { headerName: 'Объем тары (л)', field: 'bottle_volume_l', width: 130, editable: !isReadOnly, type: 'numericColumn' },
        { headerName: 'Скорость розлива', field: 'fill_speed_per_min', width: 150, editable: !isReadOnly, type: 'numericColumn' },
        {
            headerName: 'Родительский ПФ', field: 'parent_pf_id', width: 200, editable: false,
            valueFormatter: (params) => {
                if (!params.value) return '—';
                const parent = products.find(p => p.id === params.value);
                return parent ? `${parent.code} - ${parent.name}` : params.value.substring(0, 8);
            },
        },
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
        if (!field || field === 'id') return;
        const oldValue = data[field];
        try {
            await axios.put(`${API_BASE_URL}/api/v1/products/${data.id}`, { [field]: newValue });
            setProducts((prev) => prev.map((p) => p.id === data.id ? { ...p, [field]: newValue } : p));
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Ошибка сохранения');
            setProducts((prev) => prev.map((p) => p.id === data.id ? { ...p, [field]: oldValue } : p));
        }
    };

    const handleDelete = async (id: string) => {
        if (isReadOnly) return;
        if (!window.confirm('Удалить продукт?')) return;
        try {
            await axios.delete(`${API_BASE_URL}/api/v1/products/${id}`);
            setProducts((prev) => prev.filter((p) => p.id !== id));
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Ошибка удаления');
        }
    };

    const handleAdd = () => {
        if (isReadOnly) return;
        setFormData({
            code: '', name: '', type: 'PF', viscosity_coeff: 1.0,
            requires_heating: false, bottle_volume_l: undefined,
            fill_speed_per_min: undefined, parent_pf_id: undefined,
        });
        setDialogOpen(true);
    };

    const handleSave = async () => {
        if (isReadOnly) return;
        try {
            const response = await axios.post(`${API_BASE_URL}/api/v1/products/`, {
                ...formData, organization_id: '00000000-0000-0000-0000-000000000001',
            });
            setProducts((prev) => [...prev, response.data]);
            setDialogOpen(false);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Ошибка создания');
        }
    };

    if (loading) {
        return <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}><CircularProgress /></Box>;
    }

    return (
        <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
                <Typography variant="h4" component="h1" sx={{ fontWeight: 600, color: '#2c3e50' }}>
                    Справочник продуктов
                </Typography>
                <Box sx={{ display: 'flex', gap: 2 }}>
                    <FormControl size="small" sx={{ minWidth: 200 }}>
                        <InputLabel>Фильтр по типу</InputLabel>
                        <Select value={filterType} label="Фильтр по типу" onChange={(e) => setFilterType(e.target.value)}>
                            <MenuItem value="ALL">Все продукты</MenuItem>
                            <MenuItem value="PF">Полуфабрикаты</MenuItem>
                            <MenuItem value="GP">Готовая продукция</MenuItem>
                        </Select>
                    </FormControl>
                    {!isReadOnly && (
                        <Button variant="contained" startIcon={<AddIcon />} onClick={handleAdd} sx={{ textTransform: 'none', fontWeight: 600 }}>
                            Добавить продукт
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

            <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
                <Chip label={`Всего: ${products.length}`} color="primary" variant="outlined" />
                <Chip label={`ПФ: ${products.filter(p => p.type === 'PF').length}`} variant="outlined" />
                <Chip label={`ГП: ${products.filter(p => p.type === 'GP').length}`} variant="outlined" />
            </Box>

            <Card sx={{ flexGrow: 1, boxShadow: '0 2px 8px rgba(0,0,0,0.1)', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
                <CardContent sx={{ p: 2, flexGrow: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
                    <Box className="ag-theme-alpine" sx={{ flexGrow: 1, width: '100%', minHeight: 0 }}>
                        <AgGridReact
                            rowData={filteredProducts}
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
                    <DialogTitle sx={{ fontWeight: 600 }}>Добавить продукт</DialogTitle>
                    <DialogContent>
                        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
                            <Box sx={{ display: 'flex', gap: 2 }}>
                                <TextField label="Код продукта" fullWidth value={formData.code} onChange={(e) => setFormData({ ...formData, code: e.target.value })} />
                                <FormControl fullWidth>
                                    <InputLabel>Тип</InputLabel>
                                    <Select value={formData.type} label="Тип" onChange={(e) => setFormData({ ...formData, type: e.target.value })}>
                                        <MenuItem value="PF">Полуфабрикат</MenuItem>
                                        <MenuItem value="GP">Готовая продукция</MenuItem>
                                    </Select>
                                </FormControl>
                            </Box>
                            <TextField label="Наименование" fullWidth value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} />
                            <Box sx={{ display: 'flex', gap: 2 }}>
                                <TextField label="Коэф. вязкости" type="number" fullWidth value={formData.viscosity_coeff} onChange={(e) => setFormData({ ...formData, viscosity_coeff: Number(e.target.value) })} />
                                <FormControl fullWidth>
                                    <InputLabel>Требует нагрева</InputLabel>
                                    <Select value={formData.requires_heating ? 'true' : 'false'} label="Требует нагрева" onChange={(e) => setFormData({ ...formData, requires_heating: e.target.value === 'true' })}>
                                        <MenuItem value="true">Да</MenuItem>
                                        <MenuItem value="false">Нет</MenuItem>
                                    </Select>
                                </FormControl>
                            </Box>
                            {formData.type === 'GP' && (
                                <Box sx={{ display: 'flex', gap: 2 }}>
                                    <TextField label="Объем тары (л)" type="number" fullWidth value={formData.bottle_volume_l || ''} onChange={(e) => setFormData({ ...formData, bottle_volume_l: Number(e.target.value) })} />
                                    <TextField label="Скорость розлива (шт/мин)" type="number" fullWidth value={formData.fill_speed_per_min || ''} onChange={(e) => setFormData({ ...formData, fill_speed_per_min: Number(e.target.value) })} />
                                </Box>
                            )}
                            {formData.type === 'GP' && (
                                <FormControl fullWidth>
                                    <InputLabel>Родительский ПФ</InputLabel>
                                    <Select value={formData.parent_pf_id || ''} label="Родительский ПФ" onChange={(e) => setFormData({ ...formData, parent_pf_id: e.target.value })}>
                                        <MenuItem value="">— Не выбран —</MenuItem>
                                        {products.filter(p => p.type === 'PF').map(p => (
                                            <MenuItem key={p.id} value={p.id}>{p.code} - {p.name}</MenuItem>
                                        ))}
                                    </Select>
                                </FormControl>
                            )}
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

export default ProductsPage;