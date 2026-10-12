// frontend/src/pages/RecipesPage.tsx
// Итерация 13.19: markPlanDirty() при изменениях.
// Итерация 17.x: inline-edit рецептов и состава, режим просмотра версии.
// [FIX] В селекте "Продукт (ПФ)" теперь используются продукты (products),
//       а не материалы. FK recipe.product_id -> product.id.

import React, {useEffect, useState} from 'react';
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
    TextField,
    Tooltip,
    Typography,
} from '@mui/material';
import {
    Add as AddIcon,
    Delete as DeleteIcon,
    Edit as EditIcon,
    Lock as LockIcon,
    Science as ScienceIcon,
} from '@mui/icons-material';
import type {ColDef, GridReadyEvent} from 'ag-grid-community';
import {AllCommunityModule, ModuleRegistry} from 'ag-grid-community';
import type {Material, Product, Recipe, RecipeItem} from '../types';
import api from '../services/api';
import {usePlan} from '../context/PlainContext';
import DraggableDialog from '../components/common/DraggableDialog';
import AppAgGrid from '../components/common/AppAgGrid';

ModuleRegistry.registerModules([AllCommunityModule]);

interface RecipeRow {
    id: string;
    product_code: string;
    product_name: string;
    base_volume_kg: number;
    items_count: number;
    comment?: string | null;
}

interface RecipeItemRow {
    id: string;
    recipe_id: string;
    material_id: string;
    material_code: string;
    material_name: string;
    material_unit: string;
    qty_per_base: number;
}

const RecipesPage: React.FC = () => {
    const {currentVersionId, currentPlanName, markPlanDirty} = usePlan();
    const isReadOnly = currentVersionId !== null;

    const [recipes, setRecipes] = useState<Recipe[]>([]);
    const [materials, setMaterials] = useState<Material[]>([]);
    // [FIX] отдельный стейт под продукты (для селекта "Продукт (ПФ)")
    const [products, setProducts] = useState<Product[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [dialogOpen, setDialogOpen] = useState(false);
    const [selectedRecipe, setSelectedRecipe] = useState<Recipe | null>(null);
    const [formData, setFormData] = useState({
        product_id: '', base_volume_kg: 100, comment: '',
    });
    const [newItem, setNewItem] = useState<{ material_id: string; qty_per_base: number }>({
        material_id: '', qty_per_base: 1,
    });

    useEffect(() => { loadData(); }, [currentVersionId]);

    const loadData = async () => {
        setLoading(true);
        setError(null);
        try {
            // [FIX] Продукты грузим с учётом версии плана.
            // [FIX] Рецепты — тоже: если version_id задан, backend
            // читает из recipe_snapshot / recipe_item_snapshot.
            const productParams = currentVersionId ? { params: { version_id: currentVersionId } } : {};
            const recipesParams = currentVersionId ? { params: { version_id: currentVersionId } } : {};
            const [recipesResp, materialsResp, productsResp] = await Promise.all([
                api.get('/api/v1/recipes/', recipesParams),
                api.get('/api/v1/materials/'),
                api.get('/api/v1/products/', productParams),
            ]);
            setRecipes(recipesResp.data);
            setMaterials(materialsResp.data);
            setProducts(productsResp.data);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Ошибка загрузки данных');
        } finally {
            setLoading(false);
        }
    };
    
    const recipeRows: RecipeRow[] = recipes.map((r) => ({
        id: r.id,
        product_code: r.product_code || '',
        product_name: r.product_name || '',
        base_volume_kg: r.base_volume_kg,
        items_count: r.items.length,
        comment: r.comment,
    }));

    const columnDefs: ColDef<RecipeRow>[] = [
        { headerName: 'Код продукта', field: 'product_code', width: 150, editable: false },
        { headerName: 'Наименование продукта', field: 'product_name', flex: 2, minWidth: 200, editable: false },
        {
            headerName: 'Базовый объём (кг)', field: 'base_volume_kg', width: 160,
            editable: !isReadOnly, type: 'numericColumn',
        },
        { headerName: 'Компонентов', field: 'items_count', width: 120, type: 'numericColumn', editable: false },
        { headerName: 'Комментарий', field: 'comment', flex: 1, editable: !isReadOnly },
        {
            headerName: 'Действия', width: 140, cellClass: 'ag-cell-actions', editable: false,
            cellRenderer: (params: any) => (
                <Box
                    sx={{
                        display: 'flex', gap: 0.5, alignItems: 'center',
                        justifyContent: 'center', width: '100%', height: '100%',
                    }}
                >
                    <Tooltip title="Открыть состав" arrow>
                        <IconButton size="small" color="primary" onClick={() => handleViewRecipe(params.data.id)}>
                            <EditIcon fontSize="small" />
                        </IconButton>
                    </Tooltip>
                    {!isReadOnly && (
                        <Tooltip title="Удалить" arrow>
                            <IconButton size="small" color="error" onClick={() => handleDelete(params.data.id)}>
                                <DeleteIcon fontSize="small" />
                            </IconButton>
                        </Tooltip>
                    )}
                </Box>
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
        if (!field || field === 'id' || field === 'items_count') return;
        const oldValue = data[field];
        try {
            await api.put(`/api/v1/recipes/${data.id}`, { [field]: newValue });
            setRecipes((prev) => prev.map((r) => r.id === data.id ? { ...r, [field]: newValue } : r));
            markPlanDirty();
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Ошибка сохранения');
            setRecipes((prev) => prev.map((r) => r.id === data.id ? { ...r, [field]: oldValue } : r));
        }
    };

    const handleViewRecipe = (recipeId: string) => {
        const recipe = recipes.find((r) => r.id === recipeId);
        if (recipe) {
            setSelectedRecipe(recipe);
            setNewItem({ material_id: '', qty_per_base: 1 });
        }
    };

    const handleDelete = async (id: string) => {
        if (isReadOnly) return;
        if (!window.confirm('Удалить рецепт?')) return;
        try {
            await api.delete(`/api/v1/recipes/${id}`);
            setRecipes((prev) => prev.filter((r) => r.id !== id));
            markPlanDirty();
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Ошибка удаления');
        }
    };

    const handleAdd = () => {
        if (isReadOnly) return;
        setFormData({ product_id: '', base_volume_kg: 100, comment: '' });
        setDialogOpen(true);
    };

    const handleSave = async () => {
        if (isReadOnly) return;
        // [FIX-CREATE] быстрая валидация: не отправляем пустой product_id
        if (!formData.product_id) {
            setError('Выберите продукт (ПФ)');
            return;
        }
        try {
            const response = await api.post('/api/v1/recipes/', {
                ...formData,
                organization_id: '00000000-0000-0000-0000-000000000001',
                items: [],
            });
            setRecipes((prev) => [...prev, response.data]);
            setDialogOpen(false);
            markPlanDirty();
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Ошибка создания');
        }
    };

    const handleItemValueChanged = async (params: any) => {
        if (isReadOnly || !selectedRecipe) return;
        const { data, colDef, newValue } = params;
        const field = colDef.field;
        if (field !== 'qty_per_base') return;
        const oldValue = data.qty_per_base;
        try {
            await api.put(`/api/v1/recipes/${selectedRecipe.id}/items/${data.id}`, {
                material_id: data.material_id,
                qty_per_base: Number(newValue),
            });
            const updatedItems = selectedRecipe.items.map((it) =>
                it.id === data.id ? { ...it, qty_per_base: Number(newValue) } : it,
            );
            setSelectedRecipe({ ...selectedRecipe, items: updatedItems });
            setRecipes((prev) => prev.map((r) =>
                r.id === selectedRecipe.id ? { ...r, items: updatedItems } : r,
            ));
            markPlanDirty();
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Ошибка сохранения компонента');
            const rollbackItems = selectedRecipe.items.map((it) =>
                it.id === data.id ? { ...it, qty_per_base: oldValue } : it,
            );
            setSelectedRecipe({ ...selectedRecipe, items: rollbackItems });
        }
    };

    const handleAddItem = async () => {
        if (isReadOnly || !selectedRecipe) return;
        if (!newItem.material_id) {
            setError('Выберите материал');
            return;
        }
        try {
            const resp = await api.post(`/api/v1/recipes/${selectedRecipe.id}/items`, {
                material_id: newItem.material_id,
                qty_per_base: Number(newItem.qty_per_base),
            });
            const mat = materials.find((m) => m.id === newItem.material_id);
            const created: RecipeItem = {
                id: resp.data.id,
                recipe_id: selectedRecipe.id,
                material_id: newItem.material_id,
                qty_per_base: Number(newItem.qty_per_base),
                material_code: mat?.code,
                material_name: mat?.name,
                material_unit: mat?.unit,
            };
            const updatedItems = [...selectedRecipe.items, created];
            setSelectedRecipe({ ...selectedRecipe, items: updatedItems });
            setRecipes((prev) => prev.map((r) =>
                r.id === selectedRecipe.id ? { ...r, items: updatedItems } : r,
            ));
            setNewItem({ material_id: '', qty_per_base: 1 });
            markPlanDirty();
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Ошибка добавления компонента');
        }
    };

    const handleDeleteItem = async (itemId: string) => {
        if (isReadOnly || !selectedRecipe) return;
        if (!window.confirm('Удалить компонент?')) return;
        try {
            await api.delete(`/api/v1/recipes/${selectedRecipe.id}/items/${itemId}`);
            const updatedItems = selectedRecipe.items.filter((it) => it.id !== itemId);
            setSelectedRecipe({ ...selectedRecipe, items: updatedItems });
            setRecipes((prev) => prev.map((r) =>
                r.id === selectedRecipe.id ? { ...r, items: updatedItems } : r,
            ));
            markPlanDirty();
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Ошибка удаления компонента');
        }
    };

    const itemRows: RecipeItemRow[] = selectedRecipe
        ? selectedRecipe.items.map((it: RecipeItem) => ({
            id: it.id,
            recipe_id: it.recipe_id,
            material_id: it.material_id,
            material_code: it.material_code || '',
            material_name: it.material_name || '',
            material_unit: it.material_unit || '',
            qty_per_base: it.qty_per_base,
        }))
        : [];

    const itemColumnDefs: ColDef<RecipeItemRow>[] = [
        { headerName: 'Код', field: 'material_code', width: 120, editable: false },
        { headerName: 'Наименование', field: 'material_name', flex: 2, minWidth: 180, editable: false },
        {
            headerName: 'Кол-во на базу', field: 'qty_per_base', width: 140,
            editable: !isReadOnly, type: 'numericColumn',
        },
        { headerName: 'Ед.', field: 'material_unit', width: 80, editable: false },
        {
            headerName: '', width: 60, editable: false, cellClass: 'ag-cell-actions',
            cellRenderer: (params: any) => isReadOnly ? null : (
                <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
                    <Tooltip title="Удалить компонент" arrow>
                        <IconButton size="small" color="error" onClick={() => handleDeleteItem(params.data.id)}>
                            <DeleteIcon fontSize="small" />
                        </IconButton>
                    </Tooltip>
                </Box>
            ),
        },
    ];

    if (loading) {
        return <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}><CircularProgress /></Box>;
    }

    return (
        <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
                <Typography variant="h4" component="h1" sx={{ fontWeight: 600, color: '#2c3e50' }}>
                    Рецептуры
                </Typography>
                {!isReadOnly && (
                    <Button variant="contained" startIcon={<AddIcon />} onClick={handleAdd} sx={{ textTransform: 'none', fontWeight: 600 }}>
                        Добавить рецепт
                    </Button>
                )}
            </Box>

            {isReadOnly && (
                <Alert severity="info" sx={{ mb: 2 }} icon={<LockIcon fontSize="inherit" />}>
                    Режим просмотра: <b>{currentPlanName}</b>. Редактирование недоступно.
                </Alert>
            )}

            {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>{error}</Alert>}

            <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
                <Chip label={`Всего рецептов: ${recipes.length}`} color="primary" variant="outlined" icon={<ScienceIcon />} />
                <Chip label={`Материалов: ${materials.length}`} variant="outlined" />
            </Box>

            <Card sx={{ flexGrow: 1, boxShadow: '0 2px 8px rgba(0,0,0,0.1)', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
                <CardContent sx={{ p: 2, flexGrow: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
                    <Box sx={{ flexGrow: 1, width: '100%', minHeight: 0 }}>
                        <AppAgGrid
                            rowData={recipeRows}
                            columnDefs={columnDefs}
                            defaultColDef={defaultColDef}
                            getRowId={getRowId}
                            pagination={true}
                            paginationPageSize={20}
                            paginationPageSizeSelector={[20, 50, 100]}
                            onCellValueChanged={handleCellValueChanged}
                            onGridReady={(params: GridReadyEvent) => params.api.sizeColumnsToFit()}
                        />
                    </Box>
                </CardContent>
            </Card>

            {/* Диалог создания рецепта */}
            <DraggableDialog
                open={dialogOpen}
                onClose={() => setDialogOpen(false)}
                title="Добавить рецепт"
                initialWidth={600}
                initialHeight="auto"
                minWidth={480}
                minHeight={320}
                actions={
                    <>
                        <Button onClick={() => setDialogOpen(false)}>Отмена</Button>
                        <Button onClick={handleSave} variant="contained">Сохранить</Button>
                    </>
                }
            >
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                    <FormControl fullWidth>
                        <InputLabel>Продукт (ПФ)</InputLabel>
                        {/* [FIX] селект продуктов вместо материалов */}
                        <Select
                            value={formData.product_id}
                            label="Продукт (ПФ)"
                            onChange={(e) => setFormData({ ...formData, product_id: e.target.value })}
                        >
                            <MenuItem value="">— Выберите продукт —</MenuItem>
                            {products.filter((p) => p.type === 'PF').map((p) => (
                                <MenuItem key={p.id} value={p.id}>{p.code} - {p.name}</MenuItem>
                            ))}
                        </Select>
                    </FormControl>
                    <TextField label="Базовый объём (кг)" type="number" fullWidth value={formData.base_volume_kg} onChange={(e) => setFormData({ ...formData, base_volume_kg: Number(e.target.value) })} helperText="Обычно 100 кг" />
                    <TextField label="Комментарий" fullWidth multiline rows={2} value={formData.comment} onChange={(e) => setFormData({ ...formData, comment: e.target.value })} />
                </Box>
            </DraggableDialog>

            {/* Диалог состава рецепта (редактируемый) */}
            <DraggableDialog
                open={selectedRecipe !== null}
                onClose={() => setSelectedRecipe(null)}
                title={selectedRecipe ? `Состав: ${selectedRecipe.product_name} (${selectedRecipe.base_volume_kg} кг)` : 'Состав рецепта'}
                initialWidth={900}
                initialHeight="auto"
                minWidth={640}
                minHeight={400}
                actions={<Button onClick={() => setSelectedRecipe(null)}>Закрыть</Button>}
            >
                {selectedRecipe && (
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                        <Box sx={{ height: 320, width: '100%' }}>
                            <AppAgGrid
                                rowData={itemRows}
                                columnDefs={itemColumnDefs}
                                defaultColDef={{
                                    sortable: true, filter: true, resizable: true,
                                    editable: !isReadOnly, singleClickEdit: true,
                                }}
                                getRowId={(params: any) => params.data.id}
                                onCellValueChanged={handleItemValueChanged}
                            />
                        </Box>

                        {!isReadOnly && (
                            <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
                                <FormControl sx={{ flex: 2 }} size="small">
                                    <InputLabel>Материал</InputLabel>
                                    <Select
                                        value={newItem.material_id}
                                        label="Материал"
                                        onChange={(e) => setNewItem({ ...newItem, material_id: e.target.value })}
                                    >
                                        <MenuItem value="">— Выберите материал —</MenuItem>
                                        {materials.map((m) => (
                                            <MenuItem key={m.id} value={m.id}>
                                                {m.code} - {m.name} ({m.unit})
                                            </MenuItem>
                                        ))}
                                    </Select>
                                </FormControl>
                                <TextField
                                    label="Кол-во"
                                    type="number"
                                    size="small"
                                    sx={{ flex: 1 }}
                                    value={newItem.qty_per_base}
                                    onChange={(e) => setNewItem({ ...newItem, qty_per_base: Number(e.target.value) })}
                                />
                                <Button variant="outlined" onClick={handleAddItem}>Добавить</Button>
                            </Box>
                        )}
                    </Box>
                )}
            </DraggableDialog>
        </Box>
    );
};

export default RecipesPage;