// frontend/src/pages/GanttPage.tsx
import React, {useCallback, useEffect, useRef, useState} from 'react';
import {useNavigate} from 'react-router-dom';
import {
    Alert,
    Box,
    Button,
    Card,
    CardContent,
    Checkbox,
    Chip,
    CircularProgress,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    Divider,
    FormControl,
    FormControlLabel,
    IconButton,
    InputAdornment,
    InputLabel,
    MenuItem,
    Select,
    TextField,
    ToggleButton,
    ToggleButtonGroup,
    Tooltip,
    Typography,
} from '@mui/material';
import {
    ArrowBack as ArrowBackIcon,
    ArrowForward as ArrowForwardIcon,
    CalendarViewDay as CalendarViewDayIcon,
    CalendarViewMonth as CalendarViewMonthIcon,
    CalendarViewWeek as CalendarViewWeekIcon,
    Clear as ClearIcon,
    Download as DownloadIcon,
    FilterAltOff as FilterAltOffIcon,
    FitScreen as FitScreenIcon,
    History as HistoryIcon,
    Lock as LockIcon,
    QrCodeScanner as QrCodeScannerIcon,
    Refresh as RefreshIcon,
    Search as SearchIcon,
    Today as TodayIcon,
    ZoomIn as ZoomInIcon,
    ZoomOut as ZoomOutIcon,
} from '@mui/icons-material';

// ==========================================
// ВАЖНО: DataSet импортируем из vis-data,
// т.к. vis-timeline/standalone его НЕ экспортирует
// в текущей версии 8.5.4.
// ==========================================
import {Timeline, type TimelineOptions} from 'vis-timeline/standalone';
import {DataSet} from 'vis-data';
import 'vis-timeline/styles/vis-timeline-graph2d.min.css';
import {ganttApi, rescheduleApi} from '../services/api';
import {API_BASE_URL} from '../config';
import {usePlan} from '../context/PlainContext';
import type {CoolingMode, CzStatus} from '../types';

// ==========================================
// Типы для vis-timeline
// ==========================================

interface GanttItem {
    id: string;
    group: string;
    start: string;
    end: string;
    content?: string;
    title?: string;
    style?: string;
    className?: string;
}

interface GanttGroup {
    id: string;
    content: string;
}

const OPERATION_COLORS: Record<string, string> = {
    'Нагрев': '#e74c3c',
    'Охлаждение': '#3498db',
    'Перемешивание': '#9b59b6',
    'Промывка': '#95a5a6',
    'Замывка': '#7f8c8d',
    'Лабораторный': '#f1c40f',
    'Загрузка': '#2ecc71',
    'Перекачка': '#e67e22',
};

const getOperationColor = (operationName: string) => {
    for (const [key, color] of Object.entries(OPERATION_COLORS)) {
        if (operationName.includes(key)) return color;
    }
    return '#bdc3c7';
};

type ItemType = 'task' | 'setup' | 'downtime';

interface TaskData {
    id: string;
    batch_id: string;
    operation_name: string;
    equipment_id: string;
    product_id: string;
    start: string;
    end: string;
    duration_minutes: number;
    item_type?: ItemType;
    setup_type?: 'same_pf' | 'diff_pf';
    downtime_type?: 'WEEKEND' | 'REPAIR' | 'BREAKDOWN';
    is_lab_blocked?: boolean;
    lab_status?: string | null;
    lab_block_reason?: string | null;
    cooling_mode?: CoolingMode;
    task_role?: string | null;
    cz_status?: CzStatus | null;
    cz_marked_qty?: number | null;
}

// ==========================================
// Утилита: ключ для localStorage по версии
// ==========================================
const getViewportStorageKey = (versionId: string | null) =>
    `aps_gantt_viewport_${versionId || 'draft'}`;

interface ViewportState {
    start: string;
    end: string;
}

const GanttPage: React.FC = () => {
    // Итерация 13.3: навигация для перехода в «Аудит»
    const navigate = useNavigate();

    const containerRef = useRef<HTMLDivElement>(null);
    const minimapContainerRef = useRef<HTMLDivElement>(null);
    const timelineRef = useRef<Timeline | null>(null);
    const minimapRef = useRef<Timeline | null>(null);
    const handleTaskEditRef = useRef<(taskId: string) => void>(() => {});

    // Сохранение viewport
    const viewportRef = useRef<ViewportState | null>(null);
    const suppressViewportSyncRef = useRef<boolean>(false);
    const minimapSyncingRef = useRef<boolean>(false);

    const {currentVersionId, currentPlanName} = usePlan();
    const isReadOnly = currentVersionId !== null;

    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [stats, setStats] = useState({
        totalTasks: 0,
        makespanHours: 0,
        equipmentCount: 0,
        blockedCount: 0,
        coolingSlowCount: 0,
        czIncompleteCount: 0,
    });
    const [tasks, setTasks] = useState<TaskData[]>([]);
    const [equipmentList, setEquipmentList] = useState<string[]>([]);
    const [productList, setProductList] = useState<string[]>([]);

    const [filteredCount, setFilteredCount] = useState(0);

    const [zoomPreset, setZoomPreset] = useState<'day' | 'week' | 'month' | 'custom'>('custom');

    // ==========================================
    // Фильтры
    // ==========================================
    const [searchQuery, setSearchQuery] = useState('');
    const [equipmentFilter, setEquipmentFilter] = useState<string[]>([]);
    const [productFilter, setProductFilter] = useState<string[]>([]);
    const [showSetups, setShowSetups] = useState(true);
    const [showDowntimes, setShowDowntimes] = useState(true);
    const [showOnlyBlocked, setShowOnlyBlocked] = useState(false);
    const [showOnlySlowCooling, setShowOnlySlowCooling] = useState(false);
    const [showOnlyCzIncomplete, setShowOnlyCzIncomplete] = useState(false);

    const hasActiveFilters =
        searchQuery.length > 0 ||
        equipmentFilter.length > 0 ||
        productFilter.length > 0 ||
        showOnlyBlocked ||
        showOnlySlowCooling ||
        showOnlyCzIncomplete;

    const [editDialogOpen, setEditDialogOpen] = useState(false);
    const [selectedTask, setSelectedTask] = useState<TaskData | null>(null);
    const [editFormData, setEditFormData] = useState({start: '', end: ''});

    const clickTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    // ==========================================
    // Загрузка данных
    // ==========================================
    const loadGanttData = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const data = await ganttApi.getData(currentVersionId || undefined);

            const typedTasks = data.tasks as TaskData[];

            const blockedCount = typedTasks.filter((t) => t.is_lab_blocked === true).length;
            const coolingSlowCount = typedTasks.filter((t) => t.cooling_mode === 'slow').length;
            const czIncompleteCount = typedTasks.filter(
                (t) =>
                    t.task_role === 'LINE_FILL' &&
                    t.cz_status &&
                    t.cz_status !== 'COMPLETED'
            ).length;

            setStats({
                totalTasks: data.total_tasks,
                makespanHours: data.makespan_hours,
                equipmentCount: data.equipment_list.length,
                blockedCount,
                coolingSlowCount,
                czIncompleteCount,
            });
            setTasks(data.tasks);
            setEquipmentList(data.equipment_list);
            setProductList(data.product_list);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Ошибка загрузки данных Ганта');
        } finally {
            setLoading(false);
        }
    }, [currentVersionId]);

    // ==========================================
    // Загрузка viewport из localStorage при смене версии
    // ==========================================
    useEffect(() => {
        const key = getViewportStorageKey(currentVersionId);
        try {
            const raw = localStorage.getItem(key);
            if (raw) {
                const parsed = JSON.parse(raw) as ViewportState;
                if (parsed.start && parsed.end) {
                    viewportRef.current = parsed;
                    return;
                }
            }
        } catch {
            // ignore
        }
        viewportRef.current = null;
    }, [currentVersionId]);

    const saveViewportToStorage = useCallback(
        (view: ViewportState) => {
            const key = getViewportStorageKey(currentVersionId);
            try {
                localStorage.setItem(key, JSON.stringify(view));
            } catch {
                // ignore quota
            }
        },
        [currentVersionId]
    );

    useEffect(() => {
        void loadGanttData();
        return () => {
            if (timelineRef.current) {
                timelineRef.current.destroy();
                timelineRef.current = null;
            }
            if (minimapRef.current) {
                minimapRef.current.destroy();
                minimapRef.current = null;
            }
            if (clickTimeoutRef.current) {
                clearTimeout(clickTimeoutRef.current);
                clickTimeoutRef.current = null;
            }
        };
    }, [loadGanttData]);

    const handleResetFilters = () => {
        setSearchQuery('');
        setEquipmentFilter([]);
        setProductFilter([]);
        setShowOnlyBlocked(false);
        setShowOnlySlowCooling(false);
        setShowOnlyCzIncomplete(false);
    };

    // Итерация 13.3: переход в Аудит
    const handleOpenAudit = () => {
        // Открываем аудит с фильтром по перепланированиям и остаткам
        // (самые частые причины изменения плана)
        navigate('/audit?sources=RESCHEDULE,LAB,CZ');
    };

// ==========================================
// generateSetups — Итерация 9 (fix)
// ==========================================
// Раньше setup растягивался на весь промежуток между двумя
// задачами, из-за чего мог пересекать выходные и достигать
// 11 дней. Это семантически неверно.
//
// Теперь:
//   1. Setup имеет ФИКСИРОВАННУЮ длительность (30 или 90 мин).
//   2. Setup показывается ТОЛЬКО если разрыв между задачами
//      ≤ MAX_SETUP_GAP_MINUTES (4 часа). Иначе — это не замывка,
//      а ожидание (ремонт, отсутствие заказов, выходные).
//   3. Setup примыкает к НАЧАЛУ следующей задачи:
//      [next.start - duration, next.start].
//   4. Setup не показывается, если он попадает на выходной.
// ==========================================
    const MAX_SETUP_GAP_MINUTES = 4 * 60;
    const SETUP_DURATION_SAME_PF = 30;
    const SETUP_DURATION_DIFF_PF = 90;

    const isWeekendDate = (d: Date): boolean => {
        const dow = d.getDay();
        return dow === 0 || dow === 6;
    };

    const generateSetups = (tasksData: TaskData[]): TaskData[] => {
        const setups: TaskData[] = [];
        const byEquipment: Record<string, TaskData[]> = {};

        tasksData.forEach((task) => {
            if (!byEquipment[task.equipment_id]) {
                byEquipment[task.equipment_id] = [];
            }
            byEquipment[task.equipment_id].push(task);
        });

        Object.entries(byEquipment).forEach(([eqId, eqTasks]) => {
            eqTasks.sort(
                (a, b) => new Date(a.start).getTime() - new Date(b.start).getTime()
            );
            for (let i = 0; i < eqTasks.length - 1; i++) {
                const curr = eqTasks[i];
                const next = eqTasks[i + 1];

                if (curr.batch_id === next.batch_id) continue;

                const gapMinutes = Math.round(
                    (new Date(next.start).getTime() -
                        new Date(curr.end).getTime()) /
                    60000
                );

                // Нет разрыва или он слишком большой — замывки нет
                if (gapMinutes <= 0 || gapMinutes > MAX_SETUP_GAP_MINUTES) {
                    continue;
                }

                const setupType =
                    curr.product_id === next.product_id ? 'same_pf' : 'diff_pf';
                const nominalDuration =
                    setupType === 'same_pf'
                        ? SETUP_DURATION_SAME_PF
                        : SETUP_DURATION_DIFF_PF;

                // Setup не может быть длиннее фактического разрыва
                const actualDuration = Math.min(nominalDuration, gapMinutes);

                // Setup примыкает к началу следующей задачи
                const setupEnd = new Date(next.start);
                const setupStart = new Date(
                    setupEnd.getTime() - actualDuration * 60000
                );

                // Не показываем setup, если он попадает на выходной
                if (isWeekendDate(setupStart) || isWeekendDate(setupEnd)) {
                    continue;
                }

                setups.push({
                    id: `setup_${curr.id}_${next.id}`,
                    batch_id: 'Замывка',
                    operation_name: '🧼 Замывка',
                    equipment_id: eqId,
                    product_id: '—',
                    start: setupStart.toISOString(),
                    end: setupEnd.toISOString(),
                    duration_minutes: actualDuration,
                    item_type: 'setup',
                    setup_type: setupType,
                });
            }
        });
        return setups;
    };

    // ==========================================
    // Генерация выходных
    // ==========================================
    const generateWeekends = (
        tasksData: TaskData[],
        equipment: string[]
    ): TaskData[] => {
        if (tasksData.length === 0 || equipment.length === 0) return [];
        const weekends: TaskData[] = [];
        const startDate = new Date(
            Math.min(...tasksData.map((t) => new Date(t.start).getTime()))
        );
        const endDate = new Date(
            Math.max(...tasksData.map((t) => new Date(t.end).getTime()))
        );
        startDate.setHours(0, 0, 0, 0);
        endDate.setHours(23, 59, 59, 999);

        const current = new Date(startDate);
        while (current <= endDate) {
            const dayOfWeek = current.getDay();
            if (dayOfWeek === 0 || dayOfWeek === 6) {
                const weekendStart = new Date(current);
                const weekendEnd = new Date(current);
                weekendEnd.setHours(23, 59, 59, 999);
                equipment.forEach((eqId) => {
                    weekends.push({
                        id: `weekend_${current.toISOString().split('T')[0]}_${eqId}`,
                        batch_id: 'Выходной',
                        operation_name: ' Выходной',
                        equipment_id: eqId,
                        product_id: '—',
                        start: weekendStart.toISOString(),
                        end: weekendEnd.toISOString(),
                        duration_minutes: 24 * 60,
                        item_type: 'downtime',
                        downtime_type: 'WEEKEND',
                    });
                });
            }
            current.setDate(current.getDate() + 1);
        }
        return weekends;
    };

    const handleTaskEdit = useCallback(
        (taskId: string) => {
            if (isReadOnly) return;
            const taskData = tasks.find((t) => t.id === taskId);
            if (taskData) {
                setSelectedTask(taskData);
                setEditFormData({start: taskData.start, end: taskData.end});
                setEditDialogOpen(true);
            }
        },
        [tasks, isReadOnly]
    );

    useEffect(() => {
        handleTaskEditRef.current = handleTaskEdit;
    }, [handleTaskEdit]);

    // ==========================================
    // Навигация: pan
    // ==========================================
    const panByFactor = useCallback((factor: number) => {
        if (!timelineRef.current) return;
        const range = timelineRef.current.getWindow();
        const interval = range.end.getTime() - range.start.getTime();
        const shift = interval * factor;
        timelineRef.current.setWindow(
            new Date(range.start.getTime() + shift),
            new Date(range.end.getTime() + shift),
            {animation: {duration: 300, easingFunction: 'easeInOutQuad'}}
        );
    }, []);

    const handlePanLeft = useCallback(() => panByFactor(-0.5), [panByFactor]);
    const handlePanRight = useCallback(() => panByFactor(0.5), [panByFactor]);

    // ==========================================
    // Навигация: zoom
    // ==========================================
    const zoomByFactor = useCallback(
        (factor: number) => {
            if (!timelineRef.current) return;
            const range = timelineRef.current.getWindow();
            const center = (range.start.getTime() + range.end.getTime()) / 2;
            const half = ((range.end.getTime() - range.start.getTime()) / 2) * factor;
            timelineRef.current.setWindow(
                new Date(center - half),
                new Date(center + half),
                {animation: {duration: 300, easingFunction: 'easeInOutQuad'}}
            );
            setZoomPreset('custom');
        },
        []
    );

    const handleZoomIn = useCallback(() => zoomByFactor(0.7), [zoomByFactor]);
    const handleZoomOut = useCallback(() => zoomByFactor(1.4), [zoomByFactor]);

    const setWindowAroundCenter = useCallback((halfMs: number) => {
        if (!timelineRef.current) return;
        const range = timelineRef.current.getWindow();
        const center = (range.start.getTime() + range.end.getTime()) / 2;
        timelineRef.current.setWindow(
            new Date(center - halfMs),
            new Date(center + halfMs),
            {animation: {duration: 300, easingFunction: 'easeInOutQuad'}}
        );
    }, []);

    const handleZoomDay = useCallback(() => {
        setWindowAroundCenter(1000 * 60 * 60 * 8);
        setZoomPreset('day');
    }, [setWindowAroundCenter]);

    const handleZoomWeek = useCallback(() => {
        setWindowAroundCenter(1000 * 60 * 60 * 24 * 3);
        setZoomPreset('week');
    }, [setWindowAroundCenter]);

    const handleZoomMonth = useCallback(() => {
        setWindowAroundCenter(1000 * 60 * 60 * 24 * 12);
        setZoomPreset('month');
    }, [setWindowAroundCenter]);

    const handleFitAll = useCallback(() => {
        if (!timelineRef.current) return;
        suppressViewportSyncRef.current = true;
        timelineRef.current.fit({
            animation: {duration: 300, easingFunction: 'easeInOutQuad'},
        });
        setZoomPreset('custom');
        setTimeout(() => {
            suppressViewportSyncRef.current = false;
            if (timelineRef.current) {
                const range = timelineRef.current.getWindow();
                const view: ViewportState = {
                    start: new Date(range.start).toISOString(),
                    end: new Date(range.end).toISOString(),
                };
                viewportRef.current = view;
                saveViewportToStorage(view);
            }
        }, 400);
    }, [saveViewportToStorage]);

    const handleGoToToday = useCallback(() => {
        if (!timelineRef.current) return;
        const now = new Date();
        const half = 1000 * 60 * 60 * 24 * 3;
        timelineRef.current.setWindow(
            new Date(now.getTime() - half),
            new Date(now.getTime() + half),
            {animation: {duration: 300, easingFunction: 'easeInOutQuad'}}
        );
        setZoomPreset('custom');
    }, []);

    const handleExport = () => {
        const params = currentVersionId ? `?version_id=${currentVersionId}` : '';
        window.open(`${API_BASE_URL}/api/v1/gantt/export${params}`, '_blank');
    };

    const handleSaveTask = async () => {
        if (!selectedTask || isReadOnly) return;
        try {
            setTasks((prev) =>
                prev.map((t) =>
                    t.id === selectedTask.id
                        ? {...t, start: editFormData.start, end: editFormData.end}
                        : t
                )
            );
            setEditDialogOpen(false);
        } catch (err) {
            console.error('Error saving task:', err);
        }
    };

    const formatDateForInput = (isoString: string) => {
        const date = new Date(isoString);
        const pad = (n: number) => n.toString().padStart(2, '0');
        return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(
            date.getDate()
        )}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
    };

    // ==========================================
    // persistCurrentViewport
    // ==========================================
    const persistCurrentViewport = useCallback(() => {
        if (!timelineRef.current) return;
        if (suppressViewportSyncRef.current) return;

        const range = timelineRef.current.getWindow();
        if (!range || !range.start || !range.end) return;

        const view: ViewportState = {
            start: new Date(range.start).toISOString(),
            end: new Date(range.end).toISOString(),
        };
        viewportRef.current = view;
        saveViewportToStorage(view);
    }, [saveViewportToStorage]);

    // ==========================================
    // Рендер Timeline + Minimap
    // ==========================================
    const renderTimeline = useCallback(
        (tasksData: TaskData[], equipment: string[]) => {
            if (!containerRef.current) return;

            // Сохраняем текущий viewport
            if (timelineRef.current && !suppressViewportSyncRef.current) {
                try {
                    const range = timelineRef.current.getWindow();
                    if (range && range.start && range.end) {
                        viewportRef.current = {
                            start: new Date(range.start).toISOString(),
                            end: new Date(range.end).toISOString(),
                        };
                        saveViewportToStorage(viewportRef.current);
                    }
                } catch {
                    // ignore
                }
            }

            if (timelineRef.current) {
                timelineRef.current.destroy();
                timelineRef.current = null;
            }
            if (minimapRef.current) {
                minimapRef.current.destroy();
                minimapRef.current = null;
            }

            // Фильтрация
            let filteredTasks = tasksData.filter(
                (task) => task.item_type === 'task' || !task.item_type
            );

            if (showOnlyBlocked) {
                filteredTasks = filteredTasks.filter((task) => task.is_lab_blocked === true);
            }
            if (showOnlySlowCooling) {
                filteredTasks = filteredTasks.filter((task) => task.cooling_mode === 'slow');
            }
            if (showOnlyCzIncomplete) {
                filteredTasks = filteredTasks.filter(
                    (task) =>
                        task.task_role === 'LINE_FILL' &&
                        task.cz_status &&
                        task.cz_status !== 'COMPLETED'
                );
            }
            if (searchQuery) {
                const query = searchQuery.toLowerCase();
                filteredTasks = filteredTasks.filter(
                    (task) =>
                        task.operation_name.toLowerCase().includes(query) ||
                        task.batch_id.toLowerCase().includes(query) ||
                        task.product_id.toLowerCase().includes(query)
                );
            }
            if (equipmentFilter.length > 0) {
                filteredTasks = filteredTasks.filter((task) =>
                    equipmentFilter.includes(task.equipment_id)
                );
            }
            if (productFilter.length > 0) {
                filteredTasks = filteredTasks.filter((task) =>
                    productFilter.includes(task.product_id)
                );
            }

            setFilteredCount(filteredTasks.length);

            const setups = showSetups ? generateSetups(filteredTasks) : [];
            const weekends = showDowntimes ? generateWeekends(filteredTasks, equipment) : [];
            const allItems = [...filteredTasks, ...setups, ...weekends];

            if (allItems.length === 0) {
                if (containerRef.current) containerRef.current.innerHTML = '';
                if (minimapContainerRef.current) minimapContainerRef.current.innerHTML = '';
                return;
            }

            // Группы (явный тип)
            const groupsArray: GanttGroup[] = equipment.map((eq) => ({
                id: eq,
                content: `<b>${eq}</b>`,
            }));

            // Items (явный тип GanttItem[])
            const itemsArray: GanttItem[] = allItems.map((task) => {
                const itemType = task.item_type || 'task';
                const color = getOperationColor(task.operation_name);
                let style = '';
                let title = '';
                let className = '';

                if (itemType === 'task') {
                    const isBlocked = task.is_lab_blocked === true;
                    const isSlowCooling = task.cooling_mode === 'slow';
                    const isCzIncomplete =
                        task.task_role === 'LINE_FILL' &&
                        !!task.cz_status &&
                        task.cz_status !== 'COMPLETED';

                    if (isBlocked) {
                        style = `background-color: #ffebee; border: 2px solid #e74c3c; border-radius: 4px;`;
                        className = 'item-blocked';
                    } else if (isSlowCooling) {
                        style = `background-color: #fff3e0; border: 2px dashed #e67e22; border-radius: 4px;`;
                        className = 'item-cooling-slow';
                    } else if (isCzIncomplete) {
                        style = `background-color: #e3f2fd; border: 2px dotted #1976d2; border-radius: 4px;`;
                        className = 'item-cz-incomplete';
                    } else {
                        style = `background-color: ${color}30; border-left: 4px solid ${color}; border-radius: 4px;`;
                    }

                    const blockedBadge = isBlocked
                        ? `<div style="color: #e74c3c; font-weight: bold; margin-top: 4px;">🔒 ЗАБЛОКИРОВАНО ЛАБОРАТОРИЕЙ</div>
                           ${
                            task.lab_block_reason
                                ? `<div style="color: #e74c3c; font-size: 11px; margin-top: 2px;">Причина: ${task.lab_block_reason}</div>`
                                : ''
                        }`
                        : '';

                    let coolingBadge = '';
                    if (task.cooling_mode === 'slow') {
                        coolingBadge = `
                            <div style="color: #e67e22; font-weight: bold; margin-top: 4px;">
                                ⏳ ОХЛАЖДЕНИЕ ЗАМЕДЛЕНО (×1.3)
                            </div>
                            <div style="color: #e67e22; font-size: 11px; margin-top: 2px;">
                                Зона охлаждения перегружена (2+ реактора одновременно)
                            </div>
                        `;
                    } else if (task.cooling_mode === 'fast') {
                        coolingBadge = `
                            <div style="color: #3498db; font-size: 11px; margin-top: 4px;">
                                ❄️ Охлаждение в обычном режиме
                            </div>
                        `;
                    }

                    let czBadge = '';
                    if (task.task_role === 'LINE_FILL' && task.cz_status) {
                        const czLabel =
                            task.cz_status === 'COMPLETED'
                                ? '🟢 ЧЗ завершено'
                                : task.cz_status === 'IN_PROGRESS'
                                    ? '🔵 ЧЗ в работе'
                                    : task.cz_status === 'PENDING'
                                        ? '🟡 ЧЗ ожидает'
                                        : '⚪ ЧЗ не требуется';
                        czBadge = `
                            <div style="margin-top: 4px; font-size: 11px;">
                                <b>${czLabel}</b>
                                ${
                            task.cz_marked_qty != null
                                ? `<br>Промаркировано: ${task.cz_marked_qty}`
                                : ''
                        }
                            </div>
                        `;
                    }

                    title = `
            <div style="padding: 8px; min-width: 280px;">
              <b style="font-size: 14px; color: ${isBlocked ? '#e74c3c' : '#2c3e50'};">${isBlocked ? '🔒 ' : ''}${isSlowCooling ? '⏳ ' : ''}${task.operation_name}</b><br>
              <hr style="margin: 8px 0; border: none; border-top: 1px solid #ecf0f1;">
              <div style="font-size: 12px; line-height: 1.6;">
                <b>Партия:</b> ${task.batch_id}<br>
                <b>Продукт:</b> ${task.product_id}<br>
                <b>Оборудование:</b> ${task.equipment_id}<br>
                <b>Длительность:</b> ${task.duration_minutes} мин<br>
                <b>Начало:</b> ${new Date(task.start).toLocaleString('ru-RU')}<br>
                <b>Конец:</b> ${new Date(task.end).toLocaleString('ru-RU')}
                ${blockedBadge}
                ${coolingBadge}
                ${czBadge}
              </div>
            </div>
          `;
                } else if (itemType === 'setup') {
                    const setupColor =
                        task.setup_type === 'same_pf' ? '#95a5a6' : '#e67e22';
                    const setupLabel =
                        task.setup_type === 'same_pf'
                            ? 'тот же ПФ (30 мин)'
                            : 'другой ПФ (90 мин)';
                    style = `background-color: ${setupColor}25; border: 2px dashed ${setupColor}; border-radius: 4px;`;
                    className = 'item-setup';
                    title = `
            <div style="padding: 8px; min-width: 280px; background: #fff9e6;">
              <b style="font-size: 14px; color: #e67e22;"> ${task.operation_name}</b><br>
              <hr style="margin: 8px 0; border: none; border-top: 1px solid #ecf0f1;">
              <div style="font-size: 12px; line-height: 1.6;">
                <b>Тип:</b> ${setupLabel}<br>
                <b>Оборудование:</b> ${task.equipment_id}<br>
                <b>Длительность:</b> ${task.duration_minutes} мин<br>
                <b>Начало:</b> ${new Date(task.start).toLocaleString('ru-RU')}<br>
                <b>Конец:</b> ${new Date(task.end).toLocaleString('ru-RU')}
              </div>
            </div>
          `;
                } else if (itemType === 'downtime') {
                    style = `background-color: #9b59b620; border: 1px solid #9b59b6; border-radius: 4px; background-image: repeating-linear-gradient(45deg, transparent, transparent 10px, #9b59b615 10px, #9b59b615 20px);`;
                    className = 'item-downtime';
                    title = `
            <div style="padding: 8px; min-width: 280px; background: #f5eef8;">
              <b style="font-size: 14px; color: #9b59b6;">📅 ${task.operation_name}</b><br>
              <hr style="margin: 8px 0; border: none; border-top: 1px solid #ecf0f1;">
              <div style="font-size: 12px; line-height: 1.6;">
                <b>Тип:</b> ${task.downtime_type}<br>
                <b>Длительность:</b> ${task.duration_minutes} мин (${(
                        task.duration_minutes / 60
                    ).toFixed(1)} ч)<br>
                <b>Начало:</b> ${new Date(task.start).toLocaleString('ru-RU')}<br>
                <b>Конец:</b> ${new Date(task.end).toLocaleString('ru-RU')}
              </div>
            </div>
          `;
                }

                const blockedIcon = task.is_lab_blocked ? '🔒 ' : '';
                const slowCoolingIcon = task.cooling_mode === 'slow' ? '⏳ ' : '';
                const czIcon =
                    task.task_role === 'LINE_FILL' &&
                    task.cz_status &&
                    task.cz_status !== 'COMPLETED'
                        ? '📷 '
                        : '';

                return {
                    id: task.id,
                    group: task.equipment_id,
                    content: `
            <div style="padding: 4px; font-size: 11px;">
              <div style="font-weight: bold; color: ${
                        task.is_lab_blocked
                            ? '#e74c3c'
                            : task.cooling_mode === 'slow'
                                ? '#e67e22'
                                : '#2c3e50'
                    }; margin-bottom: 2px;">
                ${blockedIcon}${slowCoolingIcon}${czIcon}${task.operation_name}
              </div>
              <div style="font-size: 10px; color: #555;">
                ${task.duration_minutes} мин
              </div>
            </div>
          `,
                    start: task.start,
                    end: task.end,
                    style: style,
                    title: title,
                    className: className,
                };
            });

            // Миникарта: используем тот же тип GanttItem, но без content/title
            const minimapItemsArray: GanttItem[] = itemsArray.map((item) => ({
                id: item.id,
                group: item.group,
                start: item.start,
                end: item.end,
                style: item.style,
                className: item.className,
            }));

            const minimapGroupsArray: GanttGroup[] = equipment.map((eq) => ({
                id: eq,
                content: '',
            }));

            const groups = new DataSet<GanttGroup>(groupsArray);
            const items = new DataSet<GanttItem>(itemsArray);
            const minimapGroups = new DataSet<GanttGroup>(minimapGroupsArray);
            const minimapItems = new DataSet<GanttItem>(minimapItemsArray);

            // ==========================================
            // Итерация 11 (fix): pan + zoom + drag одновременно
            // ==========================================
            // Компромисс (Механизм 3):
            //   1. moveable: true  → pan по пустому месту.
            //   2. zoomable: true  → zoom колёсиком.
            //   3. editable.updateTime как ФУНКЦИЯ → drag только для
            //      реальных задач. Setup и downtime — не таскаются.
            //   4. CSS в index.css → курсоры grab / grabbing / not-allowed.
            //
            // vis-timeline сам разделяет жесты:
            //   - mousedown на задаче + drag  → перемещение задачи
            //   - mousedown на пустом месте + drag → pan диаграммы
            // ==========================================
            const options: TimelineOptions = {
                groupOrder: 'content',

                // ✅ Pan: перетаскивание диаграммы по пустому месту.
                moveable: true,

                // ✅ Zoom колёсиком мыши (без Ctrl).
                zoomable: true,

                // ✅ Drag только для реальных задач (не setup / не downtime).
                // Принимает функцию (item) => boolean в рантайме,
                // но типы vis-timeline объявляют только boolean.
                // Поэтому используем `as any` для приведения.
                editable: {
                    add: false,
                    updateTime: ((item: any) => {
                        if (isReadOnly) return false;
                        const itemId = String(item?.id ?? '');
                        // Setup и downtime не таскаются — их перетаскивание
                        // интерпретируется как pan диаграммы.
                        if (itemId.startsWith('setup_') || itemId.startsWith('weekend_')) {
                            return false;
                        }
                        return true;
                    }) as any,
                    updateGroup: false,
                    remove: false,
                } as any,
                selectable: true,
                multiselect: false,
                margin: {item: 2, axis: 5},
                orientation: 'top',
                stack: false,
                showCurrentTime: true,
                zoomMin: 1000 * 60 * 60 * 2,
                zoomMax: 1000 * 60 * 60 * 24 * 90,
                format: {
                    minorLabels: {hour: 'HH:mm', weekday: 'D MMM'},
                    majorLabels: {day: 'D MMMM YYYY'},
                },
                locale: 'ru',
                tooltip: {
                    followMouse: true,
                    overflowMethod: 'cap',
                    delay: 100,
                },
                snap: (date: Date) => {
                    const minutes = 15;
                    const ms = 1000 * 60 * minutes;
                    return new Date(Math.round(date.getTime() / ms) * ms);
                },
                onMove: async (item: any, callback: (item: any) => void) => {
                    // Не даём таскать setup и downtime
                    // (страховка на случай, если editable.updateTime
                    //  не сработает — оставляем для надёжности).
                    const itemId = String(item?.id ?? '');
                    if (itemId.startsWith('setup_') || itemId.startsWith('weekend_')) {
                        const original = tasks.find((t) => t.id === item.id);
                        if (original) {
                            callback({...item, start: original.start, end: original.end});
                        } else {
                            callback(item);
                        }
                        return;
                    }

                    if (isReadOnly) {
                        const original = tasks.find((t) => t.id === item.id);
                        if (original) {
                            callback({...item, start: original.start, end: original.end});
                        } else {
                            callback(item);
                        }
                        return;
                    }

                    const task = tasks.find((t) => t.id === item.id);
                    if (!task) {
                        callback(item);
                        return;
                    }

                    const newStart = new Date(item.start).toISOString();
                    const newEnd = new Date(item.end).toISOString();
                    const oldStart = new Date(task.start).toISOString();
                    const oldEnd = new Date(task.end).toISOString();

                    if (newStart === oldStart && newEnd === oldEnd) {
                        callback(item);
                        return;
                    }

                    try {
                        await rescheduleApi.moveTask(item.id, newStart, newEnd);
                        setTasks((prev) =>
                            prev.map((t) =>
                                t.id === item.id ? {...t, start: newStart, end: newEnd} : t
                            )
                        );
                        callback(item);
                    } catch (err: any) {
                        const detail = err.response?.data?.detail;
                        const msg =
                            typeof detail === 'string'
                                ? detail
                                : 'Ошибка перемещения задачи';
                        setError(msg);
                        callback({...item, start: task.start, end: task.end});
                    }
                },
            };

            // ==========================================
            // ВАЖНО: `as any` для обхода несовместимости типов
            // между vis-data.DataSet и vis-timeline.Timeline.
            // В рантайме объекты полностью совместимы.
            // ==========================================
            const newTimeline = new Timeline(
                containerRef.current,
                items as any,
                groups as any,
                options
            );
            timelineRef.current = newTimeline;

            // Восстановление viewport
            const saved = viewportRef.current;
            if (saved) {
                try {
                    newTimeline.setWindow(new Date(saved.start), new Date(saved.end), {
                        animation: false,
                    });
                } catch {
                    newTimeline.fit();
                }
            } else {
                newTimeline.fit();
            }

            newTimeline.on('rangechange', () => {
                persistCurrentViewport();
            });

            newTimeline.on('click', (props: any) => {
                if (props.item) {
                    if (clickTimeoutRef.current) {
                        clearTimeout(clickTimeoutRef.current);
                        clickTimeoutRef.current = null;
                        handleTaskEditRef.current(props.item);
                    } else {
                        clickTimeoutRef.current = setTimeout(() => {
                            clickTimeoutRef.current = null;
                        }, 300);
                    }
                }
            });

            // ==========================================
            // Миникарта
            // ==========================================
            if (!minimapContainerRef.current) return;

            const minimapOptions: TimelineOptions = {
                groupOrder: 'content',
                editable: false,
                selectable: false,
                moveable: false,
                margin: {item: 0, axis: 0},
                orientation: 'top',
                stack: false,
                showCurrentTime: true,
                zoomMin: 1000 * 60 * 60 * 2,
                zoomMax: 1000 * 60 * 60 * 24 * 90,
                format: {
                    minorLabels: {hour: '', weekday: ''},
                    majorLabels: {day: ''},
                },
                locale: 'ru',
                height: '100%',
                showMajorLabels: false,
                showMinorLabels: false,
            };

            // ==========================================
            // ВАЖНО: `as any` для обхода несовместимости типов
            // ==========================================
            const newMinimap = new Timeline(
                minimapContainerRef.current,
                minimapItems as any,
                minimapGroups as any,
                minimapOptions
            );
            minimapRef.current = newMinimap;

            const syncMinimapToMain = () => {
                if (!minimapRef.current || !timelineRef.current) return;
                if (minimapSyncingRef.current) return;
                minimapSyncingRef.current = true;
                try {
                    const range = minimapRef.current.getWindow();
                    timelineRef.current.setWindow(range.start, range.end, {
                        animation: false,
                    });
                } finally {
                    setTimeout(() => {
                        minimapSyncingRef.current = false;
                    }, 50);
                }
            };

            const syncMainToMinimap = () => {
                if (!minimapRef.current || !timelineRef.current) return;
                if (minimapSyncingRef.current) return;
                minimapSyncingRef.current = true;
                try {
                    const range = timelineRef.current.getWindow();
                    minimapRef.current.setWindow(range.start, range.end, {
                        animation: false,
                    });
                } finally {
                    setTimeout(() => {
                        minimapSyncingRef.current = false;
                    }, 50);
                }
            };

            try {
                const mainRange = newTimeline.getWindow();
                newMinimap.setWindow(mainRange.start, mainRange.end, {
                    animation: false,
                });
            } catch {
                // ignore
            }

            newMinimap.on('rangechange', syncMinimapToMain);
            newTimeline.on('rangechange', () => {
                persistCurrentViewport();
                syncMainToMinimap();
            });
        },
        [
            searchQuery,
            equipmentFilter,
            productFilter,
            showSetups,
            showDowntimes,
            showOnlyBlocked,
            showOnlySlowCooling,
            showOnlyCzIncomplete,
            isReadOnly,
            tasks,
            setError,
            persistCurrentViewport,
            saveViewportToStorage,
        ]
    );

    useEffect(() => {
        if (tasks.length > 0 && equipmentList.length > 0) {
            renderTimeline(tasks, equipmentList);
        }
    }, [tasks, equipmentList, renderTimeline]);

    if (loading) {
        return (
            <Box sx={{display: 'flex', justifyContent: 'center', mt: 8}}>
                <CircularProgress/>
            </Box>
        );
    }

    return (
        <Box sx={{height: '100%', display: 'flex', flexDirection: 'column'}}>
            {/* Заголовок */}
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
                <Typography
                    variant="h4"
                    component="h1"
                    sx={{fontWeight: 600, color: '#2c3e50'}}
                >
                    Диаграмма Ганта
                </Typography>
                <Box sx={{display: 'flex', gap: 1, flexWrap: 'wrap'}}>
                    {/* Итерация 13.3: кнопка «История изменений» */}
                    <Tooltip title="Открыть журнал аудита (перепланирования, лаборатория, ЧЗ)">
                        <Button
                            variant="outlined"
                            startIcon={<HistoryIcon/>}
                            onClick={handleOpenAudit}
                        >
                            История изменений
                        </Button>
                    </Tooltip>
                    <Button
                        variant="outlined"
                        startIcon={<RefreshIcon/>}
                        onClick={() => void loadGanttData()}
                    >
                        Обновить
                    </Button>
                    <Button
                        variant="contained"
                        color="success"
                        startIcon={<DownloadIcon/>}
                        onClick={handleExport}
                    >
                        Экспорт в Excel
                    </Button>
                </Box>
            </Box>

            {error && (
                <Alert severity="warning" sx={{mb: 2}}>
                    {error}
                    <br/>
                    <Typography variant="body2" sx={{mt: 1}}>
                        💡 Перейдите на вкладку <b>"Планирование"</b> и нажмите{' '}
                        <b>"Построить план"</b>, либо выберите сохраненную версию.
                    </Typography>
                </Alert>
            )}

            {!error && (
                <>
                    {/* Панель статистики и фильтров */}
                    <Card sx={{mb: 2, p: 2, bgcolor: '#f8f9fa'}}>
                        <Box
                            sx={{
                                display: 'flex',
                                flexWrap: 'wrap',
                                gap: 2,
                                alignItems: 'center',
                            }}
                        >
                            <Chip
                                label={
                                    hasActiveFilters
                                        ? `Показано: ${filteredCount} / ${stats.totalTasks}`
                                        : `Всего задач: ${stats.totalTasks}`
                                }
                                color={hasActiveFilters ? 'warning' : 'primary'}
                                variant={hasActiveFilters ? 'filled' : 'outlined'}
                            />
                            <Chip
                                label={`Makespan: ${stats.makespanHours.toFixed(1)} ч`}
                                color="secondary"
                                variant="outlined"
                            />
                            <Chip
                                label={`Оборудование: ${stats.equipmentCount}`}
                                variant="outlined"
                            />
                            {stats.blockedCount > 0 && (
                                <Chip
                                    icon={<LockIcon/>}
                                    label={`Заблокировано: ${stats.blockedCount}`}
                                    color="error"
                                    variant="filled"
                                />
                            )}
                            {stats.coolingSlowCount > 0 && (
                                <Chip
                                    label={`⏳ Замедленное охлаждение: ${stats.coolingSlowCount}`}
                                    color="warning"
                                    variant="filled"
                                />
                            )}
                            {stats.czIncompleteCount > 0 && (
                                <Chip
                                    icon={<QrCodeScannerIcon/>}
                                    label={`📷 Не промаркировано: ${stats.czIncompleteCount}`}
                                    color="info"
                                    variant="filled"
                                />
                            )}

                            {isReadOnly && (
                                <Chip
                                    icon={<LockIcon/>}
                                    label={`Просмотр: ${currentPlanName}`}
                                    color="info"
                                    variant="filled"
                                />
                            )}
                        </Box>

                        <Box
                            sx={{
                                display: 'flex',
                                gap: 1.5,
                                mt: 1.5,
                                flexWrap: 'wrap',
                                alignItems: 'center',
                            }}
                        >
                            {Object.entries(OPERATION_COLORS)
                                .slice(0, 5)
                                .map(([name, color]) => (
                                    <Box
                                        key={name}
                                        sx={{
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: 0.5,
                                            fontSize: '0.85rem',
                                        }}
                                    >
                                        <Box
                                            sx={{
                                                width: 12,
                                                height: 12,
                                                bgcolor: color,
                                                borderRadius: '2px',
                                            }}
                                        />
                                        {name}
                                    </Box>
                                ))}
                            <Box
                                sx={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: 0.5,
                                    fontSize: '0.85rem',
                                }}
                            >
                                <Box
                                    sx={{
                                        width: 12,
                                        height: 12,
                                        bgcolor: '#ffebee',
                                        border: '2px solid #e74c3c',
                                        borderRadius: '2px',
                                    }}
                                />
                                🔒 Заблокировано
                            </Box>
                            <Box
                                sx={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: 0.5,
                                    fontSize: '0.85rem',
                                }}
                            >
                                <Box
                                    sx={{
                                        width: 12,
                                        height: 12,
                                        bgcolor: '#fff3e0',
                                        border: '2px dashed #e67e22',
                                        borderRadius: '2px',
                                    }}
                                />
                                ⏳ Замедленное охлаждение
                            </Box>
                            <Box
                                sx={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: 0.5,
                                    fontSize: '0.85rem',
                                }}
                            >
                                <Box
                                    sx={{
                                        width: 12,
                                        height: 12,
                                        bgcolor: '#e3f2fd',
                                        border: '2px dotted #1976d2',
                                        borderRadius: '2px',
                                    }}
                                />
                                📷 ЧЗ не завершено
                            </Box>
                        </Box>

                        <Box
                            sx={{
                                display: 'flex',
                                gap: 2,
                                mt: 2,
                                flexWrap: 'wrap',
                                alignItems: 'center',
                            }}
                        >
                            <TextField
                                size="small"
                                placeholder="Поиск задач..."
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                sx={{minWidth: 250}}
                                slotProps={{
                                    input: {
                                        startAdornment: (
                                            <InputAdornment position="start">
                                                <SearchIcon/>
                                            </InputAdornment>
                                        ),
                                    },
                                }}
                            />

                            <FormControl size="small" variant="outlined" sx={{minWidth: 200}}>
                                <InputLabel>Оборудование</InputLabel>
                                <Select
                                    multiple
                                    value={equipmentFilter}
                                    onChange={(e) =>
                                        setEquipmentFilter(e.target.value as string[])
                                    }
                                    label="Оборудование"
                                    variant="outlined"
                                >
                                    {equipmentList.map((eq) => (
                                        <MenuItem key={eq} value={eq}>
                                            {eq}
                                        </MenuItem>
                                    ))}
                                </Select>
                            </FormControl>

                            <FormControl size="small" variant="outlined" sx={{minWidth: 200}}>
                                <InputLabel>Продукты</InputLabel>
                                <Select
                                    multiple
                                    value={productFilter}
                                    onChange={(e) =>
                                        setProductFilter(e.target.value as string[])
                                    }
                                    label="Продукты"
                                    variant="outlined"
                                >
                                    {productList.map((prod) => (
                                        <MenuItem key={prod} value={prod}>
                                            {prod}
                                        </MenuItem>
                                    ))}
                                </Select>
                            </FormControl>

                            <FormControlLabel
                                control={
                                    <Checkbox
                                        checked={showSetups}
                                        onChange={(e) => setShowSetups(e.target.checked)}
                                        size="small"
                                    />
                                }
                                label={<Typography variant="body2">🧼 Замывки</Typography>}
                            />

                            <FormControlLabel
                                control={
                                    <Checkbox
                                        checked={showDowntimes}
                                        onChange={(e) => setShowDowntimes(e.target.checked)}
                                        size="small"
                                    />
                                }
                                label={<Typography variant="body2">📅 Простоев</Typography>}
                            />

                            <FormControlLabel
                                control={
                                    <Checkbox
                                        checked={showOnlyBlocked}
                                        onChange={(e) => setShowOnlyBlocked(e.target.checked)}
                                        size="small"
                                        color="error"
                                    />
                                }
                                label={
                                    <Typography
                                        variant="body2"
                                        sx={{fontWeight: showOnlyBlocked ? 600 : 400}}
                                    >
                                        🔒 Только заблокированные
                                    </Typography>
                                }
                            />

                            <FormControlLabel
                                control={
                                    <Checkbox
                                        checked={showOnlySlowCooling}
                                        onChange={(e) =>
                                            setShowOnlySlowCooling(e.target.checked)
                                        }
                                        size="small"
                                        color="warning"
                                    />
                                }
                                label={
                                    <Typography
                                        variant="body2"
                                        sx={{fontWeight: showOnlySlowCooling ? 600 : 400}}
                                    >
                                        ⏳ Только замедленное охлаждение
                                    </Typography>
                                }
                            />

                            <FormControlLabel
                                control={
                                    <Checkbox
                                        checked={showOnlyCzIncomplete}
                                        onChange={(e) =>
                                            setShowOnlyCzIncomplete(e.target.checked)
                                        }
                                        size="small"
                                        color="info"
                                    />
                                }
                                label={
                                    <Typography
                                        variant="body2"
                                        sx={{fontWeight: showOnlyCzIncomplete ? 600 : 400}}
                                    >
                                        📷 Только не промаркированные
                                    </Typography>
                                }
                            />

                            <Button
                                size="small"
                                variant="outlined"
                                color="inherit"
                                startIcon={<FilterAltOffIcon/>}
                                onClick={handleResetFilters}
                                disabled={!hasActiveFilters}
                                sx={{textTransform: 'none'}}
                            >
                                Сбросить фильтры
                            </Button>
                        </Box>
                    </Card>

                    {hasActiveFilters && filteredCount === 0 && (
                        <Alert
                            severity="info"
                            icon={<ClearIcon/>}
                            sx={{mb: 2}}
                            action={
                                <Button
                                    color="inherit"
                                    size="small"
                                    onClick={handleResetFilters}
                                >
                                    Сбросить
                                </Button>
                            }
                        >
                            По заданным фильтрам ничего не найдено. Попробуйте ослабить условия.
                        </Alert>
                    )}

                    {/* Панель навигации */}
                    <Card sx={{mb: 1, p: 1.5}}>
                        <Box
                            sx={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 1,
                                flexWrap: 'wrap',
                            }}
                        >
                            <Tooltip title="Сдвинуть влево (на пол-экрана)">
                                <IconButton
                                    size="small"
                                    onClick={handlePanLeft}
                                    color="primary"
                                >
                                    <ArrowBackIcon/>
                                </IconButton>
                            </Tooltip>
                            <Tooltip title="Сдвинуть вправо (на пол-экрана)">
                                <IconButton
                                    size="small"
                                    onClick={handlePanRight}
                                    color="primary"
                                >
                                    <ArrowForwardIcon/>
                                </IconButton>
                            </Tooltip>

                            <Divider orientation="vertical" flexItem sx={{mx: 1}}/>

                            <Tooltip title="Приблизить">
                                <IconButton size="small" onClick={handleZoomIn}>
                                    <ZoomInIcon/>
                                </IconButton>
                            </Tooltip>
                            <Tooltip title="Отдалить">
                                <IconButton size="small" onClick={handleZoomOut}>
                                    <ZoomOutIcon/>
                                </IconButton>
                            </Tooltip>

                            <Divider orientation="vertical" flexItem sx={{mx: 1}}/>

                            <ToggleButtonGroup
                                size="small"
                                exclusive
                                value={zoomPreset}
                                onChange={(_, value) => {
                                    if (value) {
                                        if (value === 'day') handleZoomDay();
                                        else if (value === 'week') handleZoomWeek();
                                        else if (value === 'month') handleZoomMonth();
                                    }
                                }}
                            >
                                <ToggleButton value="day">
                                    <Tooltip title="Масштаб: день">
                                        <CalendarViewDayIcon fontSize="small"/>
                                    </Tooltip>
                                </ToggleButton>
                                <ToggleButton value="week">
                                    <Tooltip title="Масштаб: неделя">
                                        <CalendarViewWeekIcon fontSize="small"/>
                                    </Tooltip>
                                </ToggleButton>
                                <ToggleButton value="month">
                                    <Tooltip title="Масштаб: месяц">
                                        <CalendarViewMonthIcon fontSize="small"/>
                                    </Tooltip>
                                </ToggleButton>
                            </ToggleButtonGroup>

                            <Divider orientation="vertical" flexItem sx={{mx: 1}}/>

                            <Tooltip title="Показать весь план">
                                <Button
                                    size="small"
                                    variant="outlined"
                                    startIcon={<FitScreenIcon/>}
                                    onClick={handleFitAll}
                                    sx={{textTransform: 'none'}}
                                >
                                    Весь план
                                </Button>
                            </Tooltip>
                            <Tooltip title="Перейти к сегодня">
                                <Button
                                    size="small"
                                    variant="outlined"
                                    startIcon={<TodayIcon/>}
                                    onClick={handleGoToToday}
                                    sx={{textTransform: 'none'}}
                                >
                                    Сегодня
                                </Button>
                            </Tooltip>

                            <Box sx={{ml: 'auto'}}>
                                <Typography variant="caption" color="text.secondary">
                                    💡 Масштаб и позиция сохраняются автоматически
                                </Typography>
                            </Box>
                        </Box>
                    </Card>

                    {/* Основная диаграмма */}
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
                            <Box
                                ref={containerRef}
                                className={isReadOnly ? 'gantt-readonly' : ''}
                                sx={{
                                    flexGrow: 1,
                                    width: '100%',
                                    minHeight: 0,
                                    '& .vis-item': {
                                        borderColor: 'transparent',
                                        transition: 'transform 0.2s, box-shadow 0.2s',
                                        cursor: isReadOnly ? 'default' : 'move',
                                        '&:hover': {
                                            transform: 'scaleY(1.05)',
                                            zIndex: 10,
                                            boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
                                        },
                                    },
                                    '& .item-blocked': {
                                        boxShadow: '0 0 8px rgba(231, 76, 60, 0.4)',
                                        '&:hover': {
                                            boxShadow: '0 0 12px rgba(231, 76, 60, 0.7)',
                                        },
                                    },
                                    '& .item-cooling-slow': {
                                        boxShadow: '0 0 8px rgba(230, 126, 34, 0.4)',
                                        '&:hover': {
                                            boxShadow: '0 0 12px rgba(230, 126, 34, 0.7)',
                                        },
                                    },
                                    '& .item-cz-incomplete': {
                                        boxShadow: '0 0 8px rgba(25, 118, 210, 0.4)',
                                        '&:hover': {
                                            boxShadow: '0 0 12px rgba(25, 118, 210, 0.7)',
                                        },
                                    },
                                    '& .item-setup': {
                                        opacity: 0.85,
                                        '&:hover': {opacity: 1},
                                    },
                                    '& .item-downtime': {
                                        '&:hover': {opacity: 0.9},
                                    },
                                    '& .vis-label': {
                                        fontWeight: 600,
                                        color: '#2c3e50',
                                        padding: '12px !important',
                                        borderRight: '2px solid #ecf0f1',
                                    },
                                    '& .vis-time-axis .vis-text': {
                                        color: '#7f8c8d',
                                        fontSize: '12px',
                                    },
                                    '& .vis-current-time': {
                                        backgroundColor: '#e74c3c',
                                    },
                                    '& .vis-grid.vis-vertical': {
                                        borderLeft: '1px dashed #ecf0f1',
                                    },
                                }}
                            />
                        </CardContent>
                    </Card>

                    {/* Миникарта */}
                    <Card
                        sx={{
                            mt: 1,
                            mb: 1,
                            height: 90,
                            boxShadow: '0 1px 4px rgba(0,0,0,0.08)',
                            bgcolor: '#fafbfc',
                        }}
                    >
                        <CardContent
                            sx={{
                                p: 0.5,
                                height: '100%',
                                '&:last-child': {pb: 0.5},
                            }}
                        >
                            <Box
                                ref={minimapContainerRef}
                                sx={{
                                    width: '100%',
                                    height: '100%',
                                    '& .vis-item': {
                                        borderColor: 'transparent',
                                        cursor: 'pointer',
                                    },
                                    '& .vis-label': {
                                        fontSize: '10px',
                                        fontWeight: 600,
                                        color: '#7f8c8d',
                                        padding: '2px 4px !important',
                                    },
                                    '& .vis-time-axis': {
                                        display: 'none',
                                    },
                                    '& .vis-panel.vis-bottom': {
                                        display: 'none',
                                    },
                                }}
                            />
                        </CardContent>
                    </Card>

                    <Typography
                        variant="caption"
                        color="text.secondary"
                        sx={{mt: 0.5, display: 'block', textAlign: 'center'}}
                    >
                        💡 Все операции по реактору в одной строке • Пунктир = замывки •
                        Фиолетовый фон = выходные • 🔒 = заблокировано лабораторией • ⏳ =
                        замедленное охлаждение • 📷 = ЧЗ не завершено
                        {isReadOnly
                            ? ' • Режим просмотра (редактирование недоступно)'
                            : ' • Клик по пустому месту + drag = панорамирование • Клик по задаче + drag = перемещение • Колесо = зум'}
                    </Typography>
                </>
            )}

            {/* Диалог редактирования */}
            <Dialog
                open={editDialogOpen}
                onClose={() => setEditDialogOpen(false)}
                maxWidth="sm"
                fullWidth
            >
                <DialogTitle>Редактировать задачу</DialogTitle>
                <DialogContent>
                    {selectedTask && (
                        <>
                            <Typography variant="subtitle1" gutterBottom>
                                {selectedTask.operation_name}
                            </Typography>
                            <TextField
                                margin="dense"
                                label="Начало"
                                type="datetime-local"
                                fullWidth
                                value={formatDateForInput(editFormData.start)}
                                onChange={(e) =>
                                    setEditFormData({
                                        ...editFormData,
                                        start: e.target.value,
                                    })
                                }
                                slotProps={{
                                    inputLabel: {shrink: true},
                                    htmlInput: {step: 300},
                                }}
                            />
                            <TextField
                                margin="dense"
                                label="Конец"
                                type="datetime-local"
                                fullWidth
                                value={formatDateForInput(editFormData.end)}
                                onChange={(e) =>
                                    setEditFormData({
                                        ...editFormData,
                                        end: e.target.value,
                                    })
                                }
                                slotProps={{
                                    inputLabel: {shrink: true},
                                    htmlInput: {step: 300},
                                }}
                            />
                        </>
                    )}
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setEditDialogOpen(false)}>Отмена</Button>
                    <Button onClick={handleSaveTask} variant="contained">
                        Сохранить
                    </Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
};

export default GanttPage;