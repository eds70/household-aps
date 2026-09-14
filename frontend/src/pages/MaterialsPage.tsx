// frontend/src/pages/MaterialsPage.tsx
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
} from '@mui/material';
import {
    Add as AddIcon,
    Delete as DeleteIcon,
    Inventory as InventoryIcon,
} from '@mui/icons-material';
import { AgGridReact } from 'ag-grid-react';
import { ModuleRegistry, AllCommunityModule } from 'ag-grid-community';
import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-alpine.css';
import type { ColDef, GridReadyEvent } from 'ag-grid-community';
import type { Material, MaterialCategory } from '../types';
import { materialsApi } from '../services/api';

ModuleRegistry.registerModules([AllCommunityModule]);

const CATEGORY_LABELS: Record<MaterialCategory, string> = {
    RAW: 'Сырьё',
    PACKAGING: 'Упаковка',
    LABEL: 'Этикетки',
};

const UNIT_LABELS: Record<string, string> = {
    kg: 'кг',
    pc: 'шт',
    l: 'л',
};

const MaterialsPage: React.FC = () => {
    const [materials, setMaterials] = useState<Material[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [dialogOpen, setDialogOpen] = useState(false);
    const [filterCategory, setFilterCategory] = useState<string>('ALL');
    const [formData, setFormData] = useState<Partial<Material>>({
        code: '',
        name: '',
        unit: 'kg',
        category: 'RAW',
        comment: '',
    });

    useEffect(() => {
        loadMaterials();
    }, []);

    const loadMaterials = async () => {
        setLoading(true);
        setError(null);
        try {
            const data = await materialsApi.getAll();
            setMaterials(data);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Ошибка загрузки материалов');
        } finally {
            setLoading(false);
        }
    };

    const filteredMaterials =
        filterCategory === 'ALL'
            ? materials
            : materials.filter((m) => m.category === filterCategory);

    const columnDefs: ColDef<Material>[] = [
        {
            headerName: 'Код',
            field: 'code',
            width: 120,
            editable: true,
        },
        {
            headerName: 'Наименование',
            field: 'name',
            flex: 2,
            minWidth: 200,
            editable: true,
        },
        {
            headerName: 'Категория',
            field: 'category',
            width: 150,
            editable: true,
            cellEditor: 'agSelectCellEditor',
            cellEditorParams: { values: ['RAW', 'PACKAGING', 'LABEL'] },
            valueFormatter: (params) => {
                const value = params.value as MaterialCategory;
                return CATEGORY_LABELS[value] || params.value;
            },
        },
        {
            headerName: 'Ед. изм.',
            field: 'unit',
            width: 100,
            editable: true,
            cellEditor: 'agSelectCellEditor',
            cellEditorParams: { values: ['kg', 'pc', 'l'] },
            valueFormatter: (params) => UNIT_LABELS[params.value] || params.value,
        },
        {
            headerName: 'Комментарий',
            field: 'comment',
            flex: 1,
            editable: true,
        },
        {
            headerName: 'Действия',
            width: 100,
            editable: false,
            cellRenderer: (params: any) => (
                <IconButton
                    color="error"
                    size="small"
                    onClick={() => handleDelete(params.data.id)}
                >
                    <DeleteIcon fontSize="small" />
                </IconButton>
            ),
        },
    ];

    const defaultColDef: ColDef = {
        sortable: true,
        filter: true,
        resizable: true,
        editable: true,
        singleClickEdit: true,
    };

    const getRowId = (params: any) => params.data.id;

    const handleCellValueChanged = async (params: any) => {
        const { data, colDef, newValue } = params;
        const field = colDef.field;
        if (!field) return;
        const oldValue = data[field];
        try {
            await materialsApi.update(data.id, { [field]: newValue });
            setMaterials((prev) =>
                prev.map((m) => (m.id === data.id ? { ...m, [field]: newValue } : m))
            );
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Ошибка сохранения');
            setMaterials((prev) =>
                prev.map((m) => (m.id === data.id ? { ...m, [field]: oldValue } : m))
            );
        }
    };

    const handleDelete = async (id: string) => {
        if (!window.confirm('Удалить материал?')) return;
        try {
            await materialsApi.delete(id);
            setMaterials((prev) => prev.filter((m) => m.id !== id));
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Ошибка удаления');
        }
    };

    const handleAdd = () => {
        setFormData({
            code: '',
            name: '',
            unit: 'kg',
            category: 'RAW',
            comment: '',
        });
        setDialogOpen(true);
    };

    const handleSave = async () => {
        try {
            const response = await materialsApi.create({
                ...formData,
                organization_id: '00000000-0000-0000-0000-000000000001',
            });
            setMaterials((prev) => [...prev, response]);
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
                    Справочник материалов
                </Typography>
                <Box sx={{ display: 'flex', gap: 2 }}>
                    <FormControl size="small" sx={{ minWidth: 200 }}>
                        <InputLabel>Фильтр по категории</InputLabel>
                        <Select
                            value={filterCategory}
                            label="Фильтр по категории"
                            onChange={(e) => setFilterCategory(e.target.value)}
                        >
                            <MenuItem value="ALL">Все категории</MenuItem>
                            <MenuItem value="RAW">Сырьё</MenuItem>
                            <MenuItem value="PACKAGING">Упаковка</MenuItem>
                            <MenuItem value="LABEL">Этикетки</MenuItem>
                        </Select>
                    </FormControl>
                    <Button
                        variant="contained"
                        startIcon={<AddIcon />}
                        onClick={handleAdd}
                        sx={{ textTransform: 'none', fontWeight: 600 }}
                    >
                        Добавить материал
                    </Button>
                </Box>
            </Box>

            {error && (
                <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
                    {error}
                </Alert>
            )}

            <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
                <Chip
                    label={`Всего: ${materials.length}`}
                    color="primary"
                    variant="outlined"
                    icon={<InventoryIcon />}
                />
                <Chip label={`Сырьё: ${materials.filter((m) => m.category === 'RAW').length}`} variant="outlined" />
                <Chip label={`Упаковка: ${materials.filter((m) => m.category === 'PACKAGING').length}`} variant="outlined" />
                <Chip label={`Этикетки: ${materials.filter((m) => m.category === 'LABEL').length}`} variant="outlined" />
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
                            rowData={filteredMaterials}
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

            <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
                <DialogTitle sx={{ fontWeight: 600 }}>Добавить материал</DialogTitle>
                <DialogContent>
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
                        <Box sx={{ display: 'flex', gap: 2 }}>
                            <TextField
                                label="Код материала"
                                fullWidth
                                value={formData.code}
                                onChange={(e) => setFormData({ ...formData, code: e.target.value })}
                            />
                            <FormControl fullWidth>
                                <InputLabel>Категория</InputLabel>
                                <Select
                                    value={formData.category}
                                    label="Категория"
                                    onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                                >
                                    <MenuItem value="RAW">Сырьё</MenuItem>
                                    <MenuItem value="PACKAGING">Упаковка</MenuItem>
                                    <MenuItem value="LABEL">Этикетки</MenuItem>
                                </Select>
                            </FormControl>
                        </Box>
                        <TextField
                            label="Наименование"
                            fullWidth
                            value={formData.name}
                            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                        />
                        <Box sx={{ display: 'flex', gap: 2 }}>
                            <FormControl fullWidth>
                                <InputLabel>Единица измерения</InputLabel>
                                <Select
                                    value={formData.unit}
                                    label="Единица измерения"
                                    onChange={(e) => setFormData({ ...formData, unit: e.target.value })}
                                >
                                    <MenuItem value="kg">Килограммы (кг)</MenuItem>
                                    <MenuItem value="pc">Штуки (шт)</MenuItem>
                                    <MenuItem value="l">Литры (л)</MenuItem>
                                </Select>
                            </FormControl>
                        </Box>
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
                        Сохранить
                    </Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
};

export default MaterialsPage;