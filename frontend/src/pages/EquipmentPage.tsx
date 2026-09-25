// frontend/src/pages/EquipmentPage.tsx
import React, {useCallback, useEffect, useRef, useState} from "react";
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
    Typography,
} from "@mui/material";
import {
    Add as AddIcon,
    Build as BuildIcon,
    Delete as DeleteIcon,
    Lock as LockIcon,
    Refresh as RefreshIcon,
} from "@mui/icons-material";
import {AgGridReact} from "ag-grid-react";
import type {ColDef, GridReadyEvent, RowClickedEvent} from "ag-grid-community";
import {AllCommunityModule, ModuleRegistry} from "ag-grid-community";
import "ag-grid-community/styles/ag-grid.css";
import "ag-grid-community/styles/ag-theme-alpine.css";
import {Timeline} from "vis-timeline/standalone";
import {DataSet} from "vis-data";
import "vis-timeline/styles/vis-timeline-graph2d.min.css";
import {Allotment} from "allotment";
import "allotment/dist/style.css";
import type {CalendarEvent, Equipment} from "../types";
import {usePlan} from "../context/PlainContext";
import {calendarApi, equipmentApi} from "../services/api";
import axios from "axios";
import {API_BASE_URL} from "../config";
import DraggableDialog from "../components/common/DraggableDialog";

ModuleRegistry.registerModules([AllCommunityModule]);

// ---------- Константы ----------
const EQUIPMENT_TYPE_TRANSLATIONS: Record<string, string> = {
    REACTOR: "Реактор",
    BOILER: "Бойлер",
    TANK: "Емкость",
    FILLING_LINE: "Линия розлива",
    MANUAL_STATION: "Ручная станция",
};

const EQUIPMENT_TYPE_REVERSE: Record<string, string> = {
    Реактор: "REACTOR",
    Бойлер: "BOILER",
    Емкость: "TANK",
    "Линия розлива": "FILLING_LINE",
    "Ручная станция": "MANUAL_STATION",
};

const MIXER_TYPE_TRANSLATIONS: Record<string, string> = {
    standard: "Стандартная",
    high_speed: "Высокоскоростная",
    low_speed: "Низкоскоростная",
};

const MIXER_TYPE_REVERSE: Record<string, string> = {
    Стандартная: "standard",
    Высокоскоростная: "high_speed",
    Низкоскоростная: "low_speed",
};

const EVENT_TYPE_LABELS: Record<string, string> = {
    REPAIR: "Плановый ремонт",
    BREAKDOWN: "Аварийная остановка",
    WEEKEND: "Выходные",
    SHIFT_END: "Конец смены",
    LUNCH: "Обед",
};

const EVENT_TYPE_COLORS: Record<string, string> = {
    REPAIR: "#e67e22",
    BREAKDOWN: "#e74c3c",
    WEEKEND: "#95a5a6",
    SHIFT_END: "#3498db",
    LUNCH: "#9b59b6",
};

// ---------- Компонент ----------
const EquipmentPage: React.FC = () => {
    // ✅ Получаем версию плана из контекста
    const { currentVersionId, currentPlanName } = usePlan();
    const isReadOnly = currentVersionId !== null;

    // --- Оборудование (верхний грид) ---
    const [equipment, setEquipment] = useState<Equipment[]>([]);
    const [loadingEq, setLoadingEq] = useState(true);
    const [eqError, setEqError] = useState<string | null>(null);
    const [dialogOpen, setDialogOpen] = useState(false);
    const [formData, setFormData] = useState<Partial<Equipment>>({
        name: "",
        type: "REACTOR",
        volume_kg: 0,
        speed_coeff: 1.0,
        mixer_type: "standard",
        is_active: true,
    });

    // --- Выбор оборудования ---
    const [selectedEquipmentId, setSelectedEquipmentId] = useState<string | null>(null);
    const selectedEquipment = equipment.find((e) => e.id === selectedEquipmentId) || null;

    // --- Ремонты (нижний Гант) ---
    const [repairs, setRepairs] = useState<CalendarEvent[]>([]);
    const [loadingRepairs, setLoadingRepairs] = useState(false);
    const [repairsError, setRepairsError] = useState<string | null>(null);

    // --- Диалог ремонта ---
    const [repairDialogOpen, setRepairDialogOpen] = useState(false);
    const [editingRepair, setEditingRepair] = useState<CalendarEvent | null>(null);
    const [repairForm, setRepairForm] = useState({
        event_type: "REPAIR",
        starts_at: "",
        ends_at: "",
        comment: "",
    });

    // --- vis-timeline ---
    const timelineContainerRef = useRef<HTMLDivElement>(null);
    const timelineRef = useRef<Timeline | null>(null);
    const clickTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    // ========== Загрузка оборудования ==========
    const loadEquipment = useCallback(async () => {
        setLoadingEq(true);
        setEqError(null);
        try {
            const data = await equipmentApi.getAll(currentVersionId || undefined);
            setEquipment(data);
        } catch (err: any) {
            setEqError(err.response?.data?.detail || "Ошибка загрузки оборудования");
        } finally {
            setLoadingEq(false);
        }
    }, [currentVersionId]);

    useEffect(() => {
        loadEquipment();
    }, [loadEquipment]);

    // ========== Загрузка ремонтов выбранного оборудования ==========
    const loadRepairs = useCallback(async (eqId: string) => {
        setLoadingRepairs(true);
        setRepairsError(null);
        try {
            const data = await calendarApi.getByEquipment(eqId, currentVersionId || undefined);
            setRepairs(data);
        } catch (err: any) {
            setRepairsError(err.response?.data?.detail || "Ошибка загрузки ремонтов");
            setRepairs([]);
        } finally {
            setLoadingRepairs(false);
        }
    }, [currentVersionId]);

    useEffect(() => {
        if (selectedEquipmentId) {
            loadRepairs(selectedEquipmentId);
        } else {
            setRepairs([]);
        }
    }, [selectedEquipmentId, loadRepairs]);

    // ========== Обработчик редактирования ремонта ==========
    const handleEditRepair = useCallback(
        (repairId: string) => {
            if (isReadOnly) return;
            const repair = repairs.find((r) => r.id === repairId);
            if (!repair) return;
            setEditingRepair(repair);
            setRepairForm({
                event_type: repair.event_type,
                starts_at: toLocalInputValue(new Date(repair.starts_at)),
                ends_at: toLocalInputValue(new Date(repair.ends_at)),
                comment: repair.comment || "",
            });
            setRepairDialogOpen(true);
        },
        [repairs, isReadOnly]
    );

    // ========== Рендер таймлайна ==========
    const renderTimeline = useCallback(() => {
        if (!timelineContainerRef.current) return;
        if (timelineRef.current) {
            timelineRef.current.destroy();
            timelineRef.current = null;
        }
        if (!selectedEquipmentId || repairs.length === 0) return;

        const groups = new DataSet([
            {
                id: selectedEquipmentId,
                content: `<b>${selectedEquipment?.name || "Оборудование"}</b>`,
            },
        ]);

        const items = new DataSet(
            repairs.map((r) => {
                const color = EVENT_TYPE_COLORS[r.event_type] || "#bdc3c7";
                const label = EVENT_TYPE_LABELS[r.event_type] || r.event_type;
                return {
                    id: r.id,
                    group: selectedEquipmentId,
                    content: `<b>${label}</b>${r.comment ? `<br><small>${r.comment}</small>` : ""}`,
                    start: new Date(r.starts_at).toISOString(),
                    end: new Date(r.ends_at).toISOString(),
                    style: `background-color: ${color}30; border-left: 4px solid ${color}; border-radius: 4px;`,
                    title: `<b>${label}</b><br>${r.comment || ""}<br>${new Date(r.starts_at).toLocaleString("ru-RU")} — ${new Date(r.ends_at).toLocaleString("ru-RU")}`,
                    type: "range",
                };
            })
        );

        const options = {
            groupOrder: "content" as const,
            editable: {
                add: false,
                updateTime: !isReadOnly,
                updateGroup: false,
                remove: false,
            },
            margin: { item: 10, axis: 5 },
            orientation: "top" as const,
            stack: false,
            showCurrentTime: true,
            zoomMin: 1000 * 60 * 60 * 2,
            zoomMax: 1000 * 60 * 60 * 24 * 60,
            format: {
                minorLabels: { hour: "HH:mm", weekday: "D MMM" },
                majorLabels: { day: "D MMMM YYYY" },
            },
            locale: "ru",
            tooltip: { followMouse: true, overflowMethod: "cap" as const },
            snap: (date: Date) => {
                const step = 15;
                const ms = 1000 * 60 * step;
                return new Date(Math.round(date.getTime() / ms) * ms);
            },
            onMove: async (item: any, callback: (item: any) => void) => {
                if (isReadOnly) {
                    const original = repairs.find((r) => r.id === item.id);
                    if (original) {
                        callback({ ...item, start: original.starts_at, end: original.ends_at });
                    }
                    return;
                }
                const repair = repairs.find((r) => r.id === item.id);
                if (!repair) {
                    callback(item);
                    return;
                }
                try {
                    await axios.put(`${API_BASE_URL}/api/v1/calendar/${repair.id}`, {
                        starts_at: new Date(item.start).toISOString(),
                        ends_at: new Date(item.end).toISOString(),
                    });
                    setRepairs((prev) =>
                        prev.map((r) =>
                            r.id === repair.id
                                ? {
                                    ...r,
                                    starts_at: new Date(item.start).toISOString(),
                                    ends_at: new Date(item.end).toISOString(),
                                }
                                : r
                        )
                    );
                    callback(item);
                } catch (err: any) {
                    setRepairsError(err.response?.data?.detail || "Ошибка сохранения перемещения");
                    callback({ ...item, start: repair.starts_at, end: repair.ends_at });
                }
            },
            onMoving: (item: any) => item,
        };

        timelineRef.current = new Timeline(timelineContainerRef.current, items, groups, options);

        timelineRef.current.on("click", (props: any) => {
            if (props.item) {
                if (clickTimeoutRef.current) {
                    clearTimeout(clickTimeoutRef.current);
                    clickTimeoutRef.current = null;
                    handleEditRepair(props.item.id);
                } else {
                    clickTimeoutRef.current = setTimeout(() => {
                        clickTimeoutRef.current = null;
                    }, 300);
                }
            }
        });

        timelineRef.current.on("doubleclick", (props: any) => {
            if (props.item) {
                handleEditRepair(props.item.id);
            }
        });

        timelineRef.current.fit();
    }, [repairs, selectedEquipmentId, selectedEquipment, handleEditRepair, isReadOnly]);

    useEffect(() => {
        renderTimeline();
        return () => {
            if (timelineRef.current) {
                timelineRef.current.destroy();
                timelineRef.current = null;
            }
            if (clickTimeoutRef.current) {
                clearTimeout(clickTimeoutRef.current);
            }
        };
    }, [renderTimeline]);

    // ========== Обработчики грида оборудования ==========
    const columnDefs: ColDef<Equipment>[] = [
        {
            headerName: "ID",
            field: "id",
            width: 120,
            editable: false,
            valueFormatter: (params) => (params.value ? params.value.substring(0, 8) : ""),
            tooltipValueGetter: (params) => params.value || "",
            cellStyle: { fontFamily: "monospace", fontSize: "11px", color: "#7f8c8d" },
        },
        { headerName: "Наименование", field: "name", flex: 2, minWidth: 200, editable: !isReadOnly },
        {
            headerName: "Тип",
            field: "type",
            width: 150,
            editable: !isReadOnly,
            cellEditor: "agSelectCellEditor",
            cellEditorParams: { values: ["REACTOR", "BOILER", "TANK", "FILLING_LINE", "MANUAL_STATION"] },
            valueFormatter: (params) => EQUIPMENT_TYPE_TRANSLATIONS[params.value] || params.value,
            valueParser: (params) => EQUIPMENT_TYPE_REVERSE[params.newValue] || params.newValue,
        },
        { headerName: "Объем (кг)", field: "volume_kg", width: 120, editable: !isReadOnly, type: "numericColumn" },
        { headerName: "Коэф. скорости", field: "speed_coeff", width: 130, editable: !isReadOnly, type: "numericColumn" },
        {
            headerName: "Тип мешалки",
            field: "mixer_type",
            width: 180,
            editable: !isReadOnly,
            cellEditor: "agSelectCellEditor",
            cellEditorParams: { values: ["standard", "high_speed", "low_speed"] },
            valueFormatter: (params) => MIXER_TYPE_TRANSLATIONS[params.value] || params.value,
            valueParser: (params) => MIXER_TYPE_REVERSE[params.newValue] || params.newValue,
        },
        { headerName: "Активно", field: "is_active", width: 100, editable: !isReadOnly, cellEditor: "agCheckboxCellEditor" },
        {
            headerName: "Действия",
            width: 100,
            editable: false,
            cellRenderer: (params: any) =>
                isReadOnly ? null : (
                    <IconButton color="error" size="small" onClick={() => handleDeleteEquipment(params.data.id)}>
                        <DeleteIcon fontSize="small" />
                    </IconButton>
                ),
        },
    ];

    const defaultColDef: ColDef = {
        sortable: true,
        filter: true,
        resizable: true,
        editable: !isReadOnly,
        singleClickEdit: true,
    };

    const getRowId = (params: any) => params.data.id;

    const handleCellValueChanged = async (params: any) => {
        if (isReadOnly) return;
        const { data, colDef, newValue } = params;
        const field = colDef.field;
        if (!field || field === "id") return;
        const oldValue = data[field];
        try {
            await axios.put(`${API_BASE_URL}/api/v1/equipment/${data.id}`, { [field]: newValue });
            setEquipment((prev) => prev.map((eq) => (eq.id === data.id ? { ...eq, [field]: newValue } : eq)));
        } catch (err: any) {
            setEqError(err.response?.data?.detail || "Ошибка сохранения");
            setEquipment((prev) => prev.map((eq) => (eq.id === data.id ? { ...eq, [field]: oldValue } : eq)));
        }
    };

    const handleRowClicked = (event: RowClickedEvent<Equipment>) => {
        if (event.data) {
            setSelectedEquipmentId(event.data.id);
        }
    };

    const handleDeleteEquipment = async (id: string) => {
        if (isReadOnly) return;
        if (!window.confirm("Удалить оборудование?")) return;
        try {
            await axios.delete(`${API_BASE_URL}/api/v1/equipment/${id}`);
            setEquipment((prev) => prev.filter((eq) => eq.id !== id));
            if (selectedEquipmentId === id) setSelectedEquipmentId(null);
        } catch (err: any) {
            setEqError(err.response?.data?.detail || "Ошибка удаления");
        }
    };

    const handleAddEquipment = () => {
        if (isReadOnly) return;
        setFormData({
            name: "",
            type: "REACTOR",
            volume_kg: 0,
            speed_coeff: 1.0,
            mixer_type: "standard",
            is_active: true,
        });
        setDialogOpen(true);
    };

    const handleSaveEquipment = async () => {
        if (isReadOnly) return;
        try {
            const response = await axios.post(`${API_BASE_URL}/api/v1/equipment/`, {
                ...formData,
                organization_id: "00000000-0000-0000-0000-000000000001",
            });
            setEquipment((prev) => [...prev, response.data]);
            setDialogOpen(false);
        } catch (err: any) {
            setEqError(err.response?.data?.detail || "Ошибка создания");
        }
    };

    // ========== Обработчики ремонтов ==========
    const openAddRepairDialog = () => {
        if (isReadOnly) return;
        if (!selectedEquipmentId) {
            setRepairsError("Сначала выберите оборудование в верхнем списке");
            return;
        }
        setEditingRepair(null);
        const now = new Date();
        const start = new Date(now);
        start.setHours(9, 0, 0, 0);
        const end = new Date(now);
        end.setHours(18, 0, 0, 0);
        setRepairForm({
            event_type: "REPAIR",
            starts_at: toLocalInputValue(start),
            ends_at: toLocalInputValue(end),
            comment: "",
        });
        setRepairDialogOpen(true);
    };

    const handleSaveRepair = async () => {
        if (isReadOnly) return;
        if (!selectedEquipmentId) return;
        const starts_at = new Date(repairForm.starts_at).toISOString();
        const ends_at = new Date(repairForm.ends_at).toISOString();
        if (new Date(ends_at) <= new Date(starts_at)) {
            setRepairsError("Время окончания должно быть позже времени начала");
            return;
        }
        try {
            if (editingRepair) {
                const updated = await axios.put(`${API_BASE_URL}/api/v1/calendar/${editingRepair.id}`, {
                    event_type: repairForm.event_type,
                    starts_at,
                    ends_at,
                    comment: repairForm.comment,
                });
                setRepairs((prev) => prev.map((r) => (r.id === editingRepair.id ? updated.data : r)));
            } else {
                const created = await axios.post(`${API_BASE_URL}/api/v1/calendar/`, {
                    equipment_id: selectedEquipmentId,
                    event_type: repairForm.event_type,
                    starts_at,
                    ends_at,
                    comment: repairForm.comment,
                });
                setRepairs((prev) => [...prev, created.data]);
            }
            setRepairDialogOpen(false);
        } catch (err: any) {
            setRepairsError(err.response?.data?.detail || "Ошибка сохранения ремонта");
        }
    };

    const handleDeleteRepair = async () => {
        if (isReadOnly) return;
        if (!editingRepair) return;
        if (!window.confirm("Удалить этот ремонт/простой?")) return;
        try {
            await axios.delete(`${API_BASE_URL}/api/v1/calendar/${editingRepair.id}`);
            setRepairs((prev) => prev.filter((r) => r.id !== editingRepair.id));
            setRepairDialogOpen(false);
        } catch (err: any) {
            setRepairsError(err.response?.data?.detail || "Ошибка удаления");
        }
    };

    const toLocalInputValue = (d: Date) => {
        const pad = (n: number) => n.toString().padStart(2, "0");
        return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
    };

    // ========== Рендер ==========
    if (loadingEq) {
        return (
            <Box sx={{ display: "flex", justifyContent: "center", mt: 4 }}>
                <CircularProgress />
            </Box>
        );
    }

    return (
        <Box sx={{ height: "100%", display: "flex", flexDirection: "column", minHeight: 0 }}>
            {/* ========== ЗАГОЛОВОК СТРАНИЦЫ ========== */}
            <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2, flexShrink: 0 }}>
                <Typography variant="h4" component="h1" sx={{ fontWeight: 600, color: "#2c3e50" }}>
                    Справочник оборудования
                </Typography>
                {!isReadOnly && (
                    <Button variant="contained" startIcon={<AddIcon />} onClick={handleAddEquipment} sx={{ textTransform: "none", fontWeight: 600 }}>
                        Добавить оборудование
                    </Button>
                )}
            </Box>

            {eqError && (
                <Alert severity="error" sx={{ mb: 2, flexShrink: 0 }} onClose={() => setEqError(null)}>
                    {eqError}
                </Alert>
            )}

            {/* ✅ Индикатор режима просмотра */}
            {isReadOnly && (
                <Alert severity="info" sx={{ mb: 2, flexShrink: 0 }} icon={<LockIcon fontSize="inherit" />}>
                    Режим просмотра: <b>{currentPlanName}</b>. Редактирование недоступно.
                </Alert>
            )}

            {/* ========== СПЛИТТЕР ========== */}
            <Allotment vertical defaultSizes={[40, 60]} minSize={100}>
                {/* ========== ВЕРХНЯЯ ПАНЕЛЬ: ТАБЛИЦА ОБОРУДОВАНИЯ ========== */}
                <Allotment.Pane minSize={150}>
                    <Card sx={{ boxShadow: "0 2px 8px rgba(0,0,0,0.1)", display: "flex", flexDirection: "column", minHeight: 0, margin: 1, height: "96%" }}>
                        <CardContent sx={{ p: 2, flexGrow: 1, display: "flex", flexDirection: "column", minHeight: 0 }}>
                            <Box className="ag-theme-alpine" sx={{ flexGrow: 1, width: "100%", minHeight: 0 }}>
                                <AgGridReact
                                    rowData={equipment}
                                    columnDefs={columnDefs}
                                    defaultColDef={defaultColDef}
                                    getRowId={getRowId}
                                    pagination
                                    paginationPageSize={10}
                                    paginationPageSizeSelector={[10, 20, 50, 100]}
                                    onCellValueChanged={handleCellValueChanged}
                                    onRowClicked={handleRowClicked}
                                    suppressPropertyNamesCheck={true}
                                    rowSelection="single"
                                    onGridReady={(params: GridReadyEvent) => params.api.sizeColumnsToFit()}
                                    getRowStyle={(params) => {
                                        if (params.data.is_active) {
                                            return { backgroundColor: "#ffffff", cursor: "pointer" };
                                        } else {
                                            return { backgroundColor: "#f5f5f5", cursor: "pointer" };
                                        }
                                    }}
                                />
                            </Box>
                        </CardContent>
                    </Card>
                </Allotment.Pane>

                {/* ========== НИЖНЯЯ ПАНЕЛЬ: РЕМОНТЫ И ПРОСТОИ ========== */}
                <Allotment.Pane minSize={150}>
                    <Card sx={{ boxShadow: "0 2px 8px rgba(0,0,0,0.1)", display: "flex", flexDirection: "column", minHeight: 0, margin: 1, height: "98%" }}>
                        <CardContent sx={{ p: 2, flexGrow: 1, display: "flex", flexDirection: "column", minHeight: 0 }}>
                            <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2, flexWrap: "wrap", gap: 1, flexShrink: 0 }}>
                                <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
                                    <BuildIcon color="primary" />
                                    <Typography variant="h5" sx={{ fontWeight: 600, color: "#2c3e50" }}>
                                        Ремонты и простои
                                    </Typography>
                                    {selectedEquipment ? (
                                        <Chip label={selectedEquipment.name} color="primary" variant="outlined" size="small" />
                                    ) : (
                                        <Chip label="Выберите оборудование в таблице выше" variant="outlined" color="default" size="small" />
                                    )}
                                </Box>
                                <Box sx={{ display: "flex", gap: 1 }}>
                                    <Button variant="outlined" size="small" startIcon={<RefreshIcon />} onClick={() => selectedEquipmentId && loadRepairs(selectedEquipmentId)} disabled={!selectedEquipmentId}>
                                        Обновить
                                    </Button>
                                    {!isReadOnly && (
                                        <Button variant="contained" size="small" startIcon={<AddIcon />} onClick={openAddRepairDialog} disabled={!selectedEquipmentId} sx={{ textTransform: "none" }}>
                                            Добавить ремонт
                                        </Button>
                                    )}
                                </Box>
                            </Box>

                            {repairsError && (
                                <Alert severity="error" sx={{ mb: 2, flexShrink: 0 }} onClose={() => setRepairsError(null)}>
                                    {repairsError}
                                </Alert>
                            )}

                            {!selectedEquipmentId ? (
                                <Box sx={{ display: "flex", alignItems: "center", justifyContent: "center", flexGrow: 1, color: "#7f8c8d", flexDirection: "column", gap: 1 }}>
                                    <Typography variant="h6"></Typography>
                                    <Typography variant="body1">Выберите строку в таблице оборудования, чтобы увидеть его ремонты</Typography>
                                </Box>
                            ) : loadingRepairs ? (
                                <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", flexGrow: 1 }}>
                                    <CircularProgress />
                                </Box>
                            ) : repairs.length === 0 ? (
                                <Box sx={{ display: "flex", alignItems: "center", justifyContent: "center", flexGrow: 1, color: "#7f8c8d", flexDirection: "column", gap: 1 }}>
                                    <Typography variant="body1">У этого оборудования пока нет запланированных ремонтов</Typography>
                                    {!isReadOnly && (
                                        <Button variant="outlined" size="small" startIcon={<AddIcon />} onClick={openAddRepairDialog}>
                                            Добавить ремонт
                                        </Button>
                                    )}
                                </Box>
                            ) : (
                                <Box
                                    ref={timelineContainerRef}
                                    sx={{
                                        flexGrow: 1,
                                        width: "100%",
                                        minHeight: 0,
                                        "& .vis-item": { borderColor: "transparent", cursor: isReadOnly ? "default" : "move" },
                                        "& .vis-label": { fontWeight: 600, color: "#2c3e50" },
                                    }}
                                />
                            )}
                        </CardContent>
                    </Card>
                </Allotment.Pane>
            </Allotment>

            {!isReadOnly && (
                <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: "block", textAlign: "center", flexShrink: 0 }}>
                    💡 Перетаскивайте границы ремонта мышкой для изменения времени • Двойной клик — редактирование
                </Typography>
            )}

            {/* ========== ДИАЛОГ ДОБАВЛЕНИЯ ОБОРУДОВАНИЯ (DraggableDialog) ========== */}
            {!isReadOnly && (
                <DraggableDialog
                    open={dialogOpen}
                    onClose={() => setDialogOpen(false)}
                    title="Добавить оборудование"
                    initialWidth={600}
                    initialHeight="auto"
                    minWidth={480}
                    minHeight={300}
                    actions={
                        <>
                            <Button onClick={() => setDialogOpen(false)}>Отмена</Button>
                            <Button onClick={handleSaveEquipment} variant="contained">
                                Сохранить
                            </Button>
                        </>
                    }
                >
                    <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
                        <TextField
                            autoFocus
                            margin="dense"
                            label="Наименование"
                            fullWidth
                            value={formData.name}
                            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                        />
                        <FormControl fullWidth margin="dense">
                            <InputLabel>Тип</InputLabel>
                            <Select value={formData.type} label="Тип" onChange={(e) => setFormData({ ...formData, type: e.target.value })}>
                                <MenuItem value="REACTOR">Реактор</MenuItem>
                                <MenuItem value="BOILER">Бойлер</MenuItem>
                                <MenuItem value="TANK">Емкость</MenuItem>
                                <MenuItem value="FILLING_LINE">Линия розлива</MenuItem>
                                <MenuItem value="MANUAL_STATION">Ручная станция</MenuItem>
                            </Select>
                        </FormControl>
                        <TextField
                            margin="dense"
                            label="Объем (кг)"
                            type="number"
                            fullWidth
                            value={formData.volume_kg}
                            onChange={(e) => setFormData({ ...formData, volume_kg: Number(e.target.value) })}
                        />
                        <TextField
                            margin="dense"
                            label="Коэффициент скорости"
                            type="number"
                            fullWidth
                            value={formData.speed_coeff}
                            onChange={(e) => setFormData({ ...formData, speed_coeff: Number(e.target.value) })}
                        />
                        <FormControl fullWidth margin="dense">
                            <InputLabel>Тип мешалки</InputLabel>
                            <Select value={formData.mixer_type} label="Тип мешалки" onChange={(e) => setFormData({ ...formData, mixer_type: e.target.value })}>
                                <MenuItem value="standard">Стандартная</MenuItem>
                                <MenuItem value="high_speed">Высокоскоростная</MenuItem>
                                <MenuItem value="low_speed">Низкоскоростная</MenuItem>
                            </Select>
                        </FormControl>
                    </Box>
                </DraggableDialog>
            )}

            {/* ========== ДИАЛОГ РЕМОНТА (DraggableDialog) ========== */}
            {!isReadOnly && (
                <DraggableDialog
                    open={repairDialogOpen}
                    onClose={() => setRepairDialogOpen(false)}
                    title={editingRepair ? "Редактировать ремонт / простой" : "Добавить ремонт / простой"}
                    initialWidth={600}
                    initialHeight="auto"
                    minWidth={480}
                    minHeight={300}
                    actions={
                        <>
                            {editingRepair && (
                                <Button
                                    onClick={handleDeleteRepair}
                                    color="error"
                                    startIcon={<DeleteIcon />}
                                    sx={{ mr: "auto" }}
                                >
                                    Удалить
                                </Button>
                            )}
                            <Button onClick={() => setRepairDialogOpen(false)}>Отмена</Button>
                            <Button onClick={handleSaveRepair} variant="contained" sx={{ ml: 1 }}>
                                Сохранить
                            </Button>
                        </>
                    }
                >
                    <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
                        <FormControl fullWidth margin="dense">
                            <InputLabel>Тип события</InputLabel>
                            <Select
                                value={repairForm.event_type}
                                label="Тип события"
                                onChange={(e) => setRepairForm({ ...repairForm, event_type: e.target.value })}
                            >
                                <MenuItem value="REPAIR">Плановый ремонт</MenuItem>
                                <MenuItem value="BREAKDOWN">Аварийная остановка</MenuItem>
                                <MenuItem value="WEEKEND">Выходные</MenuItem>
                                <MenuItem value="SHIFT_END">Конец смены</MenuItem>
                                <MenuItem value="LUNCH">Обед</MenuItem>
                            </Select>
                        </FormControl>
                        <TextField
                            margin="dense"
                            label="Начало"
                            type="datetime-local"
                            fullWidth
                            value={repairForm.starts_at}
                            onChange={(e) => setRepairForm({ ...repairForm, starts_at: e.target.value })}
                            slotProps={{ inputLabel: { shrink: true } }}
                        />
                        <TextField
                            margin="dense"
                            label="Окончание"
                            type="datetime-local"
                            fullWidth
                            value={repairForm.ends_at}
                            onChange={(e) => setRepairForm({ ...repairForm, ends_at: e.target.value })}
                            slotProps={{ inputLabel: { shrink: true } }}
                        />
                        <TextField
                            margin="dense"
                            label="Комментарий"
                            fullWidth
                            multiline
                            rows={2}
                            value={repairForm.comment}
                            onChange={(e) => setRepairForm({ ...repairForm, comment: e.target.value })}
                        />
                    </Box>
                </DraggableDialog>
            )}
        </Box>
    );
};

export default EquipmentPage;