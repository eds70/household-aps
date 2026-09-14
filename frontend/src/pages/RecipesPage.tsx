// frontend/src/pages/RecipesPage.tsx
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
    Science as ScienceIcon,
} from '@mui/icons-material';
import { AgGridReact } from 'ag-grid-react';
import { ModuleRegistry, AllCommunityModule } from 'ag-grid-community';
import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-alpine.css';
import type { ColDef, GridReadyEvent } from 'ag-grid-community';
import type { Recipe, RecipeItem, Material } from '../types';
import { recipesApi, materialsApi } from '../services/api';

ModuleRegistry.registerModules([AllCommunityModule]);

interface RecipeRow {
    id: string;
    product_code: string;
    product_name: string;
    base_volume_kg: number;
    items_count: number;
    comment?: string | null;
}

const RecipesPage: React.FC = () => {
    const [recipes, setRecipes] = useState<Recipe[]>([]);
    const [materials, setMaterials] = useState<Material[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [dialogOpen, setDialogOpen] = useState(false);
    const [selectedRecipe, setSelectedRecipe] = useState<Recipe | null>(null);
    const [formData, setFormData] = useState({
        product_id: '',
        base_volume_kg: 100,
        comment: '',
    });

    useEffect(() => {
        loadData();
    }, []);

    const loadData = async () => {
        setLoading(true);
        setError(null);
        try {
            const [recipesData, materialsData] = await Promise.all([
                recipesApi.getAll(),
                materialsApi.getAll(),
            ]);
            setRecipes(recipesData);
            setMaterials(materialsData);
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
        {
            headerName: 'Код продукта',
            field: 'product_code',
            width: 150,
        },
        {
            headerName: 'Наименование продукта',
            field: 'product_name',
            flex: 2,
            minWidth: 200,
        },
        {
            headerName: 'Базовый объём (кг)',
            field: 'base_volume_kg',
            width: 150,
            type: 'numericColumn',
        },
        {
            headerName: 'Компонентов',
            field: 'items_count',
            width: 120,
            type: 'numericColumn',
        },
        {
            headerName: 'Комментарий',
            field: 'comment',
            flex: 1,
        },
        {
            headerName: 'Действия',
            width: 200,
            cellRenderer: (params: any) => (
                <Box sx={{ display: 'flex', gap: 0.5 }}>
                    <Button
                        size="small"
                        variant="outlined"
                        onClick={() => handleViewRecipe(params.data.id)}
                    >
                        Состав
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

    const handleViewRecipe = (recipeId: string) => {
        const recipe = recipes.find((r) => r.id === recipeId);
        if (recipe) {
            setSelectedRecipe(recipe);
        }
    };

    const handleDelete = async (id: string) => {
        if (!window.confirm('Удалить рецепт?')) return;
        try {
            await recipesApi.delete(id);
            setRecipes((prev) => prev.filter((r) => r.id !== id));
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Ошибка удаления');
        }
    };

    const handleAdd = () => {
        setFormData({
            product_id: '',
            base_volume_kg: 100,
            comment: '',
        });
        setDialogOpen(true);
    };

    const handleSave = async () => {
        try {
            const response = await recipesApi.create({
                ...formData,
                organization_id: '00000000-0000-0000-0000-000000000001',
                items: [],
            });
            setRecipes((prev) => [...prev, response]);
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
                    Рецептуры
                </Typography>
                <Button
                    variant="contained"
                    startIcon={<AddIcon />}
                    onClick={handleAdd}
                    sx={{ textTransform: 'none', fontWeight: 600 }}
                >
                    Добавить рецепт
                </Button>
            </Box>

            {error && (
                <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
                    {error}
                </Alert>
            )}

            <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
                <Chip
                    label={`Всего рецептов: ${recipes.length}`}
                    color="primary"
                    variant="outlined"
                    icon={<ScienceIcon />}
                />
                <Chip label={`Материалов: ${materials.length}`} variant="outlined" />
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
                            rowData={recipeRows}
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
                </CardContent>
            </Card>

            {/* Диалог добавления рецепта */}
            <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
                <DialogTitle sx={{ fontWeight: 600 }}>Добавить рецепт</DialogTitle>
                <DialogContent>
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
                        <FormControl fullWidth>
                            <InputLabel>Продукт (ПФ)</InputLabel>
                            <Select
                                value={formData.product_id}
                                label="Продукт (ПФ)"
                                onChange={(e) => setFormData({ ...formData, product_id: e.target.value })}
                            >
                                <MenuItem value="">— Выберите продукт —</MenuItem>
                                {materials
                                    .filter((m) => m.category === 'RAW')
                                    .map((m) => (
                                        <MenuItem key={m.id} value={m.id}>
                                            {m.code} - {m.name}
                                        </MenuItem>
                                    ))}
                            </Select>
                        </FormControl>
                        <TextField
                            label="Базовый объём (кг)"
                            type="number"
                            fullWidth
                            value={formData.base_volume_kg}
                            onChange={(e) =>
                                setFormData({ ...formData, base_volume_kg: Number(e.target.value) })
                            }
                            helperText="Обычно 100 кг"
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
                        Сохранить
                    </Button>
                </DialogActions>
            </Dialog>

            {/* Диалог просмотра состава рецепта */}
            <Dialog
                open={selectedRecipe !== null}
                onClose={() => setSelectedRecipe(null)}
                maxWidth="md"
                fullWidth
            >
                <DialogTitle sx={{ fontWeight: 600 }}>
                    {selectedRecipe && `Состав: ${selectedRecipe.product_name} (${selectedRecipe.base_volume_kg} кг)`}
                </DialogTitle>
                <DialogContent>
                    {selectedRecipe && (
                        <TableContainer component={Paper} variant="outlined">
                            <Table size="small">
                                <TableHead>
                                    <TableRow>
                                        <TableCell>Код</TableCell>
                                        <TableCell>Наименование</TableCell>
                                        <TableCell align="right">Кол-во на базу</TableCell>
                                        <TableCell>Ед.</TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {selectedRecipe.items.map((item: RecipeItem) => (
                                        <TableRow key={item.id}>
                                            <TableCell>{item.material_code}</TableCell>
                                            <TableCell>{item.material_name}</TableCell>
                                            <TableCell align="right">{item.qty_per_base}</TableCell>
                                            <TableCell>{item.material_unit}</TableCell>
                                        </TableRow>
                                    ))}
                                    {selectedRecipe.items.length === 0 && (
                                        <TableRow>
                                            <TableCell colSpan={4} align="center">
                                                Компоненты не добавлены
                                            </TableCell>
                                        </TableRow>
                                    )}
                                </TableBody>
                            </Table>
                        </TableContainer>
                    )}
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setSelectedRecipe(null)}>Закрыть</Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
};

export default RecipesPage;