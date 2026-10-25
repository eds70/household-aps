// frontend/src/pages/EquipmentPage.tsx
import React, {useCallback, useEffect, useMemo, useRef, useState} from "react";
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
    Event as EventIcon,
    InfoOutlined as InfoIcon,
    Refresh as RefreshIcon,
    WarningAmber as WarningIcon,
} from "@mui/icons-material";
import type {ColDef, GridReadyEvent, RowClickedEvent} from "ag-grid-community";
import {AllCommunityModule, ModuleRegistry} from "ag-grid-community";
import {Timeline} from "vis-timeline/standalone";
import {DataSet} from "vis-data";
import "vis-timeline/styles/vis-timeline-graph2d.min.css";
import {Allotment} from "allotment";
import "allotment/dist/style.css";
import type {CalendarEvent, Equipment} from "../types";
import {usePlan} from "../context/PlainContext";
import api, {calendarApi, equipmentApi} from "../services/api";
import DraggableDialog from "../components/common/DraggableDialog";
import AppAgGrid from '../components/common/AppAgGrid';

ModuleRegistry.registerModules([AllCommunityModule]);

const EQUIPMENT_TYPE_TRANSLATIONS: Record<string, string> = {
    REACTOR: "Реактор", BOILER: "Бойлер", TANK: "Емкость",
    FILLING_LINE: "Линия розлива", MANUAL_STATION: "Ручная станция",
};
const EQUIPMENT_TYPE_REVERSE: Record<string, string> = {
    Реактор: "REACTOR", Бойлер: "BOILER", Емкость: "TANK",
    "Линия розлива": "FILLING_LINE", "Ручная станция": "MANUAL_STATION",
};
const MIXER_TYPE_TRANSLATIONS: Record<string, string> = {
    standard: "Стандартная", high_speed: "Высокоскоростная", low_speed: "Низкоскоростная",
};
const MIXER_TYPE_REVERSE: Record<string, string> = {
    Стандартная: "standard", Высокоскоростная: "high_speed", Низкоскоростная: "low_speed",
};
const EVENT_TYPE_LABELS: Record<string, string> = {
    REPAIR: "Плановый ремонт", BREAKDOWN: "Аварийная остановка",
    WEEKEND: "Выходные", SHIFT_END: "Конец смены", LUNCH: "Обед",
};
const EVENT_TYPE_COLORS: Record<string, string> = {
    REPAIR: "#e67e22", BREAKDOWN: "#e74c3c", WEEKEND: "#95a5a6",
    SHIFT_END: "#3498db", LUNCH: "#9b59b6",
};

const MIN_REPAIR_DURATION_MS = 15 * 60 * 1000; // минимум 15 минут при ресайзе

const EquipmentPage: React.FC = () => {
    const { currentVersionId, currentPlanName, isCurrentPlanDraft, markPlanDirty } = usePlan();

    const [equipment, setEquipment] = useState<Equipment[]>([]);
    const [loadingEq, setLoadingEq] = useState(true);
    const [eqError, setEqError] = useState<string | null>(null);
    const [dialogOpen, setDialogOpen] = useState(false);
    const [formData, setFormData] = useState<Partial<Equipment>>({
        name: "", type: "REACTOR", volume_kg: 0, speed_coeff: 1.0,
        mixer_type: "standard", is_active: true,
    });

    const [selectedEquipmentId, setSelectedEquipmentId] = useState<string | null>(null);
    const selectedEquipment = equipment.find((e) => e.id === selectedEquipmentId) || null;

    const [repairs, setRepairs] = useState<CalendarEvent[]>([]);
    const [loadingRepairs, setLoadingRepairs] = useState(false);
    const [repairsError, setRepairsError] = useState<string | null>(null);

    const [repairDialogOpen, setRepairDialogOpen] = useState(false);
    const [editingRepair, setEditingRepair] = useState<CalendarEvent | null>(null);
    const [repairForm, setRepairForm] = useState({
        event_type: "REPAIR", starts_at: "", ends_at: "", comment: "",
    });

    const timelineContainerRef = useRef<HTMLDivElement>(null);
    const timelineRef = useRef<Timeline | null>(null);
    const itemsRef = useRef<DataSet<any> | null>(null);

    const [isTimelineReady, setIsTimelineReady] = useState(false);

    // Стейт для самописного Drag & Drop (как в GanttPage)
    const dragStateRef = useRef<{
        itemId: string; operationType: 'move' | 'resize';
        startX: number; originalStartMs: number; originalEndMs: number;
        originalDurationMs: number; msPerPx: number;
        fixedEndMs: number; fixedStartMs: number;
        hasMoved: boolean;
    } | null>(null);

    const rafIdRef = useRef<number | null>(null);
    const pendingEventRef = useRef<PointerEvent | null>(null);

    const repairsRef = useRef<CalendarEvent[]>([]);
    useEffect(() => { repairsRef.current = repairs; }, [repairs]);

    // ========== Загрузка ==========
    const loadEquipment = useCallback(async () => {
        setLoadingEq(true);
        setEqError(null);
        try {
            const data = await equipmentApi.getAll();
            setEquipment(data);
        } catch (err: any) {
            setEqError(err.response?.data?.detail || "Ошибка загрузки оборудования");
        } finally {
            setLoadingEq(false);
        }
    }, []);

    useEffect(() => { loadEquipment(); }, [loadEquipment]);

    const loadRepairs = useCallback(async (eqId: string) => {
        setLoadingRepairs(true);
        setRepairsError(null);
        try {
            const data = await calendarApi.getByEquipment(eqId);
            setRepairs(data);
        } catch (err: any) {
            setRepairsError(err.response?.data?.detail || "Ошибка загрузки ремонтов");
            setRepairs([]);
        } finally {
            setLoadingRepairs(false);
        }
    }, []);

    useEffect(() => {
        if (selectedEquipmentId) loadRepairs(selectedEquipmentId);
        else setRepairs([]);
    }, [selectedEquipmentId, loadRepairs]);

    const upcomingEvents = useMemo(() => {
        if (!repairs.length) return [];
        const now = new Date();
        return repairs
            .filter(r => {
                const start = new Date(r.starts_at);
                const end = new Date(r.ends_at);
                return end >= now || (start > now && start.getTime() - now.getTime() <= 7 * 24 * 3600 * 1000);
            })
            .sort((a, b) => new Date(a.starts_at).getTime() - new Date(b.starts_at).getTime())
            .slice(0, 3);
    }, [repairs]);

    const handleEditRepair = useCallback((repairId: string) => {
        const repair = repairsRef.current.find((r) => r.id === repairId);
        if (!repair) return;
        setEditingRepair(repair);
        setRepairForm({
            event_type: repair.event_type,
            starts_at: toLocalInputValue(new Date(repair.starts_at)),
            ends_at: toLocalInputValue(new Date(repair.ends_at)),
            comment: repair.comment || "",
        });
        setRepairDialogOpen(true);
    }, []);

    // ========== Самописный Drag (как в Ганте) ==========
    const attachNativeDragListeners = useCallback(() => {
        const container = timelineContainerRef.current;
        if (!container) return () => {};

        const getTaskIdFromElement = (el: HTMLElement | null): string | null => {
            if (!el) return null;
            const itemEl = el.closest('.vis-item.vis-range') as HTMLElement | null;
            if (!itemEl) return null;
            const visItem = (itemEl as any)['vis-item'];
            return visItem && visItem.id ? String(visItem.id) : null;
        };

        const onPointerDown = (e: PointerEvent) => {
            const target = e.target as HTMLElement;
            // Если кликнули не по задаче, позволяем vis-timeline обработать это (скролл)
            if (!target?.closest('.vis-item.vis-range')) return;

            const itemId = getTaskIdFromElement(target);
            if (!itemId) return;

            const repair = repairsRef.current.find(r => r.id === itemId);
            if (!repair) return;

            const timeline = timelineRef.current;
            if (!timeline) return;

            // Блокируем стандартное поведение vis-timeline ТОЛЬКО для задач
            e.stopPropagation();
            e.preventDefault();

            const isResize = !!target.closest('.vis-drag-left') || !!target.closest('.vis-drag-right');

            let msPerPx = 1;
            try {
                const range = timeline.getWindow();
                const totalMs = range.end.getTime() - range.start.getTime();
                const centerPanel = container.querySelector('.vis-panel.vis-center') as HTMLElement | null;
                const panelWidth = centerPanel?.clientWidth || container.clientWidth || 1;
                msPerPx = totalMs / panelWidth;
            } catch {}

            const startMs = new Date(repair.starts_at).getTime();
            const endMs = new Date(repair.ends_at).getTime();

            dragStateRef.current = {
                itemId, operationType: isResize ? 'resize' : 'move',
                startX: e.clientX, originalStartMs: startMs, originalEndMs: endMs,
                originalDurationMs: endMs - startMs, msPerPx,
                fixedEndMs: endMs, fixedStartMs: startMs, hasMoved: false
            };

            document.body.style.cursor = isResize ? 'ew-resize' : 'grabbing';
        };

        const onPointerMove = (e: PointerEvent) => {
            const st = dragStateRef.current;
            if (!st) return;

            e.preventDefault();

            pendingEventRef.current = e;
            if (rafIdRef.current !== null) return;

            rafIdRef.current = requestAnimationFrame(() => {
                rafIdRef.current = null;
                const ev = pendingEventRef.current;
                pendingEventRef.current = null;
                if (!ev || !dragStateRef.current) return;

                const state = dragStateRef.current;
                const deltaPx = ev.clientX - state.startX;
                const deltaMs = deltaPx * state.msPerPx;

                if (Math.abs(deltaPx) > 3) {
                    state.hasMoved = true;
                }

                let newStartMs = state.originalStartMs;
                let newEndMs = state.originalEndMs;

                if (state.operationType === 'move') {
                    newStartMs += deltaMs;
                    newEndMs += deltaMs;
                } else {
                    const originalWidthPx = state.originalDurationMs / state.msPerPx;
                    const midX = state.startX + originalWidthPx / 2;
                    if (ev.clientX < midX) {
                        newStartMs += deltaMs;
                        newEndMs = state.fixedEndMs;
                        if (newStartMs >= newEndMs - MIN_REPAIR_DURATION_MS) newStartMs = newEndMs - MIN_REPAIR_DURATION_MS;
                    } else {
                        newStartMs = state.fixedStartMs;
                        newEndMs += deltaMs;
                        if (newEndMs <= newStartMs + MIN_REPAIR_DURATION_MS) newEndMs = newStartMs + MIN_REPAIR_DURATION_MS;
                    }
                }

                if (itemsRef.current) {
                    itemsRef.current.update({
                        id: state.itemId,
                        start: new Date(newStartMs).toISOString(),
                        end: new Date(newEndMs).toISOString(),
                    });
                }
            });
        };

        const onPointerUp = async () => {
            const st = dragStateRef.current;
            dragStateRef.current = null;
            document.body.style.cursor = '';

            if (rafIdRef.current !== null) {
                cancelAnimationFrame(rafIdRef.current);
                rafIdRef.current = null;
            }
            pendingEventRef.current = null;

            if (!st) return;

            if (!st.hasMoved) {
                handleEditRepair(st.itemId);
                return;
            }

            const item = itemsRef.current?.get(st.itemId) as any;
            if (!item || !item.start || !item.end) return;

            const newStart = new Date(item.start).toISOString();
            const newEnd = new Date(item.end).toISOString();
            const originalRepair = repairsRef.current.find(r => r.id === st.itemId);
            if (!originalRepair) return;

            if (newStart === originalRepair.starts_at && newEnd === originalRepair.ends_at) return;

            setRepairs(prev => prev.map(r => r.id === st.itemId ? { ...r, starts_at: newStart, ends_at: newEnd } : r));

            try {
                await api.put(`/api/v1/calendar/${st.itemId}`, {
                    starts_at: newStart,
                    ends_at: newEnd,
                });
                markPlanDirty();
            } catch (err: any) {
                setRepairsError(err.response?.data?.detail || "Ошибка сохранения перемещения");
                setRepairs(prev => prev.map(r => r.id === st.itemId ? originalRepair : r));
                if (itemsRef.current) {
                    itemsRef.current.update({
                        id: st.itemId,
                        start: originalRepair.starts_at,
                        end: originalRepair.ends_at,
                    });
                }
            }
        };

        container.addEventListener('pointerdown', onPointerDown, true);
        window.addEventListener('pointermove', onPointerMove, true);
        window.addEventListener('pointerup', onPointerUp, true);

        return () => {
            container.removeEventListener('pointerdown', onPointerDown, true);
            window.removeEventListener('pointermove', onPointerMove, true);
            window.removeEventListener('pointerup', onPointerUp, true);
        };
    }, [markPlanDirty, handleEditRepair]);

    // ========== Инициализация Таймлайна ==========
    useEffect(() => {
        if (!selectedEquipmentId || !timelineContainerRef.current) return;

        setIsTimelineReady(false);

        if (timelineRef.current) {
            timelineRef.current.destroy();
            timelineRef.current = null;
        }

        const items = new DataSet<any>([]);
        itemsRef.current = items;
        const groups = new DataSet([{ id: selectedEquipmentId, content: "" }]);

        const options = {
            groupOrder: "content" as const,
            editable: false,
            moveable: true, // ВКЛЮЧАЕМ скролл таймлайна (мы блокируем его только при клике на задачу)
            zoomable: true, // ВКЛЮЧАЕМ зум
            margin: { item: 10, axis: 5 },
            orientation: "top" as const,
            stack: false, showCurrentTime: true,
            zoomMin: 1000 * 60 * 60 * 2, zoomMax: 1000 * 60 * 60 * 24 * 60,
            format: { minorLabels: { hour: "HH:mm", weekday: "D MMM" }, majorLabels: { day: "D MMMM YYYY" } },
            locale: "ru",
            tooltip: { followMouse: true, overflowMethod: "cap" as const },
        };

        const timer = setTimeout(() => {
            if (!timelineContainerRef.current) return;
            const timeline = new Timeline(timelineContainerRef.current, items, groups, options);
            timelineRef.current = timeline;

            const detachDrag = attachNativeDragListeners();
            (timeline as any).__detachDrag = detachDrag;

            updateTimelineItems(repairsRef.current, selectedEquipmentId);
            if (timelineRef.current) {
                const now = new Date();
                const start = new Date(now.getTime() - 2 * 24 * 60 * 60 * 1000);
                const end = new Date(now.getTime() + 5 * 24 * 60 * 60 * 1000);
                timelineRef.current.setWindow(start, end, { animation: false });
            }

            timeline.redraw();
            setIsTimelineReady(true);

        }, 150);

        return () => {
            clearTimeout(timer);
            if (timelineRef.current) {
                const tl = timelineRef.current as any;
                if (tl.__detachDrag) tl.__detachDrag();
                timelineRef.current.destroy();
                timelineRef.current = null;
                itemsRef.current = null;
            }
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [selectedEquipmentId, attachNativeDragListeners]);

    const updateTimelineItems = (currentRepairs: CalendarEvent[], eqId: string | null) => {
        if (!itemsRef.current || !eqId) return;

        const itemsData = currentRepairs.map((r) => {
            const color = EVENT_TYPE_COLORS[r.event_type] || "#bdc3c7";
            const label = EVENT_TYPE_LABELS[r.event_type] || r.event_type;
            return {
                id: r.id, group: eqId,
                content: `<b>${label}</b>${r.comment ? `<br><small>${r.comment}</small>` : ""}`,
                start: new Date(r.starts_at).toISOString(),
                end: new Date(r.ends_at).toISOString(),
                style: `background-color: ${color}30; border-left: 4px solid ${color}; border-radius: 4px; cursor: grab;`,
                title: `<b>${label}</b><br>${r.comment || ""}<br>${new Date(r.starts_at).toLocaleString("ru-RU")} — ${new Date(r.ends_at).toLocaleString("ru-RU")}`,
                type: "range",
            };
        });

        itemsRef.current.clear();
        itemsRef.current.add(itemsData);
    };

    useEffect(() => {
        updateTimelineItems(repairs, selectedEquipmentId);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [repairs]);

    useEffect(() => {
        if (!timelineContainerRef.current) return;
        const observer = new ResizeObserver(() => {
            if (timelineRef.current) timelineRef.current.redraw();
        });
        observer.observe(timelineContainerRef.current);
        return () => observer.disconnect();
    }, [selectedEquipmentId]);

    // ========== Грид ==========
    const columnDefs: ColDef<Equipment>[] = [
        {
            headerName: "ID", field: "id", width: 120, editable: false,
            valueFormatter: (params) => params.value ? params.value.substring(0, 8) : "",
            tooltip: (params) => params.value || "",
            cellStyle: { fontFamily: "monospace", fontSize: "11px", color: "#7f8c8d" },
        },
        { headerName: "Наименование", field: "name", flex: 2, minWidth: 200, editable: true },
        {
            headerName: "Тип", field: "type", width: 150, editable: true,
            cellEditor: "agSelectCellEditor",
            cellEditorParams: { values: ["REACTOR", "BOILER", "TANK", "FILLING_LINE", "MANUAL_STATION"] },
            valueFormatter: (params) => EQUIPMENT_TYPE_TRANSLATIONS[params.value] || params.value,
            valueParser: (params) => EQUIPMENT_TYPE_REVERSE[params.newValue] || params.newValue,
        },
        { headerName: "Объем (кг)", field: "volume_kg", width: 120, editable: true, type: "numericColumn" },
        { headerName: "Коэф. скорости", field: "speed_coeff", width: 130, editable: true, type: "numericColumn" },
        {
            headerName: "Тип мешалки", field: "mixer_type", width: 180, editable: true,
            cellEditor: "agSelectCellEditor",
            cellEditorParams: { values: ["standard", "high_speed", "low_speed"] },
            valueFormatter: (params) => MIXER_TYPE_TRANSLATIONS[params.value] || params.value,
            valueParser: (params) => MIXER_TYPE_REVERSE[params.newValue] || params.newValue,
        },
        { headerName: "Активно", field: "is_active", width: 100, editable: true, cellEditor: "agCheckboxCellEditor" },
        {
            headerName: "Действия", width: 100, editable: false,
            cellRenderer: (params: any) => (
                <IconButton color="error" size="small" onClick={() => handleDeleteEquipment(params.data.id)}>
                    <DeleteIcon fontSize="small" />
                </IconButton>
            ),
        },
    ];

    const defaultColDef: ColDef = {
        sortable: true, filter: true, resizable: true,
        editable: true, singleClickEdit: true,
    };

    const getRowId = (params: any) => params.data.id;

    const handleCellValueChanged = async (params: any) => {
        const { data, colDef, newValue } = params;
        const field = colDef.field;
        if (!field || field === "id") return;
        const oldValue = data[field];
        try {
            await api.put(`/api/v1/equipment/${data.id}`, { [field]: newValue });
            setEquipment((prev) => prev.map((eq) => (eq.id === data.id ? { ...eq, [field]: newValue } : eq)));
            markPlanDirty();
        } catch (err: any) {
            setEqError(err.response?.data?.detail || "Ошибка сохранения");
            setEquipment((prev) => prev.map((eq) => (eq.id === data.id ? { ...eq, [field]: oldValue } : eq)));
        }
    };

    const handleRowClicked = (event: RowClickedEvent<Equipment>) => {
        if (event.data) setSelectedEquipmentId(event.data.id);
    };

    const handleDeleteEquipment = async (id: string) => {
        if (!window.confirm("Удалить оборудование?")) return;
        try {
            await api.delete(`/api/v1/equipment/${id}`);
            setEquipment((prev) => prev.filter((eq) => eq.id !== id));
            if (selectedEquipmentId === id) setSelectedEquipmentId(null);
            markPlanDirty();
        } catch (err: any) {
            setEqError(err.response?.data?.detail || "Ошибка удаления");
        }
    };

    const handleAddEquipment = () => {
        setFormData({
            name: "", type: "REACTOR", volume_kg: 0, speed_coeff: 1.0,
            mixer_type: "standard", is_active: true,
        });
        setDialogOpen(true);
    };

    const handleSaveEquipment = async () => {
        try {
            const response = await api.post(`/api/v1/equipment/`, {
                ...formData, organization_id: "00000000-0000-0000-0000-000000000001",
            });
            setEquipment((prev) => [...prev, response.data]);
            setDialogOpen(false);
            markPlanDirty();
        } catch (err: any) {
            setEqError(err.response?.data?.detail || "Ошибка создания");
        }
    };

    const openAddRepairDialog = () => {
        if (!selectedEquipmentId) {
            setRepairsError("Сначала выберите оборудование в верхнем списке");
            return;
        }
        setEditingRepair(null);
        const now = new Date();
        const start = new Date(now); start.setHours(9, 0, 0, 0);
        const end = new Date(now); end.setHours(18, 0, 0, 0);
        setRepairForm({
            event_type: "REPAIR",
            starts_at: toLocalInputValue(start),
            ends_at: toLocalInputValue(end),
            comment: "",
        });
        setRepairDialogOpen(true);
    };

    const handleSaveRepair = async () => {
        if (!selectedEquipmentId) return;
        const starts_at = new Date(repairForm.starts_at).toISOString();
        const ends_at = new Date(repairForm.ends_at).toISOString();
        if (new Date(ends_at) <= new Date(starts_at)) {
            setRepairsError("Время окончания должно быть позже времени начала");
            return;
        }
        try {
            if (editingRepair) {
                const updated = await api.put(`/api/v1/calendar/${editingRepair.id}`, {
                    event_type: repairForm.event_type,
                    starts_at, ends_at, comment: repairForm.comment,
                });
                setRepairs((prev) => prev.map((r) => (r.id === editingRepair.id ? updated.data : r)));
            } else {
                const created = await api.post(`/api/v1/calendar/`, {
                    equipment_id: selectedEquipmentId,
                    event_type: repairForm.event_type,
                    starts_at, ends_at, comment: repairForm.comment,
                });
                setRepairs((prev) => [...prev, created.data]);
            }
            setRepairDialogOpen(false);
            markPlanDirty();
        } catch (err: any) {
            setRepairsError(err.response?.data?.detail || "Ошибка сохранения ремонта");
        }
    };

    const handleDeleteRepair = async () => {
        if (!editingRepair) return;
        if (!window.confirm("Удалить этот ремонт/простой?")) return;
        try {
            await api.delete(`/api/v1/calendar/${editingRepair.id}`);
            setRepairs((prev) => prev.filter((r) => r.id !== editingRepair.id));
            setRepairDialogOpen(false);
            markPlanDirty();
        } catch (err: any) {
            setRepairsError(err.response?.data?.detail || "Ошибка удаления");
        }
    };

    const toLocalInputValue = (d: Date) => {
        const pad = (n: number) => n.toString().padStart(2, "0");
        return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
    };

    if (loadingEq) {
        return <Box sx={{ display: "flex", justifyContent: "center", mt: 4 }}><CircularProgress /></Box>;
    }

    return (
        <Box sx={{ height: "100%", display: "flex", flexDirection: "column", minHeight: 0 }}>
            <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2, flexShrink: 0 }}>
                <Typography variant="h4" component="h1" sx={{ fontWeight: 600, color: "#2c3e50" }}>
                    Справочник оборудования
                </Typography>
                <Button variant="contained" startIcon={<AddIcon />} onClick={handleAddEquipment} sx={{ textTransform: "none", fontWeight: 600 }}>
                    Добавить оборудование
                </Button>
            </Box>

            {currentVersionId && (
                <Alert severity="info" sx={{ mb: 2, flexShrink: 0 }} icon={<InfoIcon />}>
                    Вы редактируете <b>глобальный справочник</b> «{currentPlanName}».
                    {isCurrentPlanDraft
                        ? ' Чтобы изменения попали в черновик, нажмите «Построить план» в шапке.'
                        : ' Изменения не попадут в активный план без пересчёта.'}
                </Alert>
            )}

            {eqError && (
                <Alert severity="error" sx={{ mb: 2, flexShrink: 0 }} onClose={() => setEqError(null)}>
                    {eqError}
                </Alert>
            )}

            <Allotment vertical defaultSizes={[40, 60]} minSize={100}>
                <Allotment.Pane minSize={150}>
                    <Card sx={{ boxShadow: "0 2px 8px rgba(0,0,0,0.1)", display: "flex", flexDirection: "column", minHeight: 0, margin: 1, height: "96%" }}>
                        <CardContent sx={{ p: 2, flexGrow: 1, display: "flex", flexDirection: "column", minHeight: 0 }}>
                            <Box sx={{ flexGrow: 1, width: "100%", minHeight: 0 }}>
                                <AppAgGrid
                                    rowData={equipment}
                                    columnDefs={columnDefs}
                                    defaultColDef={defaultColDef}
                                    getRowId={getRowId}
                                    pagination
                                    paginationPageSize={10}
                                    paginationPageSizeSelector={[10, 20, 50, 100]}
                                    onCellValueChanged={handleCellValueChanged}
                                    onRowClicked={handleRowClicked}
                                    rowSelection={{mode: 'singleRow'}}
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
                                    <Button variant="contained" size="small" startIcon={<AddIcon />} onClick={openAddRepairDialog} disabled={!selectedEquipmentId} sx={{ textTransform: "none" }}>
                                        Добавить ремонт
                                    </Button>
                                </Box>
                            </Box>

                            {upcomingEvents.length > 0 && (
                                <Box sx={{ display: "flex", gap: 1, mb: 2, flexWrap: "wrap" }}>
                                    {upcomingEvents.map(ev => {
                                        const start = new Date(ev.starts_at);
                                        const end = new Date(ev.ends_at);
                                        const now = new Date();
                                        const diffDays = Math.ceil((start.getTime() - now.getTime()) / (1000 * 3600 * 24));

                                        let label = "";
                                        let color: "error" | "warning" | "info" = "info";

                                        if (start <= now && end >= now) {
                                            label = `Сейчас идёт: ${EVENT_TYPE_LABELS[ev.event_type] || ev.event_type}`;
                                            color = "error";
                                        } else if (diffDays === 0) {
                                            label = `Сегодня начнётся: ${EVENT_TYPE_LABELS[ev.event_type] || ev.event_type}`;
                                            color = "warning";
                                        } else if (diffDays > 0 && diffDays <= 7) {
                                            label = `Через ${diffDays} дн.: ${EVENT_TYPE_LABELS[ev.event_type] || ev.event_type}`;
                                            color = "warning";
                                        } else {
                                            label = `${start.toLocaleDateString("ru-RU")}: ${EVENT_TYPE_LABELS[ev.event_type] || ev.event_type}`;
                                            color = "info";
                                        }

                                        return (
                                            <Alert
                                                key={ev.id}
                                                severity={color}
                                                icon={color === 'error' ? <WarningIcon /> : <EventIcon />}
                                                sx={{ py: 0, px: 2, borderRadius: 4, '& .MuiAlert-message': { fontSize: '0.85rem', fontWeight: 600 } }}
                                            >
                                                {label}
                                            </Alert>
                                        );
                                    })}
                                </Box>
                            )}

                            {repairsError && (
                                <Alert severity="error" sx={{ mb: 2, flexShrink: 0 }} onClose={() => setRepairsError(null)}>
                                    {repairsError}
                                </Alert>
                            )}

                            {!selectedEquipmentId ? (
                                <Box sx={{ display: "flex", alignItems: "center", justifyContent: "center", flexGrow: 1, color: "#7f8c8d", flexDirection: "column", gap: 1 }}>
                                    <Typography variant="body1">Выберите строку в таблице оборудования, чтобы увидеть его ремонты</Typography>
                                </Box>
                            ) : loadingRepairs && repairs.length === 0 ? (
                                <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", flexGrow: 1 }}>
                                    <CircularProgress />
                                </Box>
                            ) : (
                                <Box sx={{ flexGrow: 1, position: "relative", minHeight: 0 }}>
                                    <Box
                                        ref={timelineContainerRef}
                                        sx={{
                                            position: "absolute", top: 0, left: 0, right: 0, bottom: 0,
                                            "& .vis-item": { borderColor: "transparent" },
                                            "& .vis-label": { fontWeight: 600, color: "#2c3e50" },
                                            visibility: isTimelineReady ? "visible" : "hidden",
                                            opacity: isTimelineReady ? 1 : 0,
                                            transition: "opacity 0.2s ease-in",
                                        }}
                                    />
                                    {!isTimelineReady && (
                                        <Box sx={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', bgcolor: 'rgba(255,255,255,0.8)', zIndex: 10 }}>
                                            <CircularProgress size={24} />
                                        </Box>
                                    )}
                                </Box>
                            )}
                        </CardContent>
                    </Card>
                </Allotment.Pane>
            </Allotment>

            <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: "block", textAlign: "center", flexShrink: 0 }}>
                💡 Перетаскивайте границы ремонта мышкой для изменения времени • Клик по событию — редактирование или удаление
            </Typography>

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
                        <Button onClick={handleSaveEquipment} variant="contained">Сохранить</Button>
                    </>
                }
            >
                <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
                    <TextField
                        autoFocus margin="dense" label="Наименование" fullWidth
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
                        margin="dense" label="Объем (кг)" type="number" fullWidth
                        value={formData.volume_kg}
                        onChange={(e) => setFormData({ ...formData, volume_kg: Number(e.target.value) })}
                    />
                    <TextField
                        margin="dense" label="Коэффициент скорости" type="number" fullWidth
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
                            <Button onClick={handleDeleteRepair} color="error" startIcon={<DeleteIcon />} sx={{ mr: "auto" }}>
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
                        margin="dense" label="Начало" type="datetime-local" fullWidth
                        value={repairForm.starts_at}
                        onChange={(e) => setRepairForm({ ...repairForm, starts_at: e.target.value })}
                        slotProps={{ inputLabel: { shrink: true } }}
                    />
                    <TextField
                        margin="dense" label="Окончание" type="datetime-local" fullWidth
                        value={repairForm.ends_at}
                        onChange={(e) => setRepairForm({ ...repairForm, ends_at: e.target.value })}
                        slotProps={{ inputLabel: { shrink: true } }}
                    />
                    <TextField
                        margin="dense" label="Комментарий" fullWidth multiline rows={2}
                        value={repairForm.comment}
                        onChange={(e) => setRepairForm({ ...repairForm, comment: e.target.value })}
                    />
                </Box>
            </DraggableDialog>
        </Box>
    );
};

export default EquipmentPage;