// frontend/src/pages/MaterialsPage.tsx
import React, {useCallback, useEffect, useMemo, useState} from 'react';
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
    Tab,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Tabs,
    TextField,
    Tooltip,
    Typography,
} from '@mui/material';
import {
    Add as AddIcon,
    CloudUpload as CloudUploadIcon,
    Delete as DeleteIcon,
    Download as DownloadIcon,
    History as HistoryIcon,
    Inventory as InventoryIcon,
    Refresh as RefreshIcon,
    Upload as UploadIcon,
} from '@mui/icons-material';
import {AgGridReact} from 'ag-grid-react';
import type {CellStyle, ColDef, GridReadyEvent} from 'ag-grid-community';
import {AllCommunityModule, ModuleRegistry} from 'ag-grid-community';
import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-alpine.css';
import type {Material, MaterialCategory, MaterialImportResponse, MaterialStockLogEntry,} from '../types';
import {materialsApi} from '../services/api';
import DraggableDialog from '../components/common/DraggableDialog';

ModuleRegistry.registerModules([AllCommunityModule]);

// ==========================================
// КОНСТАНТЫ
// ==========================================

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

const ACTION_LABELS: Record<string, string> = {
    INSERT: 'Создание',
    UPDATE: 'Изменение',
    DELETE: 'Удаление',
};

const ACTION_COLORS: Record<string, 'success' | 'info' | 'error'> = {
    INSERT: 'success',
    UPDATE: 'info',
    DELETE: 'error',
};

const SOURCE_LABELS: Record<string, string> = {
    MANUAL: 'Вручную',
    IMPORT: 'Импорт',
    SYSTEM: 'Система',
};

const SOURCE_COLORS: Record<string, 'primary' | 'warning' | 'default'> = {
    MANUAL: 'primary',
    IMPORT: 'warning',
    SYSTEM: 'default',
};

// ==========================================
// ВСПОМОГАТЕЛЬНОЕ: скачивание blob
// ==========================================

function downloadBlob(blob: Blob, filename: string) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// ==========================================
// КОМПОНЕНТ
// ==========================================

const MaterialsPage: React.FC = () => {
    const [activeTab, setActiveTab] = useState(0);

    // ---------- Справочник ----------
    const [materials, setMaterials] = useState<Material[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);
    const [dialogOpen, setDialogOpen] = useState(false);
    const [filterCategory, setFilterCategory] = useState<string>('ALL');

    const [formData, setFormData] = useState<Partial<Material> & {
        initial_qty?: number;
        initial_reserved_qty?: number;
    }>({
        code: '',
        name: '',
        unit: 'kg',
        category: 'RAW',
        comment: '',
        initial_qty: 0,
        initial_reserved_qty: 0,
    });

    // ---------- Журнал ----------
    const [logEntries, setLogEntries] = useState<MaterialStockLogEntry[]>([]);
    const [logTotal, setLogTotal] = useState(0);
    const [logLoading, setLogLoading] = useState(false);
    const [logFilterMaterial, setLogFilterMaterial] = useState<string>('');
    const [logFilterSource, setLogFilterSource] = useState<string>('');
    const [logLimit, setLogLimit] = useState<number>(200);
    const [logDateFrom, setLogDateFrom] = useState<string>('');
    const [logDateTo, setLogDateTo] = useState<string>('');

    // ---------- Импорт ----------
    const [importDialogOpen, setImportDialogOpen] = useState(false);
    const [importFile, setImportFile] = useState<File | null>(null);
    const [importing, setImporting] = useState(false);
    const [importResult, setImportResult] = useState<MaterialImportResponse | null>(null);

    // ---------- Rollback + Cleanup (Итерация 13.3) ----------
    const [reverting, setReverting] = useState<string | null>(null);
    const [cleanupDialogOpen, setCleanupDialogOpen] = useState(false);
    const [cleanupDays, setCleanupDays] = useState<number>(90);
    const [cleanupSource, setCleanupSource] = useState<string>('');
    const [cleaning, setCleaning] = useState(false);

    // ==========================================
    // ЗАГРУЗКА
    // ==========================================
    const loadMaterials = useCallback(async () => {
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
    }, []);

    const loadLog = useCallback(async () => {
        setLogLoading(true);
        try {
            const data = await materialsApi.getStockLog({
                material_id: logFilterMaterial || undefined,
                source: logFilterSource || undefined,
                date_from: logDateFrom ? new Date(logDateFrom).toISOString() : undefined,
                date_to: logDateTo ? new Date(logDateTo + 'T23:59:59').toISOString() : undefined,
                limit: logLimit,
            });
            setLogEntries(data.entries);
            setLogTotal(data.total);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Ошибка загрузки журнала');
        } finally {
            setLogLoading(false);
        }
    }, [logFilterMaterial, logFilterSource, logDateFrom, logDateTo, logLimit]);

    useEffect(() => {
        loadMaterials();
    }, [loadMaterials]);

    useEffect(() => {
        if (activeTab === 1) {
            loadLog();
        }
    }, [activeTab, loadLog]);

    const showSuccess = (msg: string, ms = 3000) => {
        setSuccess(msg);
        setTimeout(() => setSuccess(null), ms);
    };

    // ==========================================
    // AGGrid КОЛОНКИ (СПРАВОЧНИК)
    // ==========================================
    const filteredMaterials = useMemo(
        () =>
            filterCategory === 'ALL'
                ? materials
                : materials.filter((m) => m.category === filterCategory),
        [materials, filterCategory],
    );

    const columnDefs: ColDef<Material>[] = useMemo(
        () => [
            { headerName: 'Код', field: 'code', width: 120, editable: true },
            { headerName: 'Наименование', field: 'name', flex: 2, minWidth: 200, editable: true },
            {
                headerName: 'Категория',
                field: 'category',
                width: 140,
                editable: true,
                cellEditor: 'agSelectCellEditor',
                cellEditorParams: { values: ['RAW', 'PACKAGING', 'LABEL'] },
                valueFormatter: (params) =>
                    CATEGORY_LABELS[params.value as MaterialCategory] || params.value,
            },
            {
                headerName: 'Ед. изм.',
                field: 'unit',
                width: 90,
                editable: true,
                cellEditor: 'agSelectCellEditor',
                cellEditorParams: { values: ['kg', 'pc', 'l'] },
                valueFormatter: (params) => UNIT_LABELS[params.value] || params.value,
            },
            {
                headerName: 'Остаток',
                field: 'stock_qty',
                width: 130,
                editable: true,
                type: 'numericColumn',
                cellStyle: (params): CellStyle => {
                    const v = params.value as number | null | undefined;
                    if (v == null) return { color: '#bdc3c7' };
                    if (v <= 0) return { color: '#e74c3c', fontWeight: '600' };
                    return { color: '#27ae60', fontWeight: '600' };
                },
                valueFormatter: (params) => {
                    const v = params.value as number | null | undefined;
                    return v == null ? '—' : v.toFixed(2);
                },
                tooltipValueGetter: () => 'Двойной клик для изменения остатка',
            },
            {
                headerName: 'Резерв',
                field: 'reserved_qty',
                width: 120,
                editable: true,
                type: 'numericColumn',
                cellStyle: (params): CellStyle => {
                    const v = params.value as number | null | undefined;
                    if (v && v > 0) return { color: '#e67e22', fontWeight: '600' };
                    return { color: '#95a5a6' };
                },
                valueFormatter: (params) => {
                    const v = params.value as number | null | undefined;
                    return v == null ? '—' : v.toFixed(2);
                },
            },
            {
                headerName: 'Доступно',
                width: 120,
                editable: false,
                type: 'numericColumn',
                valueGetter: (params) => {
                    const qty = Number(params.data?.stock_qty || 0);
                    const reserved = Number(params.data?.reserved_qty || 0);
                    return Math.max(0, qty - reserved);
                },
                cellStyle: (): CellStyle => ({
                    fontWeight: '700',
                    color: '#2c3e50',
                }),
                valueFormatter: (params) => Number(params.value).toFixed(2),
            },
            {
                headerName: 'Комментарий',
                field: 'comment',
                flex: 1,
                editable: true,
                valueFormatter: (params) => params.value || '—',
            },
            {
                headerName: 'Действия',
                width: 90,
                editable: false,
                cellRenderer: (params: any) => (
                    <Tooltip title="Удалить материал">
                        <IconButton
                            color="error"
                            size="small"
                            onClick={() => handleDelete(params.data.id)}
                        >
                            <DeleteIcon fontSize="small" />
                        </IconButton>
                    </Tooltip>
                ),
            },
        ],
        [],
    );

    const defaultColDef: ColDef = {
        sortable: true,
        filter: true,
        resizable: true,
        editable: true,
        singleClickEdit: false,
    };

    // ==========================================
    // ОБРАБОТЧИКИ СПРАВОЧНИКА
    // ==========================================
    const handleCellValueChanged = async (params: any) => {
        const { data, colDef, newValue } = params;
        const field = colDef.field as string;
        if (!field) return;
        const oldValue = data[field];

        if (field === 'stock_qty' || field === 'reserved_qty') {
            const parsed = Number(newValue);
            if (isNaN(parsed) || parsed < 0) {
                setError('Остаток должен быть неотрицательным числом');
                setMaterials((prev) =>
                    prev.map((m) => (m.id === data.id ? { ...m, [field]: oldValue } : m)),
                );
                return;
            }
            try {
                const stockUpdate: { qty?: number; reserved_qty?: number } = {};
                if (field === 'stock_qty') stockUpdate.qty = parsed;
                if (field === 'reserved_qty') stockUpdate.reserved_qty = parsed;

                await materialsApi.updateStock(data.id, stockUpdate);
                setMaterials((prev) =>
                    prev.map((m) => (m.id === data.id ? { ...m, [field]: parsed } : m)),
                );
                showSuccess(`Остаток обновлён: ${data.name} → ${parsed.toFixed(2)}`);
            } catch (err: any) {
                setError(err.response?.data?.detail || 'Ошибка сохранения остатка');
                setMaterials((prev) =>
                    prev.map((m) => (m.id === data.id ? { ...m, [field]: oldValue } : m)),
                );
            }
            return;
        }

        try {
            await materialsApi.update(data.id, { [field]: newValue });
            setMaterials((prev) =>
                prev.map((m) => (m.id === data.id ? { ...m, [field]: newValue } : m)),
            );
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Ошибка сохранения');
            setMaterials((prev) =>
                prev.map((m) => (m.id === data.id ? { ...m, [field]: oldValue } : m)),
            );
        }
    };

    const handleDelete = async (id: string) => {
        if (!window.confirm('Удалить материал? Все остатки и история будут удалены.')) return;
        try {
            await materialsApi.delete(id);
            setMaterials((prev) => prev.filter((m) => m.id !== id));
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Ошибка удаления');
        }
    };

    const handleAdd = () => {
        setFormData({
            code: '', name: '', unit: 'kg', category: 'RAW', comment: '',
            initial_qty: 0, initial_reserved_qty: 0,
        });
        setDialogOpen(true);
    };

    const handleSave = async () => {
        if (!formData.code?.trim() || !formData.name?.trim()) {
            setError('Заполните код и наименование');
            return;
        }
        try {
            const response = await materialsApi.create({
                ...formData,
                organization_id: '00000000-0000-0000-0000-000000000001',
            });
            setMaterials((prev) => [...prev, response]);
            setDialogOpen(false);
            showSuccess(`Материал создан: ${response.name}`);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Ошибка создания');
        }
    };

    // ==========================================
    // ИМПОРТ / ЭКСПОРТ
    // ==========================================
    const handleDownloadTemplate = async () => {
        try {
            const blob = await materialsApi.downloadImportTemplate();
            downloadBlob(blob, 'materials_import_template.xlsx');
        } catch (err: any) {
            setError('Ошибка скачивания шаблона');
        }
    };

    const handleExport = async () => {
        try {
            const blob = await materialsApi.exportExcel();
            downloadBlob(blob, `materials_export_${new Date().toISOString().slice(0, 10)}.xlsx`);
            showSuccess('Экспорт завершён');
        } catch (err: any) {
            setError('Ошибка экспорта');
        }
    };

    const handleOpenImport = () => {
        setImportFile(null);
        setImportResult(null);
        setImportDialogOpen(true);
    };

    const handleDoImport = async () => {
        if (!importFile) {
            setError('Выберите файл');
            return;
        }
        setImporting(true);
        setImportResult(null);
        try {
            const result = await materialsApi.importExcel(importFile);
            setImportResult(result);
            await loadMaterials();
            if (activeTab === 1) {
                await loadLog();
            }
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Ошибка импорта');
        } finally {
            setImporting(false);
        }
    };

    // ==========================================
    // ИТЕРАЦИЯ 13.3: ROLLBACK + CLEANUP
    // ==========================================
    const handleRevert = async (logId: string) => {
        if (!window.confirm(
            'Отменить это изменение остатков?\n\n' +
            'Будет создана НОВАЯ запись в журнале (source=MANUAL, reason=Откат).'
        )) return;

        setReverting(logId);
        try {
            const result = await materialsApi.revertStockLog(logId);
            showSuccess(result.message);
            await Promise.all([loadMaterials(), loadLog()]);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Ошибка отката');
        } finally {
            setReverting(null);
        }
    };

    const handleCleanup = async () => {
        setCleaning(true);
        try {
            const result = await materialsApi.cleanupStockLog(
                cleanupDays,
                cleanupSource || undefined,
            );
            showSuccess(result.message);
            setCleanupDialogOpen(false);
            await loadLog();
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Ошибка очистки');
        } finally {
            setCleaning(false);
        }
    };

    // ==========================================
    // РЕНДЕР
    // ==========================================
    if (loading && materials.length === 0) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', mt: 8 }}>
                <CircularProgress />
            </Box>
        );
    }

    const totalStock = materials.reduce((s, m) => s + (m.stock_qty || 0), 0);
    const zeroStockCount = materials.filter((m) => (m.stock_qty || 0) <= 0).length;

    return (
        <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            {/* ====== ШАПКА ====== */}
            <Box
                sx={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    mb: 2,
                    flexWrap: 'wrap',
                    gap: 2,
                }}
            >
                <Typography variant="h4" component="h1" sx={{ fontWeight: 600, color: '#2c3e50' }}>
                    Справочник материалов
                </Typography>
                <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                    <Button
                        variant="outlined"
                        startIcon={<DownloadIcon />}
                        onClick={handleDownloadTemplate}
                        sx={{ textTransform: 'none' }}
                    >
                        Шаблон
                    </Button>
                    <Button
                        variant="outlined"
                        startIcon={<CloudUploadIcon />}
                        onClick={handleExport}
                        sx={{ textTransform: 'none' }}
                    >
                        Экспорт
                    </Button>
                    <Button
                        variant="outlined"
                        color="warning"
                        startIcon={<UploadIcon />}
                        onClick={handleOpenImport}
                        sx={{ textTransform: 'none' }}
                    >
                        Импорт из Excel
                    </Button>
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

            {/* ====== ALERTS ====== */}
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

            {/* ====== ЧИПЫ-СТАТИСТИКА ====== */}
            <Box sx={{ display: 'flex', gap: 1, mb: 2, flexWrap: 'wrap' }}>
                <Chip
                    label={`Всего: ${materials.length}`}
                    color="primary"
                    variant="outlined"
                    icon={<InventoryIcon />}
                />
                <Chip
                    label={`Сырьё: ${materials.filter((m) => m.category === 'RAW').length}`}
                    variant="outlined"
                />
                <Chip
                    label={`Упаковка: ${materials.filter((m) => m.category === 'PACKAGING').length}`}
                    variant="outlined"
                />
                <Chip
                    label={`Суммарный остаток: ${totalStock.toFixed(0)}`}
                    color="success"
                    variant="outlined"
                />
                {zeroStockCount > 0 && (
                    <Chip
                        label={`Нулевой остаток: ${zeroStockCount}`}
                        color="warning"
                        variant="filled"
                    />
                )}
            </Box>

            {/* ====== TABS ====== */}
            <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
                <Tabs value={activeTab} onChange={(_, v) => setActiveTab(v)}>
                    <Tab icon={<InventoryIcon />} iconPosition="start" label="Справочник" />
                    <Tab
                        icon={<HistoryIcon />}
                        iconPosition="start"
                        label={`Журнал изменений${logTotal > 0 ? ` (${logTotal})` : ''}`}
                    />
                </Tabs>
            </Box>

            {/* ====== TAB 0: СПРАВОЧНИК ====== */}
            {activeTab === 0 && (
                <>
                    <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
                        <FormControl size="small" variant="outlined" sx={{ minWidth: 220 }}>
                            <InputLabel>Фильтр по категории</InputLabel>
                            <Select
                                value={filterCategory}
                                label="Фильтр по категории"
                                variant="outlined"
                                onChange={(e) => setFilterCategory(e.target.value)}
                            >
                                <MenuItem value="ALL">Все категории</MenuItem>
                                <MenuItem value="RAW">Сырьё</MenuItem>
                                <MenuItem value="PACKAGING">Упаковка</MenuItem>
                                <MenuItem value="LABEL">Этикетки</MenuItem>
                            </Select>
                        </FormControl>
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
                            <Box
                                className="ag-theme-alpine"
                                sx={{ flexGrow: 1, width: '100%', minHeight: 0 }}
                            >
                                <AgGridReact
                                    rowData={filteredMaterials}
                                    columnDefs={columnDefs}
                                    defaultColDef={defaultColDef}
                                    getRowId={(p) => p.data.id}
                                    pagination
                                    paginationPageSize={20}
                                    paginationPageSizeSelector={[20, 50, 100]}
                                    onCellValueChanged={handleCellValueChanged}
                                    suppressPropertyNamesCheck
                                    onGridReady={(p: GridReadyEvent) => p.api.sizeColumnsToFit()}
                                />
                            </Box>
                        </CardContent>
                    </Card>

                    <Typography
                        variant="caption"
                        color="text.secondary"
                        sx={{ mt: 1, display: 'block', textAlign: 'center' }}
                    >
                        💡 Двойной клик по ячейке «Остаток» / «Резерв» — редактирование.
                        Все изменения автоматически попадают в «Журнал изменений».
                    </Typography>
                </>
            )}

            {/* ====== TAB 1: ЖУРНАЛ ====== */}
            {activeTab === 1 && (
                <>
                    <Box
                        sx={{
                            display: 'flex',
                            gap: 2,
                            mb: 2,
                            flexWrap: 'wrap',
                            alignItems: 'center',
                        }}
                    >
                        <FormControl size="small" variant="outlined" sx={{ minWidth: 220 }}>
                            <InputLabel>Материал</InputLabel>
                            <Select
                                value={logFilterMaterial}
                                label="Материал"
                                variant="outlined"
                                onChange={(e) => setLogFilterMaterial(e.target.value)}
                            >
                                <MenuItem value="">— Все материалы —</MenuItem>
                                {materials.map((m) => (
                                    <MenuItem key={m.id} value={m.id}>
                                        {m.code} — {m.name}
                                    </MenuItem>
                                ))}
                            </Select>
                        </FormControl>

                        <FormControl size="small" variant="outlined" sx={{ minWidth: 160 }}>
                            <InputLabel>Источник</InputLabel>
                            <Select
                                value={logFilterSource}
                                label="Источник"
                                variant="outlined"
                                onChange={(e) => setLogFilterSource(e.target.value)}
                            >
                                <MenuItem value="">— Все —</MenuItem>
                                <MenuItem value="MANUAL">Вручную</MenuItem>
                                <MenuItem value="IMPORT">Импорт</MenuItem>
                                <MenuItem value="SYSTEM">Система</MenuItem>
                            </Select>
                        </FormControl>

                        <TextField
                            size="small"
                            type="date"
                            label="С даты"
                            value={logDateFrom}
                            onChange={(e) => setLogDateFrom(e.target.value)}
                            slotProps={{ inputLabel: { shrink: true } }}
                            sx={{ width: 170 }}
                        />
                        <TextField
                            size="small"
                            type="date"
                            label="По дату"
                            value={logDateTo}
                            onChange={(e) => setLogDateTo(e.target.value)}
                            slotProps={{ inputLabel: { shrink: true } }}
                            sx={{ width: 170 }}
                        />

                        <TextField
                            size="small"
                            type="number"
                            label="Лимит"
                            value={logLimit}
                            onChange={(e) => setLogLimit(Number(e.target.value) || 200)}
                            sx={{ width: 100 }}
                            slotProps={{ htmlInput: { min: 10, max: 1000, step: 10 } }}
                        />

                        <Button
                            variant="outlined"
                            startIcon={<RefreshIcon />}
                            onClick={loadLog}
                            disabled={logLoading}
                            sx={{ textTransform: 'none' }}
                        >
                            Обновить
                        </Button>

                        <Button
                            size="small"
                            variant="text"
                            onClick={() => {
                                const today = new Date().toISOString().slice(0, 10);
                                setLogDateFrom(today);
                                setLogDateTo(today);
                            }}
                            sx={{ textTransform: 'none' }}
                        >
                            Сегодня
                        </Button>
                        <Button
                            size="small"
                            variant="text"
                            onClick={() => {
                                const now = new Date();
                                const week = new Date(now.getTime() - 7 * 24 * 3600 * 1000);
                                setLogDateFrom(week.toISOString().slice(0, 10));
                                setLogDateTo(now.toISOString().slice(0, 10));
                            }}
                            sx={{ textTransform: 'none' }}
                        >
                            Неделя
                        </Button>
                        <Button
                            size="small"
                            variant="text"
                            onClick={() => {
                                const now = new Date();
                                const month = new Date(now.getTime() - 30 * 24 * 3600 * 1000);
                                setLogDateFrom(month.toISOString().slice(0, 10));
                                setLogDateTo(now.toISOString().slice(0, 10));
                            }}
                            sx={{ textTransform: 'none' }}
                        >
                            Месяц
                        </Button>
                        <Button
                            size="small"
                            variant="text"
                            color="inherit"
                            onClick={() => {
                                setLogDateFrom('');
                                setLogDateTo('');
                                setLogFilterMaterial('');
                                setLogFilterSource('');
                            }}
                            sx={{ textTransform: 'none' }}
                        >
                            Сбросить
                        </Button>

                        <Button
                            size="small"
                            variant="outlined"
                            color="error"
                            startIcon={<DeleteIcon />}
                            onClick={() => setCleanupDialogOpen(true)}
                            sx={{ textTransform: 'none', ml: 'auto' }}
                        >
                            Очистить старые
                        </Button>

                        <Chip
                            label={`Показано: ${logEntries.length} / ${logTotal}`}
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
                                p: 0,
                                flexGrow: 1,
                                display: 'flex',
                                flexDirection: 'column',
                                minHeight: 0,
                            }}
                        >
                            {logLoading && logEntries.length === 0 ? (
                                <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                                    <CircularProgress />
                                </Box>
                            ) : logEntries.length === 0 ? (
                                <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
                                    <Typography color="text.secondary">
                                        Записей нет. Измените остаток или импортируйте данные из Excel.
                                    </Typography>
                                </Box>
                            ) : (
                                <TableContainer sx={{ flexGrow: 1, minHeight: 0 }}>
                                    <Table size="small" stickyHeader>
                                        <TableHead>
                                            <TableRow>
                                                <TableCell sx={{ fontWeight: 600 }}>Дата</TableCell>
                                                <TableCell sx={{ fontWeight: 600 }}>Материал</TableCell>
                                                <TableCell sx={{ fontWeight: 600 }} align="center">
                                                    Действие
                                                </TableCell>
                                                <TableCell sx={{ fontWeight: 600 }} align="right">
                                                    Было
                                                </TableCell>
                                                <TableCell sx={{ fontWeight: 600 }} align="right">
                                                    Стало
                                                </TableCell>
                                                <TableCell sx={{ fontWeight: 600 }} align="right">
                                                    Δ
                                                </TableCell>
                                                <TableCell sx={{ fontWeight: 600 }} align="center">
                                                    Источник
                                                </TableCell>
                                                <TableCell sx={{ fontWeight: 600 }}>Пользователь</TableCell>
                                                <TableCell sx={{ fontWeight: 600 }}>Причина</TableCell>
                                                <TableCell sx={{ fontWeight: 600 }} align="center">
                                                    Отмена
                                                </TableCell>
                                            </TableRow>
                                        </TableHead>
                                        <TableBody>
                                            {logEntries.map((e) => {
                                                const deltaNum = e.delta_qty ?? 0;
                                                const deltaColor =
                                                    deltaNum > 0
                                                        ? '#27ae60'
                                                        : deltaNum < 0
                                                            ? '#e74c3c'
                                                            : '#95a5a6';
                                                return (
                                                    <TableRow key={e.id} hover>
                                                        <TableCell>
                                                            <Typography variant="caption">
                                                                {new Date(e.changed_at).toLocaleString('ru-RU')}
                                                            </Typography>
                                                        </TableCell>
                                                        <TableCell>
                                                            <Typography
                                                                variant="body2"
                                                                sx={{ fontWeight: 600 }}
                                                            >
                                                                {e.material_code || '—'}
                                                            </Typography>
                                                            <Typography
                                                                variant="caption"
                                                                color="text.secondary"
                                                            >
                                                                {e.material_name || ''}
                                                            </Typography>
                                                        </TableCell>
                                                        <TableCell align="center">
                                                            <Chip
                                                                label={ACTION_LABELS[e.action] || e.action}
                                                                color={ACTION_COLORS[e.action] || 'default'}
                                                                size="small"
                                                            />
                                                        </TableCell>
                                                        <TableCell align="right">
                                                            <Typography variant="body2">
                                                                {e.old_qty != null
                                                                    ? e.old_qty.toFixed(2)
                                                                    : '—'}
                                                            </Typography>
                                                            {e.old_reserved_qty != null &&
                                                                e.old_reserved_qty > 0 && (
                                                                    <Typography
                                                                        variant="caption"
                                                                        color="text.secondary"
                                                                    >
                                                                        (рез.{' '}
                                                                        {e.old_reserved_qty.toFixed(2)})
                                                                    </Typography>
                                                                )}
                                                        </TableCell>
                                                        <TableCell align="right">
                                                            <Typography
                                                                variant="body2"
                                                                sx={{ fontWeight: 600 }}
                                                            >
                                                                {e.new_qty != null
                                                                    ? e.new_qty.toFixed(2)
                                                                    : '—'}
                                                            </Typography>
                                                            {e.new_reserved_qty != null &&
                                                                e.new_reserved_qty > 0 && (
                                                                    <Typography
                                                                        variant="caption"
                                                                        color="text.secondary"
                                                                    >
                                                                        (рез.{' '}
                                                                        {e.new_reserved_qty.toFixed(2)})
                                                                    </Typography>
                                                                )}
                                                        </TableCell>
                                                        <TableCell align="right">
                                                            <Typography
                                                                variant="body2"
                                                                sx={{ fontWeight: 700, color: deltaColor }}
                                                            >
                                                                {deltaNum > 0 ? '+' : ''}
                                                                {deltaNum.toFixed(2)}
                                                            </Typography>
                                                        </TableCell>
                                                        <TableCell align="center">
                                                            <Chip
                                                                label={
                                                                    SOURCE_LABELS[e.source || 'SYSTEM'] ||
                                                                    e.source
                                                                }
                                                                color={
                                                                    SOURCE_COLORS[e.source || 'SYSTEM'] ||
                                                                    'default'
                                                                }
                                                                size="small"
                                                                variant="outlined"
                                                            />
                                                        </TableCell>
                                                        <TableCell>
                                                            <Typography variant="caption">
                                                                {e.changed_by_name || '—'}
                                                            </Typography>
                                                        </TableCell>
                                                        <TableCell>
                                                            <Tooltip title={e.reason || e.comment || ''}>
                                                                <Typography
                                                                    variant="caption"
                                                                    sx={{
                                                                        maxWidth: 200,
                                                                        display: 'inline-block',
                                                                        overflow: 'hidden',
                                                                        textOverflow: 'ellipsis',
                                                                        whiteSpace: 'nowrap',
                                                                    }}
                                                                >
                                                                    {e.reason || e.comment || '—'}
                                                                </Typography>
                                                            </Tooltip>
                                                        </TableCell>
                                                        <TableCell align="center">
                                                            <Tooltip title="Отменить это изменение">
                                                                <span>
                                                                    <IconButton
                                                                        size="small"
                                                                        color="warning"
                                                                        onClick={() => handleRevert(e.id)}
                                                                        disabled={reverting === e.id}
                                                                    >
                                                                        {reverting === e.id ? (
                                                                            <CircularProgress size={16} />
                                                                        ) : (
                                                                            <HistoryIcon fontSize="small" />
                                                                        )}
                                                                    </IconButton>
                                                                </span>
                                                            </Tooltip>
                                                        </TableCell>
                                                    </TableRow>
                                                );
                                            })}
                                        </TableBody>
                                    </Table>
                                </TableContainer>
                            )}
                        </CardContent>
                    </Card>
                </>
            )}

            {/* ====== ДИАЛОГ ДОБАВЛЕНИЯ МАТЕРИАЛА (DraggableDialog) ====== */}
            <DraggableDialog
                open={dialogOpen}
                onClose={() => setDialogOpen(false)}
                title="Добавить материал"
                initialWidth={700}
                initialHeight="auto"
                minWidth={480}
                minHeight={400}
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
                    <Box sx={{ display: 'flex', gap: 2 }}>
                        <TextField
                            label="Код материала"
                            fullWidth
                            required
                            value={formData.code}
                            onChange={(e) =>
                                setFormData({ ...formData, code: e.target.value })
                            }
                        />
                        <FormControl fullWidth variant="outlined">
                            <InputLabel>Категория</InputLabel>
                            <Select
                                value={formData.category}
                                label="Категория"
                                variant="outlined"
                                onChange={(e) =>
                                    setFormData({
                                        ...formData,
                                        category: e.target.value as MaterialCategory,
                                    })
                                }
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
                        required
                        value={formData.name}
                        onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    />
                    <FormControl fullWidth variant="outlined">
                        <InputLabel>Единица измерения</InputLabel>
                        <Select
                            value={formData.unit}
                            label="Единица измерения"
                            variant="outlined"
                            onChange={(e) =>
                                setFormData({ ...formData, unit: e.target.value })
                            }
                        >
                            <MenuItem value="kg">Килограммы (кг)</MenuItem>
                            <MenuItem value="pc">Штуки (шт)</MenuItem>
                            <MenuItem value="l">Литры (л)</MenuItem>
                        </Select>
                    </FormControl>

                    <Typography variant="subtitle2" sx={{ mt: 1, fontWeight: 600 }}>
                        Начальные остатки
                    </Typography>
                    <Box sx={{ display: 'flex', gap: 2 }}>
                        <TextField
                            label="Остаток на складе"
                            type="number"
                            fullWidth
                            value={formData.initial_qty ?? 0}
                            onChange={(e) =>
                                setFormData({
                                    ...formData,
                                    initial_qty: Number(e.target.value),
                                })
                            }
                            slotProps={{ htmlInput: { min: 0, step: 0.01 } }}
                        />
                        <TextField
                            label="Зарезервировано"
                            type="number"
                            fullWidth
                            value={formData.initial_reserved_qty ?? 0}
                            onChange={(e) =>
                                setFormData({
                                    ...formData,
                                    initial_reserved_qty: Number(e.target.value),
                                })
                            }
                            slotProps={{ htmlInput: { min: 0, step: 0.01 } }}
                        />
                    </Box>
                    <Alert severity="info">
                        Доступное количество ={' '}
                        {(
                            (formData.initial_qty ?? 0) -
                            (formData.initial_reserved_qty ?? 0)
                        ).toFixed(2)}{' '}
                        {formData.unit}
                    </Alert>
                    <TextField
                        label="Комментарий"
                        fullWidth
                        multiline
                        rows={2}
                        value={formData.comment}
                        onChange={(e) =>
                            setFormData({ ...formData, comment: e.target.value })
                        }
                    />
                </Box>
            </DraggableDialog>

            {/* ====== ДИАЛОГ ИМПОРТА (DraggableDialog) ====== */}
            <DraggableDialog
                open={importDialogOpen}
                onClose={() => !importing && setImportDialogOpen(false)}
                title="Импорт материалов из Excel"
                initialWidth={900}
                initialHeight={600}
                minWidth={640}
                minHeight={400}
                actions={
                    <>
                        <Button
                            onClick={() => setImportDialogOpen(false)}
                            disabled={importing}
                        >
                            {importResult ? 'Закрыть' : 'Отмена'}
                        </Button>
                        <Button
                            onClick={handleDoImport}
                            variant="contained"
                            color="warning"
                            disabled={!importFile || importing}
                            startIcon={importing ? <CircularProgress size={18} /> : <UploadIcon />}
                        >
                            {importing ? 'Импорт...' : 'Импортировать'}
                        </Button>
                    </>
                }
            >
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                    <Alert severity="info">
                        <b>Формат:</b> колонки «Код», «Наименование», «Категория», «Ед.изм.»,
                        «Остаток», «Резерв».
                        <br />
                        <b>Логика:</b> если материал с таким «Код» уже есть — обновляем
                        (справочные поля + остатки). Если нет — создаём.
                        <br />
                        Не забудьте сначала <b>скачать шаблон</b> — там уже правильные
                        заголовки.
                    </Alert>

                    <Button
                        variant="outlined"
                        component="label"
                        startIcon={<UploadIcon />}
                        sx={{ alignSelf: 'flex-start', textTransform: 'none' }}
                        disabled={importing}
                    >
                        Выбрать файл .xlsx
                        <input
                            type="file"
                            hidden
                            accept=".xlsx,.xlsm"
                            onChange={(e) => {
                                const f = e.target.files?.[0] || null;
                                setImportFile(f);
                                setImportResult(null);
                            }}
                        />
                    </Button>

                    {importFile && (
                        <Chip
                            label={`📄 ${importFile.name} (${(
                                importFile.size / 1024
                            ).toFixed(1)} KB)`}
                            color="primary"
                            variant="outlined"
                            onDelete={() => setImportFile(null)}
                        />
                    )}

                    {importResult && (
                        <>
                            <Alert
                                severity={importResult.errors > 0 ? 'warning' : 'success'}
                            >
                                {importResult.message}
                            </Alert>

                            <TableContainer sx={{ maxHeight: 400 }}>
                                <Table size="small" stickyHeader>
                                    <TableHead>
                                        <TableRow>
                                            <TableCell>#</TableCell>
                                            <TableCell>Код</TableCell>
                                            <TableCell>Наименование</TableCell>
                                            <TableCell align="right">Остаток</TableCell>
                                            <TableCell align="center">Статус</TableCell>
                                            <TableCell>Сообщение</TableCell>
                                        </TableRow>
                                    </TableHead>
                                    <TableBody>
                                        {importResult.rows.map((r, i) => (
                                            <TableRow key={i} hover>
                                                <TableCell>{r.row_number}</TableCell>
                                                <TableCell>
                                                    <Typography
                                                        variant="caption"
                                                        sx={{ fontFamily: 'monospace' }}
                                                    >
                                                        {r.code || '—'}
                                                    </Typography>
                                                </TableCell>
                                                <TableCell>{r.name || '—'}</TableCell>
                                                <TableCell align="right">
                                                    {r.qty != null ? r.qty.toFixed(2) : '—'}
                                                </TableCell>
                                                <TableCell align="center">
                                                    <Chip
                                                        label={r.status}
                                                        color={
                                                            r.status === 'CREATED'
                                                                ? 'success'
                                                                : r.status === 'UPDATED'
                                                                    ? 'info'
                                                                    : r.status === 'SKIPPED'
                                                                        ? 'default'
                                                                        : 'error'
                                                        }
                                                        size="small"
                                                    />
                                                </TableCell>
                                                <TableCell>
                                                    <Typography variant="caption">
                                                        {r.message || ''}
                                                    </Typography>
                                                </TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </TableContainer>
                        </>
                    )}
                </Box>
            </DraggableDialog>

            {/* ====== ДИАЛОГ ОЧИСТКИ ЖУРНАЛА (DraggableDialog) ====== */}
            <DraggableDialog
                open={cleanupDialogOpen}
                onClose={() => !cleaning && setCleanupDialogOpen(false)}
                title="Очистка журнала изменений"
                initialWidth={600}
                initialHeight="auto"
                minWidth={480}
                minHeight={320}
                actions={
                    <>
                        <Button
                            onClick={() => setCleanupDialogOpen(false)}
                            disabled={cleaning}
                        >
                            Отмена
                        </Button>
                        <Button
                            onClick={handleCleanup}
                            variant="contained"
                            color="error"
                            disabled={cleaning}
                            startIcon={
                                cleaning ? <CircularProgress size={18} /> : <DeleteIcon />
                            }
                        >
                            {cleaning ? 'Очистка...' : 'Очистить'}
                        </Button>
                    </>
                }
            >
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                    <Alert severity="warning">
                        Удаляются <b>записи журнала</b> (не остатки!). Откат удалённых
                        записей станет невозможен. Сами остатки материалов{' '}
                        <b>не меняются</b>.
                    </Alert>

                    <TextField
                        label="Удалить записи старше (дней)"
                        type="number"
                        fullWidth
                        value={cleanupDays}
                        onChange={(e) => setCleanupDays(Number(e.target.value) || 90)}
                        slotProps={{ htmlInput: { min: 1, max: 3650, step: 1 } }}
                        helperText="Например: 90 — удалить всё старше 3 месяцев"
                    />

                    <FormControl fullWidth variant="outlined">
                        <InputLabel>Источник (опционально)</InputLabel>
                        <Select
                            value={cleanupSource}
                            label="Источник (опционально)"
                            variant="outlined"
                            onChange={(e) => setCleanupSource(e.target.value)}
                        >
                            <MenuItem value="">Все источники</MenuItem>
                            <MenuItem value="MANUAL">Только MANUAL</MenuItem>
                            <MenuItem value="IMPORT">Только IMPORT</MenuItem>
                            <MenuItem value="SYSTEM">Только SYSTEM</MenuItem>
                        </Select>
                    </FormControl>
                </Box>
            </DraggableDialog>
        </Box>
    );
};

export default MaterialsPage;