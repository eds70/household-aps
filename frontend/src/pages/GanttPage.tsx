// frontend/src/pages/GanttPage.tsx
// Часть 1/2 — импорты, типы, state, логика.
// Часть 2/2 — renderTimeline + drawDependencies + JSX.
//
// Итерация 13.10: выходные — фоновые полосы (type: 'background').
//   - Убраны блоки «Выходной 1440 мин» на каждой строке.
//   - Выходные подсвечиваются вертикальными полосами на всю высоту.
//   - Верхняя полоса дат подсвечивает субботу/воскресенье фиолетовым.
//   - Связи — по hover (Итерация 13.9).

import React, {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {useNavigate} from 'react-router-dom';
import {
    Alert,
    Box,
    Button,
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
    Paper,
    Popover,
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
    AccountTree as AccountTreeIcon,
    ArrowBack as ArrowBackIcon,
    ArrowForward as ArrowForwardIcon,
    Download as DownloadIcon,
    FilterAlt as FilterAltIcon,
    FilterAltOff as FilterAltOffIcon,
    FitScreen as FitScreenIcon,
    History as HistoryIcon,
    Lock as LockIcon,
    Map as MapIcon,
    Refresh as RefreshIcon,
    Search as SearchIcon,
    Today as TodayIcon,
    ZoomIn as ZoomInIcon,
    ZoomOut as ZoomOutIcon,
} from '@mui/icons-material';

import {Timeline, type TimelineOptions} from 'vis-timeline/standalone';
import {DataSet} from 'vis-data';
import 'vis-timeline/styles/vis-timeline-graph2d.min.css';
import {ganttApi, rescheduleApi} from '../services/api';
import {API_BASE_URL} from '../config';
import {usePlan} from '../context/PlainContext';
import type {CoolingMode, CzStatus} from '../types';

// ==========================================
// Итерация 13.6: типы для связей
// ==========================================

type LinkColorKey = 'same_row' | 'to_tank' | 'to_line' | 'to_wash' | 'direct';

const LINK_COLORS: Record<LinkColorKey, string> = {
    same_row: '#7f8c8d',
    to_tank: '#e74c3c',
    to_line: '#3498db',
    to_wash: '#9b59b6',
    direct: '#27ae60',
};

const HOVER_COLOR = '#e67e22';

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

interface BackgroundItem {
    id: string;
    type: 'background';
    start: string;
    end: string;
    className?: string;
    style?: string;
    content?: string;
}

interface GanttGroup {
    id: string;
    content: string;
}

interface TaskData {
    id: string;
    batch_id: string;
    operation_name: string;
    equipment_id: string;
    product_id: string;
    start: string;
    end: string;
    duration_minutes: number;
    item_type?: 'task' | 'setup' | 'downtime';
    setup_type?: 'same_pf' | 'diff_pf';
    downtime_type?: 'WEEKEND' | 'REPAIR' | 'BREAKDOWN';
    is_lab_blocked?: boolean;
    lab_status?: string | null;
    lab_block_reason?: string | null;
    cooling_mode?: CoolingMode;
    task_role?: string | null;
    cz_status?: CzStatus | null;
    cz_marked_qty?: number | null;
    depends_on_task_ids?: string[];
}

// ==========================================
// Утилиты
// ==========================================

const getViewportStorageKey = (versionId: string | null) =>
    `aps_gantt_viewport_${versionId || 'draft'}`;

const MINIMAP_STORAGE_KEY = 'aps_gantt_minimap';
const DEPENDENCIES_STORAGE_KEY = 'aps_gantt_show_dependencies';
const ALL_DEPENDENCIES_STORAGE_KEY = 'aps_gantt_show_all_dependencies';

interface ViewportState {
    start: string;
    end: string;
}

const NON_BATCH_VALUES = new Set(['Замывка', 'Выходной']);

const GanttPage: React.FC = () => {
    const navigate = useNavigate();

    // --- Refs ---
    const containerRef = useRef<HTMLDivElement>(null);
    const minimapContainerRef = useRef<HTMLDivElement>(null);
    const svgOverlayRef = useRef<SVGSVGElement | null>(null);
    const timelineRef = useRef<Timeline | null>(null);
    const minimapRef = useRef<Timeline | null>(null);
    const handleTaskEditRef = useRef<(taskId: string) => void>(() => {});

    // --- Viewport ---
    const viewportRef = useRef<ViewportState | null>(null);
    const suppressViewportSyncRef = useRef<boolean>(false);
    const minimapSyncingRef = useRef<boolean>(false);

    // --- Redraw throttle ---
    const redrawRafRef = useRef<number | null>(null);
    const hoveredBatchIdRef = useRef<string | null>(null);
    const hoveredTaskIdRef = useRef<string | null>(null);

    // --- Plan context ---
    const {currentVersionId, currentPlanName} = usePlan();
    const isReadOnly = currentVersionId !== null;

    // --- State ---
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

    // --- UI ---
    const [showMinimap, setShowMinimap] = useState<boolean>(() => {
        return localStorage.getItem(MINIMAP_STORAGE_KEY) === '1';
    });
    const [showDependencies, setShowDependencies] = useState<boolean>(() => {
        return localStorage.getItem(DEPENDENCIES_STORAGE_KEY) !== '0';
    });
    const [showAllDependencies, setShowAllDependencies] = useState<boolean>(() => {
        return localStorage.getItem(ALL_DEPENDENCIES_STORAGE_KEY) === '1';
    });
    const [filtersAnchorEl, setFiltersAnchorEl] = useState<HTMLElement | null>(null);
    const filtersOpen = Boolean(filtersAnchorEl);
    const [hoveredBatchId, setHoveredBatchId] = useState<string | null>(null);

    // --- Фильтры ---
    const [searchQuery, setSearchQuery] = useState('');
    const [equipmentFilter, setEquipmentFilter] = useState<string[]>([]);
    const [productFilter, setProductFilter] = useState<string[]>([]);
    const [showSetups, setShowSetups] = useState(true);
    const [showDowntimes, setShowDowntimes] = useState(true);
    const [showOnlyBlocked, setShowOnlyBlocked] = useState(false);
    const [showOnlySlowCooling, setShowOnlySlowCooling] = useState(false);
    const [showOnlyCzIncomplete, setShowOnlyCzIncomplete] = useState(false);
    const [batchFilter, setBatchFilter] = useState<string | null>(null);

    const hasActiveFilters =
        searchQuery.length > 0 ||
        equipmentFilter.length > 0 ||
        productFilter.length > 0 ||
        showOnlyBlocked ||
        showOnlySlowCooling ||
        showOnlyCzIncomplete ||
        batchFilter !== null;

    // --- Диалог редактирования ---
    const [editDialogOpen, setEditDialogOpen] = useState(false);
    const [selectedTask, setSelectedTask] = useState<TaskData | null>(null);
    const [editFormData, setEditFormData] = useState({start: '', end: ''});

    const clickTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    // ==========================================
    // Итерация 13.7: список уникальных партий
    // ==========================================
    const availableBatches = useMemo(() => {
        const set = new Set<string>();
        tasks.forEach((t) => {
            if (t.batch_id && !NON_BATCH_VALUES.has(t.batch_id)) {
                set.add(t.batch_id);
            }
        });
        return Array.from(set).sort();
    }, [tasks]);

    const selectedBatchTasks = useMemo(() => {
        if (!selectedTask?.batch_id) return [];
        if (NON_BATCH_VALUES.has(selectedTask.batch_id)) return [];
        return tasks
            .filter((t) => t.batch_id === selectedTask.batch_id && (!t.item_type || t.item_type === 'task'))
            .sort((a, b) => new Date(a.start).getTime() - new Date(b.start).getTime());
    }, [tasks, selectedTask]);

    // ==========================================
    // Сохранение настроек в localStorage
    // ==========================================
    useEffect(() => {
        localStorage.setItem(MINIMAP_STORAGE_KEY, showMinimap ? '1' : '0');
    }, [showMinimap]);

    useEffect(() => {
        localStorage.setItem(DEPENDENCIES_STORAGE_KEY, showDependencies ? '1' : '0');
    }, [showDependencies]);

    useEffect(() => {
        localStorage.setItem(ALL_DEPENDENCIES_STORAGE_KEY, showAllDependencies ? '1' : '0');
    }, [showAllDependencies]);

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
    // Восстановление viewport при смене версии
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
                // ignore
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
            if (redrawRafRef.current !== null) {
                cancelAnimationFrame(redrawRafRef.current);
                redrawRafRef.current = null;
            }
        };
    }, [loadGanttData]);

    // ==========================================
    // Фильтры
    // ==========================================
    const handleResetFilters = () => {
        setSearchQuery('');
        setEquipmentFilter([]);
        setProductFilter([]);
        setShowOnlyBlocked(false);
        setShowOnlySlowCooling(false);
        setShowOnlyCzIncomplete(false);
        setBatchFilter(null);
    };

    const handleOpenAudit = () => {
        navigate('/audit?sources=RESCHEDULE,LAB,CZ');
    };

    const handleToggleFilters = (event: React.MouseEvent<HTMLElement>) => {
        setFiltersAnchorEl(event.currentTarget);
    };

    const handleCloseFilters = () => {
        setFiltersAnchorEl(null);
    };

    // ==========================================
    // generateSetups
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
            eqTasks.sort((a, b) => new Date(a.start).getTime() - new Date(b.start).getTime());
            for (let i = 0; i < eqTasks.length - 1; i++) {
                const curr = eqTasks[i];
                const next = eqTasks[i + 1];
                if (curr.batch_id === next.batch_id) continue;

                const gapMinutes = Math.round(
                    (new Date(next.start).getTime() - new Date(curr.end).getTime()) / 60000
                );
                if (gapMinutes <= 0 || gapMinutes > MAX_SETUP_GAP_MINUTES) continue;

                const setupType = curr.product_id === next.product_id ? 'same_pf' : 'diff_pf';
                const nominalDuration =
                    setupType === 'same_pf' ? SETUP_DURATION_SAME_PF : SETUP_DURATION_DIFF_PF;
                const actualDuration = Math.min(nominalDuration, gapMinutes);

                const setupEnd = new Date(next.start);
                const setupStart = new Date(setupEnd.getTime() - actualDuration * 60000);
                if (isWeekendDate(setupStart) || isWeekendDate(setupEnd)) continue;

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
    // Итерация 13.10: выходные — фоновые полосы
    // ==========================================
    // Вместо блоков «Выходной 1440 мин» на каждой строке создаём
    // один background-item на всю высоту диаграммы. vis-timeline
    // рисует его под задачами в виде вертикальной полосы.
    //
    const generateWeekendBackgrounds = (
        tasksData: TaskData[],
    ): BackgroundItem[] => {
        if (tasksData.length === 0) return [];

        const weekends: BackgroundItem[] = [];
        const startDate = new Date(Math.min(...tasksData.map((t) => new Date(t.start).getTime())));
        const endDate = new Date(Math.max(...tasksData.map((t) => new Date(t.end).getTime())));
        startDate.setHours(0, 0, 0, 0);
        endDate.setHours(23, 59, 59, 999);

        const current = new Date(startDate);
        while (current <= endDate) {
            const dayOfWeek = current.getDay();
            if (dayOfWeek === 0 || dayOfWeek === 6) {
                const weekendStart = new Date(current);
                const weekendEnd = new Date(current);
                weekendEnd.setHours(23, 59, 59, 999);

                weekends.push({
                    id: `weekend_bg_${current.toISOString().split('T')[0]}`,
                    type: 'background',
                    start: weekendStart.toISOString(),
                    end: weekendEnd.toISOString(),
                    className: 'weekend-background',
                    style: 'background-color: rgba(155, 89, 182, 0.10); border-left: 1px dashed rgba(155, 89, 182, 0.4); border-right: 1px dashed rgba(155, 89, 182, 0.4);',
                });
            }
            current.setDate(current.getDate() + 1);
        }
        return weekends;
    };

    // ==========================================
    // Редактирование задачи
    // ==========================================
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
    const zoomByFactor = useCallback((factor: number) => {
        if (!timelineRef.current) return;
        const range = timelineRef.current.getWindow();
        const center = (range.start.getTime() + range.end.getTime()) / 2;
        const half = ((range.end.getTime() - range.start.getTime()) / 2) * factor;
        timelineRef.current.setWindow(
            new Date(center - half),
            new Date(center + half),
            {animation: {duration: 300, easingFunction: 'easeInOutQuad'}}
        );
    }, []);

    const handleZoomIn = useCallback(() => zoomByFactor(0.7), [zoomByFactor]);
    const handleZoomOut = useCallback(() => zoomByFactor(1.4), [zoomByFactor]);

    const handleFitAll = useCallback(() => {
        if (!timelineRef.current) return;
        suppressViewportSyncRef.current = true;
        timelineRef.current.fit({animation: {duration: 300, easingFunction: 'easeInOutQuad'}});
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
        return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
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
    // Итерация 13.6: определение цвета провода
    // ==========================================
    const getLinkColor = useCallback(
        (fromTask: TaskData, toTask: TaskData): LinkColorKey => {
            if (toTask.task_role === 'WASH') {
                return 'to_wash';
            }
            if (
                fromTask.task_role === 'REACTOR_OP' &&
                toTask.task_role === 'TANK_TRANSFER'
            ) {
                return 'to_tank';
            }
            if (
                fromTask.task_role === 'TANK_TRANSFER' &&
                toTask.task_role === 'LINE_FILL'
            ) {
                return 'to_line';
            }
            if (
                fromTask.task_role === 'REACTOR_OP' &&
                toTask.task_role === 'LINE_FILL'
            ) {
                return 'direct';
            }
            return 'same_row';
        },
        []
    );

    // ==========================================
    // Итерация 13.9: рисование связей
    // ==========================================
    const drawDependencies = useCallback(
        (allTasks: TaskData[]) => {
            const svg = svgOverlayRef.current;
            const containerEl = containerRef.current;
            if (!svg || !containerEl) return;

            while (svg.firstChild) {
                svg.removeChild(svg.firstChild);
            }

            if (!showDependencies) {
                svg.style.display = 'none';
                return;
            }

            const hoveredId = hoveredTaskIdRef.current;
            const drawAll = showAllDependencies && !hoveredId;

            if (!hoveredId && !drawAll) {
                svg.style.display = 'none';
                return;
            }
            svg.style.display = 'block';

            const ganttContainer = containerEl.parentElement;
            if (!ganttContainer) return;

            if (svg.parentElement !== ganttContainer) {
                ganttContainer.appendChild(svg);
            }

            const containerRect = ganttContainer.getBoundingClientRect();
            if (containerRect.width === 0 || containerRect.height === 0) return;

            svg.style.position = 'absolute';
            svg.style.left = '0';
            svg.style.top = '0';
            svg.style.width = `${containerRect.width}px`;
            svg.style.height = `${containerRect.height}px`;
            svg.style.pointerEvents = 'none';
            svg.style.overflow = 'hidden';
            svg.style.zIndex = '5';

            svg.setAttribute('viewBox', `0 0 ${containerRect.width} ${containerRect.height}`);

            // ==========================================
            // Собираем bbox задач
            // ==========================================
            const boxMap = new Map<
                string,
                {left: number; right: number; top: number; bottom: number}
            >();

            const itemEls = containerEl.querySelectorAll<HTMLElement>(
                '.vis-item.vis-range'
            );

            itemEls.forEach((el) => {
                const visItem = (el as any)['vis-item'];
                if (!visItem || !visItem.id) return;

                const itemId = String(visItem.id);
                const domEl: HTMLElement = (visItem.dom && visItem.dom.box) || el;
                const rect = domEl.getBoundingClientRect();
                if (rect.width === 0 || rect.height === 0) return;

                boxMap.set(itemId, {
                    left: rect.left - containerRect.left,
                    right: rect.right - containerRect.left,
                    top: rect.top - containerRect.top,
                    bottom: rect.bottom - containerRect.top,
                });
            });

            if (boxMap.size === 0) return;

            const taskMap = new Map<string, TaskData>();
            allTasks.forEach((t) => {
                if (!t.item_type || t.item_type === 'task') {
                    taskMap.set(t.id, t);
                }
            });

            type LinkToDraw = {
                fromId: string;
                toId: string;
                color: string;
                isHighlighted: boolean;
            };
            const linksToDraw: LinkToDraw[] = [];

            const addLink = (fromTask: TaskData, toTask: TaskData, isHighlighted: boolean) => {
                const colorKey = getLinkColor(fromTask, toTask);

                if (drawAll && colorKey === 'same_row' && !showAllDependencies) {
                    return;
                }

                linksToDraw.push({
                    fromId: fromTask.id,
                    toId: toTask.id,
                    color: isHighlighted ? HOVER_COLOR : LINK_COLORS[colorKey],
                    isHighlighted,
                });
            };

            if (hoveredId) {
                const hoveredTask = taskMap.get(hoveredId);
                if (hoveredTask) {
                    (hoveredTask.depends_on_task_ids || []).forEach((fromId) => {
                        const fromTask = taskMap.get(fromId);
                        if (fromTask) {
                            addLink(fromTask, hoveredTask, true);
                        }
                    });

                    allTasks.forEach((toTask) => {
                        if (!toTask.depends_on_task_ids) return;
                        if (toTask.depends_on_task_ids.includes(hoveredTask.id)) {
                            addLink(hoveredTask, toTask, true);
                        }
                    });
                }
            } else if (drawAll) {
                allTasks.forEach((toTask) => {
                    if (!toTask.depends_on_task_ids || toTask.depends_on_task_ids.length === 0) {
                        return;
                    }
                    toTask.depends_on_task_ids.forEach((fromId) => {
                        const fromTask = taskMap.get(fromId);
                        if (fromTask) {
                            addLink(fromTask, toTask, false);
                        }
                    });
                });
            }

            linksToDraw.forEach(({fromId, toId, color, isHighlighted}) => {
                const fromBox = boxMap.get(fromId);
                const toBox = boxMap.get(toId);
                if (!fromBox || !toBox) return;

                const x1 = fromBox.right;
                const y1 = (fromBox.top + fromBox.bottom) / 2;
                const x2 = toBox.left;
                const y2 = (toBox.top + toBox.bottom) / 2;

                if (x1 === x2 && y1 === y2) return;

                let pathD: string;
                const isSameVisualRow = Math.abs(y1 - y2) < 2;

                if (isSameVisualRow) {
                    pathD = `M ${x1},${y1} H ${x2}`;
                } else {
                    const gap = x2 - x1;
                    let midX: number;
                    if (gap > 20) {
                        midX = x1 + 10;
                    } else {
                        midX = x1 + Math.max(4, gap / 2);
                    }

                    if (midX > x2 - 2) {
                        const backMidX = x2 - 10;
                        pathD = `M ${x1},${y1} H ${Math.max(x1 + 4, backMidX)} V ${y2} H ${x2}`;
                    } else {
                        pathD = `M ${x1},${y1} H ${midX} V ${y2} H ${x2}`;
                    }
                }

                const path = document.createElementNS(
                    'http://www.w3.org/2000/svg',
                    'path'
                );
                path.setAttribute('d', pathD);
                path.setAttribute(
                    'class',
                    'gantt-dependency-line' + (isHighlighted ? ' highlighted' : '')
                );
                path.setAttribute('stroke', color);
                path.setAttribute('fill', 'none');
                if (isHighlighted) {
                    path.setAttribute('stroke-width', '2.5');
                    path.setAttribute('stroke-opacity', '1');
                } else {
                    path.setAttribute('stroke-width', '1.5');
                    path.setAttribute('stroke-opacity', '0.55');
                }
                svg.appendChild(path);

                const arrowSize = isHighlighted ? 6 : 5;
                const arrow = document.createElementNS(
                    'http://www.w3.org/2000/svg',
                    'polygon'
                );
                arrow.setAttribute(
                    'points',
                    `${x2},${y2} ` +
                    `${x2 - arrowSize},${y2 - arrowSize / 1.5} ` +
                    `${x2 - arrowSize},${y2 + arrowSize / 1.5}`
                );
                arrow.setAttribute(
                    'class',
                    'gantt-dependency-arrowhead' + (isHighlighted ? ' highlighted' : '')
                );
                arrow.setAttribute('fill', color);
                arrow.setAttribute('fill-opacity', isHighlighted ? '1' : '0.55');
                svg.appendChild(arrow);
            });
        },
        [showDependencies, showAllDependencies, getLinkColor]
    );

    // ==========================================
    // Throttled redraw
    // ==========================================
    const scheduleRedraw = useCallback(() => {
        if (redrawRafRef.current !== null) {
            cancelAnimationFrame(redrawRafRef.current);
        }
        redrawRafRef.current = requestAnimationFrame(() => {
            redrawRafRef.current = null;
            if (timelineRef.current) {
                drawDependencies(tasks);
            }
        });
    }, [drawDependencies, tasks]);

    // ==========================================
    // Hover
    // ==========================================
    const handleItemOver = useCallback(
        (props: any) => {
            if (!props.item) return;
            const itemId = String(props.item);
            const task = tasks.find((t) => t.id === itemId);
            if (!task || task.item_type === 'downtime' || task.item_type === 'setup') {
                return;
            }

            hoveredTaskIdRef.current = itemId;

            if (task.batch_id && !NON_BATCH_VALUES.has(task.batch_id)) {
                if (hoveredBatchIdRef.current !== task.batch_id) {
                    hoveredBatchIdRef.current = task.batch_id;
                    setHoveredBatchId(task.batch_id);
                }
            }

            if (timelineRef.current) {
                drawDependencies(tasks);
            }
        },
        [tasks, drawDependencies]
    );

    const handleItemOut = useCallback(
        (props: any) => {
            if (!props.item) return;
            const itemId = String(props.item);
            const task = tasks.find((t) => t.id === itemId);
            if (!task) return;

            hoveredTaskIdRef.current = null;

            if (hoveredBatchIdRef.current === task.batch_id) {
                hoveredBatchIdRef.current = null;
                setHoveredBatchId(null);
            }

            if (timelineRef.current) {
                drawDependencies(tasks);
            }
        },
        [tasks, drawDependencies]
    );

    // ==========================================
    // Эффекты
    // ==========================================
    useEffect(() => {
        if (!timelineRef.current) return;
        drawDependencies(tasks);
    }, [hoveredBatchId, drawDependencies, tasks]);

    useEffect(() => {
        if (!timelineRef.current) return;
        drawDependencies(tasks);
    }, [showDependencies, drawDependencies, tasks]);

    useEffect(() => {
        if (!timelineRef.current) return;
        drawDependencies(tasks);
    }, [showAllDependencies, drawDependencies, tasks]);

    // ==========================================
    // Рендер Timeline + Minimap
    // ==========================================
    const renderTimeline = useCallback(
        (tasksData: TaskData[], equipment: string[]) => {
            if (!containerRef.current) return;

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

            // ==========================================
            // Фильтрация
            // ==========================================
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
            if (batchFilter) {
                filteredTasks = filteredTasks.filter(
                    (task) => task.batch_id === batchFilter,
                );
            }

            setFilteredCount(filteredTasks.length);

            const setups = showSetups ? generateSetups(filteredTasks) : [];
            const weekendBackgrounds = showDowntimes
                ? generateWeekendBackgrounds(filteredTasks)
                : [];

            // Обычные задачи (task, setup)
            const taskItems = [...filteredTasks, ...setups];

            if (taskItems.length === 0 && weekendBackgrounds.length === 0) {
                if (containerRef.current) containerRef.current.innerHTML = '';
                if (minimapContainerRef.current) minimapContainerRef.current.innerHTML = '';
                return;
            }

            const groupsArray: GanttGroup[] = equipment.map((eq) => ({
                id: eq,
                content: `<b>${eq}</b>`,
            }));

            const itemsArray: GanttItem[] = taskItems.map((task) => {
                const itemType = task.item_type || 'task';
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
                        let roleColor = '#95a5a6';
                        if (task.task_role === 'REACTOR_OP') roleColor = '#3498db';
                        else if (task.task_role === 'TANK_TRANSFER') roleColor = '#e67e22';
                        else if (task.task_role === 'LINE_FILL') roleColor = '#27ae60';
                        else if (task.task_role === 'WASH') roleColor = '#9b59b6';
                        style = `background-color: ${roleColor}25; border-left: 4px solid ${roleColor}; border-radius: 4px;`;
                    }

                    const blockedBadge = isBlocked
                        ? `<div style="color: #e74c3c; font-weight: bold; margin-top: 4px;">🔒 ЗАБЛОКИРОВАНО ЛАБОРАТОРИЕЙ</div>${task.lab_block_reason ? `<div style="color: #e74c3c; font-size: 11px; margin-top: 2px;">Причина: ${task.lab_block_reason}</div>` : ''}`
                        : '';

                    let coolingBadge = '';
                    if (task.cooling_mode === 'slow') {
                        coolingBadge = `<div style="color: #e67e22; font-weight: bold; margin-top: 4px;">⏳ ОХЛАЖДЕНИЕ ЗАМЕДЛЕНО (×1.3)</div>`;
                    } else if (task.cooling_mode === 'fast') {
                        coolingBadge = `<div style="color: #3498db; font-size: 11px; margin-top: 4px;">❄️ Охлаждение в обычном режиме</div>`;
                    }

                    let czBadge = '';
                    if (task.task_role === 'LINE_FILL' && task.cz_status) {
                        const czLabel =
                            task.cz_status === 'COMPLETED' ? '🟢 ЧЗ завершено' :
                                task.cz_status === 'IN_PROGRESS' ? '🔵 ЧЗ в работе' :
                                    task.cz_status === 'PENDING' ? '🟡 ЧЗ ожидает' :
                                        '⚪ ЧЗ не требуется';
                        czBadge = `<div style="margin-top: 4px; font-size: 11px;"><b>${czLabel}</b>${task.cz_marked_qty != null ? `<br>Промаркировано: ${task.cz_marked_qty}` : ''}</div>`;
                    }

                    const hoverHint = showDependencies && !showAllDependencies
                        ? `<div style="margin-top: 6px; padding-top: 6px; border-top: 1px solid #ecf0f1; color: #e67e22; font-size: 11px;">💡 Наведите — появятся связи</div>`
                        : '';

                    title = `
            <div style="padding: 8px; min-width: 280px;">
              <b style="font-size: 14px; color: ${isBlocked ? '#e74c3c' : '#2c3e50'};">${isBlocked ? '🔒 ' : ''}${isSlowCooling ? '⏳ ' : ''}${task.operation_name}</b><br>
              <hr style="margin: 8px 0; border: none; border-top: 1px solid #ecf0f1;">
              <div style="font-size: 12px; line-height: 1.6;">
                <b>Партия:</b> ${task.batch_id}<br>
                <b>Продукт:</b> ${task.product_id}<br>
                <b>Оборудование:</b> ${task.equipment_id}<br>
                <b>Роль:</b> ${task.task_role || '—'}<br>
                <b>Длительность:</b> ${task.duration_minutes} мин<br>
                <b>Начало:</b> ${new Date(task.start).toLocaleString('ru-RU')}<br>
                <b>Конец:</b> ${new Date(task.end).toLocaleString('ru-RU')}
                ${blockedBadge}
                ${coolingBadge}
                ${czBadge}
                ${hoverHint}
              </div>
            </div>
          `;
                } else if (itemType === 'setup') {
                    const setupColor = task.setup_type === 'same_pf' ? '#95a5a6' : '#e67e22';
                    style = `background-color: ${setupColor}25; border: 2px dashed ${setupColor}; border-radius: 4px;`;
                    className = 'item-setup';
                    title = `<div style="padding: 8px; min-width: 280px;"><b>🧼 Замывка</b><br>${task.duration_minutes} мин</div>`;
                } else if (itemType === 'downtime') {
                    // Оставляем для обратной совместимости (если API вернёт downtime).
                    // Но generateWeekendBackgrounds больше не создаёт такие items.
                    style = `background-color: #9b59b620; border: 1px solid #9b59b6; border-radius: 4px;`;
                    className = 'item-downtime';
                    title = `<div style="padding: 8px; min-width: 280px;"><b>📅 ${task.operation_name}</b><br>${task.duration_minutes} мин</div>`;
                }

                const blockedIcon = task.is_lab_blocked ? '🔒 ' : '';
                const slowCoolingIcon = task.cooling_mode === 'slow' ? '⏳ ' : '';
                const czIcon =
                    task.task_role === 'LINE_FILL' &&
                    task.cz_status &&
                    task.cz_status !== 'COMPLETED'
                        ? '📷 '
                        : '';

                const shortName = task.operation_name.length > 24
                    ? task.operation_name.substring(0, 22) + '…'
                    : task.operation_name;

                return {
                    id: task.id,
                    group: task.equipment_id,
                    content: `
            <div style="padding: 4px; font-size: 11px;">
              <div style="font-weight: bold; color: ${task.is_lab_blocked ? '#e74c3c' : task.cooling_mode === 'slow' ? '#e67e22' : '#2c3e50'}; margin-bottom: 2px;">
                ${blockedIcon}${slowCoolingIcon}${czIcon}${shortName}
              </div>
              <div style="font-size: 10px; color: #555;">${task.duration_minutes} мин</div>
            </div>
          `,
                    start: task.start,
                    end: task.end,
                    style: style,
                    title: title,
                    className: className,
                };
            });

            // ==========================================
            // Миникарта — без фоновых полос (для читаемости)
            // ==========================================
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

            // ==========================================
            // Итерация 13.10: объединяем задачи и фоновые полосы выходных
            // в один DataSet. vis-timeline сам различает их по type.
            // ==========================================
            const allVisItems: any[] = [
                ...itemsArray,
                ...weekendBackgrounds,
            ];

            const items = new DataSet<any>(allVisItems);
            const minimapGroups = new DataSet<GanttGroup>(minimapGroupsArray);
            const minimapItems = new DataSet<GanttItem>(minimapItemsArray);

            const options: TimelineOptions = {
                groupOrder: 'content',
                moveable: true,
                zoomable: true,
                editable: {
                    add: false,
                    updateTime: !isReadOnly,
                    updateGroup: false,
                    remove: false,
                },
                selectable: true,
                multiselect: false,
                margin: {item: 2, axis: 5},
                orientation: 'top',
                stack: false,
                showCurrentTime: true,
                zoomMin: 1000 * 60 * 60 * 2,
                zoomMax: 1000 * 60 * 60 * 24 * 90,
                format: {
                    minorLabels: {
                        millisecond: 'SSS',
                        second: 'ss',
                        minute: 'HH:mm',
                        hour: 'HH:mm',
                        weekday: 'ddd D MMM',
                        day: 'D MMM',
                        week: 'w',
                        month: 'MMMM',
                        year: 'YYYY',
                    },
                    majorLabels: {
                        millisecond: 'HH:mm:ss',
                        second: 'D MMMM HH:mm',
                        minute: 'ddd D MMMM',
                        hour: 'ddd D MMMM',
                        weekday: 'MMMM YYYY',
                        day: 'MMMM YYYY',
                        week: 'MMMM YYYY',
                        month: 'YYYY',
                        year: '',
                    },
                },
                locale: 'ru',
                tooltip: {
                    followMouse: true,
                    overflowMethod: 'cap',
                    delay: 100,
                },
                snap: (date: Date) => {
                    const ms = 1000 * 60 * 15;
                    return new Date(Math.round(date.getTime() / ms) * ms);
                },
                verticalScroll: true,
                onMove: async (item: any, callback: (item: any) => void) => {
                    const itemId = String(item?.id ?? '');
                    if (itemId.startsWith('setup_') || itemId.startsWith('weekend_')) {
                        const original = tasks.find((t) => t.id === item.id);
                        callback(original ? {...item, start: original.start, end: original.end} : item);
                        return;
                    }
                    if (isReadOnly) {
                        const original = tasks.find((t) => t.id === item.id);
                        callback(original ? {...item, start: original.start, end: original.end} : item);
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
                            prev.map((t) => t.id === item.id ? {...t, start: newStart, end: newEnd} : t)
                        );
                        callback(item);
                    } catch (err: any) {
                        const detail = err.response?.data?.detail;
                        setError(typeof detail === 'string' ? detail : 'Ошибка перемещения задачи');
                        callback({...item, start: task.start, end: task.end});
                    }
                },
            };

            const newTimeline = new Timeline(
                containerRef.current,
                items as any,
                groups as any,
                options
            );
            timelineRef.current = newTimeline;

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

            // ==========================================
            // Обработчики событий
            // ==========================================
            newTimeline.on('rangechange', () => {
                persistCurrentViewport();

                if (showAllDependencies && !hoveredTaskIdRef.current) {
                    scheduleRedraw();
                }
            });

            newTimeline.on('rangechanged', () => {
                if (showAllDependencies && !hoveredTaskIdRef.current) {
                    drawDependencies(tasksData);
                }
            });

            newTimeline.on('changed', () => {
                scheduleRedraw();
            });

            newTimeline.on('itemover', handleItemOver);
            newTimeline.on('itemout', handleItemOut);

            newTimeline.on('click', (props: any) => {
                if (!props.item) return;
                const itemId = String(props.item);
                const task = tasks.find((t) => t.id === itemId);

                // Игнорируем клики по background-полосам выходных
                if (!task) return;

                if (clickTimeoutRef.current) {
                    clearTimeout(clickTimeoutRef.current);
                    clickTimeoutRef.current = null;

                    if (task && task.batch_id && !NON_BATCH_VALUES.has(task.batch_id)) {
                        setBatchFilter(task.batch_id);
                    } else {
                        handleTaskEditRef.current(props.item);
                    }
                } else {
                    clickTimeoutRef.current = setTimeout(() => {
                        clickTimeoutRef.current = null;
                        handleTaskEditRef.current(props.item);
                    }, 300);
                }
            });

            // ==========================================
            // Первичная отрисовка связей
            // ==========================================
            const tryDrawDeps = (attempt: number) => {
                if (!timelineRef.current) return;
                const containerEl = containerRef.current;
                if (!containerEl) return;

                const renderedCount = containerEl.querySelectorAll(
                    '.vis-item.vis-range'
                ).length;

                if (renderedCount > 0) {
                    drawDependencies(tasksData);
                } else if (attempt < 30) {
                    setTimeout(() => tryDrawDeps(attempt + 1), 100);
                }
            };

            requestAnimationFrame(() => {
                tryDrawDeps(1);
            });

            // ==========================================
            // Миникарта
            // ==========================================
            if (!showMinimap || !minimapContainerRef.current) return;

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
                    timelineRef.current.setWindow(range.start, range.end, {animation: false});
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
                    minimapRef.current.setWindow(range.start, range.end, {animation: false});
                } finally {
                    setTimeout(() => {
                        minimapSyncingRef.current = false;
                    }, 50);
                }
            };

            try {
                const mainRange = newTimeline.getWindow();
                newMinimap.setWindow(mainRange.start, mainRange.end, {animation: false});
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
            batchFilter,
            showSetups,
            showDowntimes,
            showOnlyBlocked,
            showOnlySlowCooling,
            showOnlyCzIncomplete,
            showMinimap,
            showAllDependencies,
            showDependencies,
            isReadOnly,
            tasks,
            setError,
            persistCurrentViewport,
            saveViewportToStorage,
            drawDependencies,
            scheduleRedraw,
            handleItemOver,
            handleItemOut,
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

    // ==========================================
    // JSX
    // ==========================================
    return (
        <Box sx={{height: '100%', display: 'flex', flexDirection: 'column', minHeight: 0}}>
            <Paper
                elevation={1}
                sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1,
                    px: 1.5,
                    py: 0.75,
                    mb: 1,
                    flexShrink: 0,
                    flexWrap: 'wrap',
                }}
            >
                <Typography
                    variant="h6"
                    sx={{fontWeight: 600, fontSize: '1.1rem', mr: 1, whiteSpace: 'nowrap'}}
                >
                    📊 Диаграмма Ганта
                </Typography>

                <Tooltip title={hasActiveFilters ? `Показано: ${filteredCount} из ${stats.totalTasks}` : 'Всего задач'}>
                    <Chip
                        label={hasActiveFilters ? `${filteredCount}/${stats.totalTasks}` : `${stats.totalTasks}`}
                        size="small"
                        color={hasActiveFilters ? 'warning' : 'primary'}
                        variant="outlined"
                    />
                </Tooltip>
                <Tooltip title="Makespan (часы)">
                    <Chip label={`${stats.makespanHours.toFixed(1)} ч`} size="small" variant="outlined"/>
                </Tooltip>
                <Tooltip title="Количество единиц оборудования">
                    <Chip label={`${stats.equipmentCount} об.`} size="small" variant="outlined"/>
                </Tooltip>

                {isReadOnly && (
                    <Tooltip title={`Режим просмотра: ${currentPlanName}`}>
                        <Chip icon={<LockIcon fontSize="small"/>} label="Просмотр" size="small" color="info" variant="filled"/>
                    </Tooltip>
                )}

                <TextField
                    size="small"
                    placeholder="Поиск..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    sx={{width: 200, ml: 'auto'}}
                    slotProps={{
                        input: {
                            startAdornment: (
                                <InputAdornment position="start">
                                    <SearchIcon fontSize="small"/>
                                </InputAdornment>
                            ),
                        },
                    }}
                />

                <Tooltip title="Фильтры">
                    <IconButton
                        size="small"
                        onClick={handleToggleFilters}
                        color={hasActiveFilters ? 'warning' : 'default'}
                    >
                        <FilterAltIcon/>
                    </IconButton>
                </Tooltip>

                <Paper
                    variant="outlined"
                    sx={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 0.25,
                        px: 0.5,
                        py: 0.25,
                        borderColor: '#bdc3c7',
                    }}
                >
                    <Tooltip title="Сдвинуть влево"><IconButton size="small" onClick={handlePanLeft}><ArrowBackIcon fontSize="small"/></IconButton></Tooltip>
                    <Tooltip title="Сдвинуть вправо"><IconButton size="small" onClick={handlePanRight}><ArrowForwardIcon fontSize="small"/></IconButton></Tooltip>
                    <Divider orientation="vertical" flexItem sx={{mx: 0.25}}/>
                    <Tooltip title="Приблизить"><IconButton size="small" onClick={handleZoomIn}><ZoomInIcon fontSize="small"/></IconButton></Tooltip>
                    <Tooltip title="Отдалить"><IconButton size="small" onClick={handleZoomOut}><ZoomOutIcon fontSize="small"/></IconButton></Tooltip>
                    <Divider orientation="vertical" flexItem sx={{mx: 0.25}}/>
                    <Tooltip title="Показать весь план"><IconButton size="small" onClick={handleFitAll}><FitScreenIcon fontSize="small"/></IconButton></Tooltip>
                    <Tooltip title="Перейти к сегодня"><IconButton size="small" onClick={handleGoToToday}><TodayIcon fontSize="small"/></IconButton></Tooltip>
                </Paper>

                <Tooltip title={showMinimap ? 'Скрыть навигатор timeline' : 'Показать навигатор timeline'}>
                    <IconButton
                        size="small"
                        onClick={() => setShowMinimap((v) => !v)}
                        color={showMinimap ? 'primary' : 'default'}
                    >
                        <MapIcon/>
                    </IconButton>
                </Tooltip>

                <Tooltip
                    title={
                        showDependencies
                            ? (showAllDependencies
                                ? 'Скрыть связи между задачами'
                                : 'Связи показываются при наведении на задачу')
                            : 'Показать связи между задачами'
                    }
                >
                    <IconButton
                        size="small"
                        onClick={() => setShowDependencies((v) => !v)}
                        color={showDependencies ? 'primary' : 'default'}
                    >
                        <AccountTreeIcon/>
                    </IconButton>
                </Tooltip>

                {showDependencies && (
                    <Tooltip title={showAllDependencies ? 'Переключить в режим "по наведению"' : 'Показать все связи (с задержкой при pan)'}>
                        <Chip
                            size="small"
                            label={showAllDependencies ? '🔗 Все' : '📎 По hover'}
                            color={showAllDependencies ? 'secondary' : 'default'}
                            variant={showAllDependencies ? 'filled' : 'outlined'}
                            onClick={() => setShowAllDependencies((v) => !v)}
                            sx={{cursor: 'pointer', fontSize: '0.7rem'}}
                        />
                    </Tooltip>
                )}

                {showDependencies && !showAllDependencies && (
                    <Tooltip title="Наведите курсор на любую задачу — увидите её связи">
                        <Chip
                            size="small"
                            label="💡 Наведите на задачу"
                            variant="outlined"
                            sx={{
                                fontSize: '0.7rem',
                                color: '#e67e22',
                                borderColor: '#e67e22',
                                cursor: 'help',
                            }}
                        />
                    </Tooltip>
                )}

                <Divider orientation="vertical" flexItem sx={{mx: 0.25}}/>

                <Tooltip title="История изменений"><IconButton size="small" onClick={handleOpenAudit}><HistoryIcon/></IconButton></Tooltip>
                <Tooltip title="Обновить"><IconButton size="small" onClick={() => void loadGanttData()}><RefreshIcon/></IconButton></Tooltip>
                <Tooltip title="Экспорт в Excel"><IconButton size="small" color="success" onClick={handleExport}><DownloadIcon/></IconButton></Tooltip>
            </Paper>

            {error && (
                <Alert severity="warning" sx={{mb: 1, flexShrink: 0}}>
                    {error}
                </Alert>
            )}

            {hasActiveFilters && (
                <Paper
                    elevation={0}
                    sx={{
                        display: 'flex',
                        gap: 0.5,
                        mb: 1,
                        p: 0.5,
                        flexShrink: 0,
                        flexWrap: 'wrap',
                        bgcolor: '#fff8e1',
                    }}
                >
                    <Typography variant="caption" sx={{alignSelf: 'center', mr: 1, fontWeight: 600}}>
                        Фильтры:
                    </Typography>
                    {batchFilter && (
                        <Chip
                            label={`📌 Партия: ${batchFilter.substring(0, 8)}`}
                            size="small"
                            color="secondary"
                            onDelete={() => setBatchFilter(null)}
                        />
                    )}
                    {equipmentFilter.length > 0 && (
                        <Chip label={`Оборуд.: ${equipmentFilter.join(', ')}`} size="small" onDelete={() => setEquipmentFilter([])}/>
                    )}
                    {productFilter.length > 0 && (
                        <Chip label={`Продукты: ${productFilter.join(', ')}`} size="small" onDelete={() => setProductFilter([])}/>
                    )}
                    {showOnlyBlocked && <Chip label="🔒 Только заблокированные" size="small" color="error" onDelete={() => setShowOnlyBlocked(false)}/>}
                    {showOnlySlowCooling && <Chip label="⏳ Только замедленное охлаждение" size="small" color="warning" onDelete={() => setShowOnlySlowCooling(false)}/>}
                    {showOnlyCzIncomplete && <Chip label="📷 Только не промаркированные" size="small" color="info" onDelete={() => setShowOnlyCzIncomplete(false)}/>}
                    <Button size="small" onClick={handleResetFilters} startIcon={<FilterAltOffIcon/>}>
                        Сбросить
                    </Button>
                </Paper>
            )}

            <Box
                className="gantt-container"
                sx={{
                    flexGrow: 1,
                    minHeight: 0,
                    position: 'relative',
                    border: '1px solid #e0e0e0',
                    borderRadius: 1,
                    overflow: 'hidden',
                    bgcolor: 'white',
                    '& .vis-item.vis-range:not(.item-downtime):not(.item-setup)': showDependencies && !showAllDependencies
                        ? {cursor: 'help'}
                        : {},
                }}
            >
                <Box
                    ref={containerRef}
                    className={isReadOnly ? 'gantt-readonly' : ''}
                    sx={{
                        width: '100%',
                        height: '100%',
                        '& .vis-timeline': {border: 'none'},
                        '& .vis-item': {
                            borderColor: 'transparent',
                            transition: 'box-shadow 0.15s',
                        },
                        '& .item-blocked': {boxShadow: '0 0 8px rgba(231, 76, 60, 0.4)'},
                        '& .item-cooling-slow': {boxShadow: '0 0 8px rgba(230, 126, 34, 0.4)'},
                        '& .item-cz-incomplete': {boxShadow: '0 0 8px rgba(25, 118, 210, 0.4)'},
                        '& .vis-item.chain-highlighted': {
                            zIndex: 20,
                            boxShadow: '0 0 0 2px #e67e22, 0 4px 12px rgba(230, 126, 34, 0.4)',
                        },
                        '& .vis-item.vis-range:hover': {
                            boxShadow: '0 0 0 2px #e67e22',
                        },
                    }}
                />

                <svg
                    ref={svgOverlayRef}
                    className="gantt-dependencies-svg"
                    xmlns="http://www.w3.org/2000/svg"
                    style={{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        width: '100%',
                        height: '100%',
                        pointerEvents: 'none',
                        zIndex: 5,
                        overflow: 'hidden',
                    }}
                />
            </Box>

            {showMinimap && (
                <Paper
                    variant="outlined"
                    sx={{mt: 0.5, height: 80, flexShrink: 0, overflow: 'hidden'}}
                >
                    <Box
                        ref={minimapContainerRef}
                        sx={{
                            width: '100%',
                            height: '100%',
                            '& .vis-item': {borderColor: 'transparent', cursor: 'pointer'},
                            '& .vis-label': {fontSize: '10px', color: '#7f8c8d', padding: '2px 4px !important'},
                            '& .vis-time-axis': {display: 'none'},
                            '& .vis-panel.vis-bottom': {display: 'none'},
                        }}
                    />
                </Paper>
            )}

            <Popover
                open={filtersOpen}
                anchorEl={filtersAnchorEl}
                onClose={handleCloseFilters}
                anchorOrigin={{vertical: 'bottom', horizontal: 'right'}}
                transformOrigin={{vertical: 'top', horizontal: 'right'}}
            >
                <Box sx={{p: 2, minWidth: 340, maxHeight: '80vh', overflow: 'auto', display: 'flex', flexDirection: 'column', gap: 2}}>
                    <Typography variant="subtitle2" sx={{fontWeight: 600}}>🎛 Фильтры</Typography>

                    <FormControl size="small" variant="outlined" fullWidth>
                        <InputLabel>Оборудование</InputLabel>
                        <Select
                            multiple
                            value={equipmentFilter}
                            onChange={(e) => setEquipmentFilter(typeof e.target.value === 'string' ? e.target.value.split(',') : e.target.value)}
                            label="Оборудование"
                            variant="outlined"
                        >
                            {equipmentList.map((eq) => <MenuItem key={eq} value={eq}>{eq}</MenuItem>)}
                        </Select>
                    </FormControl>

                    <FormControl size="small" variant="outlined" fullWidth>
                        <InputLabel>Продукты</InputLabel>
                        <Select
                            multiple
                            value={productFilter}
                            onChange={(e) => setProductFilter(typeof e.target.value === 'string' ? e.target.value.split(',') : e.target.value)}
                            label="Продукты"
                            variant="outlined"
                        >
                            {productList.map((prod) => <MenuItem key={prod} value={prod}>{prod}</MenuItem>)}
                        </Select>
                    </FormControl>

                    <FormControl size="small" variant="outlined" fullWidth>
                        <InputLabel>Партия</InputLabel>
                        <Select
                            value={batchFilter || ''}
                            label="Партия"
                            variant="outlined"
                            onChange={(e) => setBatchFilter(e.target.value || null)}
                        >
                            <MenuItem value="">— Все партии —</MenuItem>
                            {availableBatches.map((bid) => (
                                <MenuItem key={bid} value={bid}>
                                    Партия {bid.substring(0, 8)}
                                </MenuItem>
                            ))}
                        </Select>
                    </FormControl>

                    <Divider/>
                    <Typography variant="caption" color="text.secondary">Отображение:</Typography>

                    <FormControlLabel control={<Checkbox checked={showSetups} onChange={(e) => setShowSetups(e.target.checked)} size="small"/>} label={<Typography variant="body2">🧼 Замывки</Typography>}/>
                    <FormControlLabel control={<Checkbox checked={showDowntimes} onChange={(e) => setShowDowntimes(e.target.checked)} size="small"/>} label={<Typography variant="body2">📅 Выходные (фон)</Typography>}/>

                    {showDependencies && (
                        <FormControlLabel
                            control={
                                <Checkbox
                                    checked={showAllDependencies}
                                    onChange={(e) => setShowAllDependencies(e.target.checked)}
                                    size="small"
                                    color="secondary"
                                />
                            }
                            label={
                                <Typography variant="body2">
                                    🔗 Показывать все связи постоянно
                                </Typography>
                            }
                        />
                    )}

                    <Divider/>
                    <Typography variant="caption" color="text.secondary">Только проблемные:</Typography>

                    <FormControlLabel control={<Checkbox checked={showOnlyBlocked} onChange={(e) => setShowOnlyBlocked(e.target.checked)} size="small" color="error"/>} label={<Typography variant="body2">🔒 Только заблокированные</Typography>}/>
                    <FormControlLabel control={<Checkbox checked={showOnlySlowCooling} onChange={(e) => setShowOnlySlowCooling(e.target.checked)} size="small" color="warning"/>} label={<Typography variant="body2">⏳ Только замедленное охлаждение</Typography>}/>
                    <FormControlLabel control={<Checkbox checked={showOnlyCzIncomplete} onChange={(e) => setShowOnlyCzIncomplete(e.target.checked)} size="small" color="info"/>} label={<Typography variant="body2">📷 Только не промаркированные</Typography>}/>

                    <Divider/>

                    <Button variant="outlined" size="small" startIcon={<FilterAltOffIcon/>} onClick={handleResetFilters} disabled={!hasActiveFilters}>
                        Сбросить все фильтры
                    </Button>
                </Box>
            </Popover>

            {/* ==========================================
    Расширенный диалог задачи с информацией о партии.
    Итерация 13.11:
      - Перемещаемый (drag за заголовок)
      - Скроллируемый
      - Блок «Редактирование времени» — первым
    ========================================== */}
            {/* ==========================================
    Расширенный диалог задачи с информацией о партии.
    Итерация 13.12:
      - Перемещаемый (drag за заголовок)
      - Resizable (drag за правый нижний угол)
      - Скроллируемый
      - Блок «Редактирование времени» — первым
    ========================================== */}
            <Dialog
                open={editDialogOpen}
                onClose={(_event, reason) => {
                    // Итерация 13.12: запрещаем закрытие по клику вне диалога.
                    // Esc по-прежнему закрывает.
                    if (reason === 'backdropClick') {
                        return;
                    }
                    setEditDialogOpen(false);
                }}
                maxWidth={false}
                fullWidth={false}
                slotProps={{
                    root: {
                        sx: {
                            '& .MuiDialog-container': {
                                alignItems: 'flex-start',
                                justifyContent: 'flex-start',
                                padding: 0,
                            },
                        },
                    },
                    paper: {
                        sx: {
                            width: 700,
                            height: 'auto',
                            maxHeight: '90vh',
                            minWidth: 480,
                            minHeight: 320,
                            display: 'flex',
                            flexDirection: 'column',
                            position: 'relative',
                            overflow: 'hidden',
                        },
                    },
                }}
            >
                {/* ==========================================
        Ручка-ресайзер в правом нижнем углу
        ========================================== */}
                <Box
                    onMouseDown={(e) => {
                        e.stopPropagation();
                        e.preventDefault();

                        const dialogEl = (e.currentTarget as HTMLElement).closest(
                            '.MuiDialog-paper'
                        ) as HTMLElement | null;
                        if (!dialogEl) return;

                        const rect = dialogEl.getBoundingClientRect();
                        const startX = e.clientX;
                        const startY = e.clientY;
                        const startWidth = rect.width;
                        const startHeight = rect.height;

                        const onMouseMove = (ev: MouseEvent) => {
                            const dx = ev.clientX - startX;
                            const dy = ev.clientY - startY;

                            const newWidth = Math.max(480, startWidth + dx);
                            const newHeight = Math.max(320, startHeight + dy);

                            // Ограничения по экрану
                            const maxW = window.innerWidth * 0.95;
                            const maxH = window.innerHeight * 0.9;

                            dialogEl.style.width = `${Math.min(newWidth, maxW)}px`;
                            dialogEl.style.height = `${Math.min(newHeight, maxH)}px`;
                            dialogEl.style.maxHeight = `${maxH}px`;
                        };

                        const onMouseUp = () => {
                            document.removeEventListener('mousemove', onMouseMove);
                            document.removeEventListener('mouseup', onMouseUp);
                        };

                        document.addEventListener('mousemove', onMouseMove);
                        document.addEventListener('mouseup', onMouseUp);
                    }}
                    sx={{
                        position: 'absolute',
                        right: 0,
                        bottom: 0,
                        width: 20,
                        height: 20,
                        cursor: 'nwse-resize',
                        zIndex: 10,
                        // Визуальная ручка (уголок)
                        '&::before': {
                            content: '""',
                            position: 'absolute',
                            right: 3,
                            bottom: 3,
                            width: 12,
                            height: 12,
                            borderRight: '2px solid #bdc3c7',
                            borderBottom: '2px solid #bdc3c7',
                            transition: 'border-color 0.15s',
                        },
                        '&:hover::before': {
                            borderRightColor: '#3498db',
                            borderBottomColor: '#3498db',
                        },
                        // Слегка увеличим область захвата
                        '&::after': {
                            content: '""',
                            position: 'absolute',
                            right: 0,
                            bottom: 0,
                            width: 20,
                            height: 20,
                        },
                    }}
                />

                <DialogTitle
                    sx={{
                        fontWeight: 600,
                        display: 'flex',
                        alignItems: 'center',
                        gap: 1,
                        cursor: 'move',
                        userSelect: 'none',
                        flexShrink: 0,
                        '&:active': {cursor: 'grabbing'},
                        borderBottom: '1px solid #e0e0e0',
                    }}
                    onMouseDown={(e) => {
                        // Игнорируем клики по кнопкам/chip'ам в заголовке
                        const target = e.target as HTMLElement;
                        if (
                            target.closest('button') ||
                            target.closest('.MuiChip-root') ||
                            target.closest('.MuiIconButton-root')
                        ) {
                            return;
                        }

                        const dialogEl = (e.currentTarget as HTMLElement).closest(
                            '.MuiDialog-paper'
                        ) as HTMLElement | null;
                        if (!dialogEl) return;

                        const rect = dialogEl.getBoundingClientRect();
                        const startX = e.clientX;
                        const startY = e.clientY;
                        const startLeft = rect.left;
                        const startTop = rect.top;

                        // Фиксируем диалог в текущей позиции
                        dialogEl.style.margin = '0';
                        dialogEl.style.position = 'fixed';
                        dialogEl.style.left = `${startLeft}px`;
                        dialogEl.style.top = `${startTop}px`;
                        dialogEl.style.right = 'auto';
                        dialogEl.style.bottom = 'auto';

                        const onMouseMove = (ev: MouseEvent) => {
                            const dx = ev.clientX - startX;
                            const dy = ev.clientY - startY;
                            dialogEl.style.left = `${startLeft + dx}px`;
                            dialogEl.style.top = `${startTop + dy}px`;
                        };

                        const onMouseUp = () => {
                            document.removeEventListener('mousemove', onMouseMove);
                            document.removeEventListener('mouseup', onMouseUp);
                        };

                        document.addEventListener('mousemove', onMouseMove);
                        document.addEventListener('mouseup', onMouseUp);
                    }}
                >
                    {selectedTask?.operation_name || 'Задача'}
                    {selectedTask?.batch_id && !NON_BATCH_VALUES.has(selectedTask.batch_id) && (
                        <Chip
                            size="small"
                            label={`📌 ${selectedTask.batch_id.substring(0, 8)}`}
                            color="secondary"
                            variant="outlined"
                        />
                    )}
                    <Typography
                        variant="caption"
                        sx={{ml: 'auto', color: 'text.secondary', fontSize: '0.7rem'}}
                    >
                        🖱 Перетащите заголовок / угол
                    </Typography>
                </DialogTitle>

                <DialogContent
                    dividers
                    sx={{
                        flexGrow: 1,
                        minHeight: 0,
                        overflowY: 'auto',
                        pt: 2,
                    }}
                >
                    {selectedTask && (
                        <Box sx={{display: 'flex', flexDirection: 'column', gap: 2}}>
                            {/* ==========================================
                    Блок 1: Редактирование времени (первый)
                    ========================================== */}
                            {!isReadOnly && (
                                <Box>
                                    <Typography variant="subtitle2" sx={{fontWeight: 700, mb: 1, color: '#2c3e50'}}>
                                        ⏱ Редактирование времени
                                    </Typography>
                                    <Box sx={{display: 'flex', flexDirection: 'column', gap: 2}}>
                                        <TextField
                                            margin="dense"
                                            label="Начало"
                                            type="datetime-local"
                                            fullWidth
                                            value={formatDateForInput(editFormData.start)}
                                            onChange={(e) => setEditFormData({...editFormData, start: e.target.value})}
                                            slotProps={{inputLabel: {shrink: true}, htmlInput: {step: 300}}}
                                        />
                                        <TextField
                                            margin="dense"
                                            label="Конец"
                                            type="datetime-local"
                                            fullWidth
                                            value={formatDateForInput(editFormData.end)}
                                            onChange={(e) => setEditFormData({...editFormData, end: e.target.value})}
                                            slotProps={{inputLabel: {shrink: true}, htmlInput: {step: 300}}}
                                        />
                                    </Box>
                                </Box>
                            )}

                            {isReadOnly && (
                                <Alert severity="info">
                                    Режим просмотра: редактирование недоступно.
                                </Alert>
                            )}

                            {/* ==========================================
                    Блок 2: Карточка партии
                    ========================================== */}
                            {selectedTask.batch_id && !NON_BATCH_VALUES.has(selectedTask.batch_id) ? (
                                <Box
                                    sx={{
                                        bgcolor: '#f8f9fa',
                                        border: '1px solid #e0e0e0',
                                        borderRadius: 1,
                                        p: 1.5,
                                    }}
                                >
                                    <Typography variant="subtitle2" sx={{fontWeight: 700, mb: 1, color: '#2c3e50'}}>
                                        📦 Информация о партии
                                    </Typography>
                                    <Box
                                        sx={{
                                            display: 'grid',
                                            gridTemplateColumns: {xs: '1fr', sm: '1fr 1fr'},
                                            gap: 1,
                                        }}
                                    >
                                        <Box>
                                            <Typography variant="caption" color="text.secondary">Партия</Typography>
                                            <Typography variant="body2" sx={{fontFamily: 'monospace', fontSize: '0.8rem'}}>
                                                {selectedTask.batch_id}
                                            </Typography>
                                        </Box>
                                        <Box>
                                            <Typography variant="caption" color="text.secondary">Продукт</Typography>
                                            <Typography variant="body2" sx={{fontWeight: 600}}>
                                                {selectedTask.product_id}
                                            </Typography>
                                        </Box>
                                        <Box>
                                            <Typography variant="caption" color="text.secondary">Роль задачи</Typography>
                                            <Typography variant="body2">
                                                {selectedTask.task_role || '—'}
                                            </Typography>
                                        </Box>
                                        <Box>
                                            <Typography variant="caption" color="text.secondary">Оборудование</Typography>
                                            <Typography variant="body2">
                                                {selectedTask.equipment_id}
                                            </Typography>
                                        </Box>
                                        <Box>
                                            <Typography variant="caption" color="text.secondary">Лаборатория</Typography>
                                            <Box sx={{mt: 0.25}}>
                                                <Chip
                                                    size="small"
                                                    label={
                                                        selectedTask.is_lab_blocked
                                                            ? '🔒 Заблокировано'
                                                            : selectedTask.lab_status === 'APPROVED'
                                                                ? '✅ Одобрено'
                                                                : selectedTask.lab_status === 'PENDING_LAB'
                                                                    ? '🧪 Ожидает лабу'
                                                                    : '— Не требуется'
                                                    }
                                                    color={
                                                        selectedTask.is_lab_blocked
                                                            ? 'error'
                                                            : selectedTask.lab_status === 'APPROVED'
                                                                ? 'success'
                                                                : selectedTask.lab_status === 'PENDING_LAB'
                                                                    ? 'info'
                                                                    : 'default'
                                                    }
                                                    variant={selectedTask.is_lab_blocked ? 'filled' : 'outlined'}
                                                />
                                            </Box>
                                            {selectedTask.lab_block_reason && (
                                                <Typography
                                                    variant="caption"
                                                    sx={{color: 'error.main', display: 'block', mt: 0.5}}
                                                >
                                                    Причина: {selectedTask.lab_block_reason}
                                                </Typography>
                                            )}
                                        </Box>
                                        <Box>
                                            <Typography variant="caption" color="text.secondary">Честный Знак</Typography>
                                            <Box sx={{mt: 0.25}}>
                                                {selectedTask.task_role === 'LINE_FILL' ? (
                                                    <Box>
                                                        <Chip
                                                            size="small"
                                                            label={
                                                                selectedTask.cz_status === 'COMPLETED'
                                                                    ? '🟢 Завершено'
                                                                    : selectedTask.cz_status === 'IN_PROGRESS'
                                                                        ? '🔵 В работе'
                                                                        : selectedTask.cz_status === 'PENDING'
                                                                            ? '🟡 Ожидает'
                                                                            : '⚪ Не требуется'
                                                            }
                                                            color={
                                                                selectedTask.cz_status === 'COMPLETED'
                                                                    ? 'success'
                                                                    : selectedTask.cz_status === 'IN_PROGRESS'
                                                                        ? 'info'
                                                                        : selectedTask.cz_status === 'PENDING'
                                                                            ? 'warning'
                                                                            : 'default'
                                                            }
                                                            variant="outlined"
                                                        />
                                                        {selectedTask.cz_marked_qty != null && (
                                                            <Typography variant="caption" sx={{display: 'block', mt: 0.5}}>
                                                                Промаркировано: {selectedTask.cz_marked_qty}
                                                            </Typography>
                                                        )}
                                                    </Box>
                                                ) : (
                                                    <Typography variant="body2">—</Typography>
                                                )}
                                            </Box>
                                        </Box>
                                        <Box>
                                            <Typography variant="caption" color="text.secondary">Режим охлаждения</Typography>
                                            <Typography variant="body2">
                                                {selectedTask.cooling_mode === 'slow'
                                                    ? '⏳ Замедлено (×1.3)'
                                                    : selectedTask.cooling_mode === 'fast'
                                                        ? '❄️ Обычное'
                                                        : '—'}
                                            </Typography>
                                        </Box>
                                        <Box>
                                            <Typography variant="caption" color="text.secondary">Длительность</Typography>
                                            <Typography variant="body2">
                                                {selectedTask.duration_minutes} мин
                                            </Typography>
                                        </Box>
                                        <Box>
                                            <Typography variant="caption" color="text.secondary">Начало / Конец</Typography>
                                            <Typography variant="body2" sx={{fontSize: '0.8rem'}}>
                                                {new Date(selectedTask.start).toLocaleString('ru-RU')}
                                                <br/>
                                                {new Date(selectedTask.end).toLocaleString('ru-RU')}
                                            </Typography>
                                        </Box>
                                    </Box>

                                    {selectedTask.depends_on_task_ids && selectedTask.depends_on_task_ids.length > 0 && (
                                        <Box sx={{mt: 1.5}}>
                                            <Typography variant="caption" color="text.secondary">
                                                Зависит от задач: {selectedTask.depends_on_task_ids.length}
                                            </Typography>
                                            <Box sx={{display: 'flex', gap: 0.5, flexWrap: 'wrap', mt: 0.5}}>
                                                {selectedTask.depends_on_task_ids.slice(0, 5).map((id) => (
                                                    <Chip
                                                        key={id}
                                                        size="small"
                                                        label={id.substring(0, 8)}
                                                        variant="outlined"
                                                    />
                                                ))}
                                                {selectedTask.depends_on_task_ids.length > 5 && (
                                                    <Chip
                                                        size="small"
                                                        label={`+${selectedTask.depends_on_task_ids.length - 5}`}
                                                        variant="outlined"
                                                    />
                                                )}
                                            </Box>
                                        </Box>
                                    )}

                                    <Box sx={{mt: 1.5, display: 'flex', gap: 1, flexWrap: 'wrap'}}>
                                        <Button
                                            variant="contained"
                                            size="small"
                                            color="secondary"
                                            onClick={() => {
                                                setBatchFilter(selectedTask.batch_id);
                                                setEditDialogOpen(false);
                                            }}
                                        >
                                            📌 Показать только эту партию
                                        </Button>
                                    </Box>
                                </Box>
                            ) : (
                                <Alert severity="info" icon={false}>
                                    Задача не привязана к партии ({selectedTask.batch_id || 'нет'})
                                </Alert>
                            )}

                            {/* ==========================================
                    Блок 3: Все операции партии
                    ========================================== */}
                            {selectedBatchTasks.length > 1 && (
                                <Box>
                                    <Typography variant="subtitle2" sx={{fontWeight: 700, mb: 1, color: '#2c3e50'}}>
                                        🔧 Все операции партии ({selectedBatchTasks.length})
                                    </Typography>
                                    <TableContainer component={Paper} variant="outlined">
                                        <Table size="small" stickyHeader>
                                            <TableHead>
                                                <TableRow>
                                                    <TableCell sx={{fontWeight: 600}}>Операция</TableCell>
                                                    <TableCell sx={{fontWeight: 600}}>Оборудование</TableCell>
                                                    <TableCell sx={{fontWeight: 600}}>Роль</TableCell>
                                                    <TableCell sx={{fontWeight: 600}} align="right">Длит.</TableCell>
                                                    <TableCell sx={{fontWeight: 600}}>Начало</TableCell>
                                                </TableRow>
                                            </TableHead>
                                            <TableBody>
                                                {selectedBatchTasks.map((t) => {
                                                    const isCurrent = t.id === selectedTask.id;
                                                    return (
                                                        <TableRow
                                                            key={t.id}
                                                            hover
                                                            selected={isCurrent}
                                                            sx={{
                                                                cursor: 'pointer',
                                                                bgcolor: isCurrent ? '#e3f2fd' : undefined,
                                                            }}
                                                        >
                                                            <TableCell>
                                                                <Typography variant="caption" sx={{fontWeight: isCurrent ? 700 : 400}}>
                                                                    {t.operation_name}
                                                                </Typography>
                                                            </TableCell>
                                                            <TableCell>
                                                                <Typography variant="caption">
                                                                    {t.equipment_id}
                                                                </Typography>
                                                            </TableCell>
                                                            <TableCell>
                                                                <Typography variant="caption">
                                                                    {t.task_role || '—'}
                                                                </Typography>
                                                            </TableCell>
                                                            <TableCell align="right">
                                                                <Typography variant="caption">
                                                                    {t.duration_minutes} мин
                                                                </Typography>
                                                            </TableCell>
                                                            <TableCell>
                                                                <Typography variant="caption">
                                                                    {new Date(t.start).toLocaleString('ru-RU')}
                                                                </Typography>
                                                            </TableCell>
                                                        </TableRow>
                                                    );
                                                })}
                                            </TableBody>
                                        </Table>
                                    </TableContainer>
                                </Box>
                            )}
                        </Box>
                    )}
                </DialogContent>

                <DialogActions sx={{px: 3, py: 1.5, flexShrink: 0}}>
                    <Button onClick={() => setEditDialogOpen(false)}>Закрыть</Button>
                    {!isReadOnly && (
                        <Button onClick={handleSaveTask} variant="contained">
                            Сохранить время
                        </Button>
                    )}
                </DialogActions>
            </Dialog>
        </Box>
    );
};

export default GanttPage;