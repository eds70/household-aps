// frontend/src/pages/RecipesPage.tsx
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
    Paper,
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
import {
    Add as AddIcon,
    Delete as DeleteIcon,
    InfoOutlined as InfoOutlinedIcon,
    Science as ScienceIcon,
} from '@mui/icons-material';
import {AgGridReact} from 'ag-grid-react';
import type {ColDef, GridReadyEvent} from 'ag-grid-community';
import {AllCommunityModule, ModuleRegistry} from 'ag-grid-community';
import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-alpine.css';
import type {Material, Recipe, RecipeItem} from '../types';
import {materialsApi, recipesApi} from '../services/api';
import DraggableDialog from '../components/common/DraggableDialog';

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
            width: 120,
            cellClass: 'ag-cell-actions',
            editable: false,
            cellRenderer: (params: any) => (
                <Box
                    sx={{
                        display: 'flex',
                        gap: 0.5,
                        alignItems: 'center',
                        justifyContent: 'center',
                        width: '100%',
                        height: '100%',
                    }}
                >
                    <Tooltip title="Показать состав рецепта" arrow>
                        <IconButton
                            size="small"
                            color="primary"
                            onClick={() => handleViewRecipe(params.data.id)}
                        >
                            <InfoOutlinedIcon fontSize="small" />
                        </IconButton>
                    </Tooltip>
                    <Tooltip title="Удалить" arrow>
                        <IconButton
                            size="small"
                            color="error"
                            onClick={() => handleDelete(params.data.id)}
                        >
                            <DeleteIcon fontSize="small" />
                        </IconButton>
                    </Tooltip>
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

            {/* Диалог добавления рецепта (DraggableDialog) */}
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
                        <Button onClick={handleSave} variant="contained">
                            Сохранить
                        </Button>
                    </>
                }
            >
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
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
            </DraggableDialog>

            {/* Диалог просмотра состава рецепта (DraggableDialog) */}
            <DraggableDialog
                open={selectedRecipe !== null}
                onClose={() => setSelectedRecipe(null)}
                title={
                    selectedRecipe
                        ? `Состав: ${selectedRecipe.product_name} (${selectedRecipe.base_volume_kg} кг)`
                        : 'Состав рецепта'
                }
                initialWidth={700}
                initialHeight="auto"
                minWidth={480}
                minHeight={320}
                actions={
                    <Button onClick={() => setSelectedRecipe(null)}>Закрыть</Button>
                }
            >
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
            </DraggableDialog>
        </Box>
    );
};

export default RecipesPage;