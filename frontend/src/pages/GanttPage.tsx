// frontend/src/pages/GanttPage.tsx
import React, {useCallback, useEffect, useRef, useState} from 'react';
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
    FormControl,
    FormControlLabel,
    InputAdornment,
    InputLabel,
    MenuItem,
    Select,
    TextField,
    ToggleButton,
    ToggleButtonGroup,
    Typography,
} from '@mui/material';
import {
    Clear as ClearIcon,
    Download as DownloadIcon,
    FilterAltOff as FilterAltOffIcon,
    Lock as LockIcon,
    QrCodeScanner as QrCodeScannerIcon,
    Refresh as RefreshIcon,
    Search as SearchIcon,
    Today as TodayIcon,
    ZoomIn as ZoomInIcon,
    ZoomOut as ZoomOutIcon,
} from '@mui/icons-material';
import {Timeline} from 'vis-timeline/standalone';
import {DataSet} from 'vis-data';
import 'vis-timeline/styles/vis-timeline-graph2d.min.css';
import {ganttApi, rescheduleApi} from '../services/api';
import {API_BASE_URL} from '../config';
import {usePlan} from '../context/PlainContext';
import type {CoolingMode, CzStatus} from '../types';

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
    // Итерация 5: блокировка лабораторией
    is_lab_blocked?: boolean;
    lab_status?: string | null;
    lab_block_reason?: string | null;
    // Итерация 7: режим охлаждения
    cooling_mode?: CoolingMode;
    // Итерация 8: роль и ЧЗ
    task_role?: string | null;
    cz_status?: CzStatus | null;
    cz_marked_qty?: number | null;
}

const GanttPage: React.FC = () => {
    const containerRef = useRef<HTMLDivElement>(null);
    const timelineRef = useRef<any>(null);
    const handleTaskEditRef = useRef<(taskId: string) => void>(() => {});

    const { currentVersionId, currentPlanName } = usePlan();
    const isReadOnly = currentVersionId !== null;

    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [stats, setStats] = useState({
        totalTasks: 0,
        makespanHours: 0,
        equipmentCount: 0,
        blockedCount: 0,
        coolingSlowCount: 0,
        czIncompleteCount: 0,     // Итерация 8
    });
    const [tasks, setTasks] = useState<TaskData[]>([]);
    const [equipmentList, setEquipmentList] = useState<string[]>([]);
    const [productList, setProductList] = useState<string[]>([]);

    const [filteredCount, setFilteredCount] = useState(0);

    // Фильтры
    const [searchQuery, setSearchQuery] = useState('');
    const [equipmentFilter, setEquipmentFilter] = useState<string[]>([]);
    const [productFilter, setProductFilter] = useState<string[]>([]);
    const [showSetups, setShowSetups] = useState(true);
    const [showDowntimes, setShowDowntimes] = useState(true);
    const [showOnlyBlocked, setShowOnlyBlocked] = useState(false);
    const [showOnlySlowCooling, setShowOnlySlowCooling] = useState(false);
    const [showOnlyCzIncomplete, setShowOnlyCzIncomplete] = useState(false);   // Итерация 8

    const hasActiveFilters =
        searchQuery.length > 0 ||
        equipmentFilter.length > 0 ||
        productFilter.length > 0 ||
        showOnlyBlocked ||
        showOnlySlowCooling ||
        showOnlyCzIncomplete;

    const [editDialogOpen, setEditDialogOpen] = useState(false);
    const [selectedTask, setSelectedTask] = useState<TaskData | null>(null);
    const [editFormData, setEditFormData] = useState({ start: '', end: '' });

    const clickTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    const loadGanttData = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const data = await ganttApi.getData(currentVersionId || undefined);

            const typedTasks = data.tasks as TaskData[];

            const blockedCount = typedTasks.filter(
                (t) => t.is_lab_blocked === true
            ).length;
            const coolingSlowCount = typedTasks.filter(
                (t) => t.cooling_mode === 'slow'
            ).length;
            // Итерация 8: считаем задачи LINE_FILL с незавершённой маркировкой
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

    useEffect(() => {
        loadGanttData();
        return () => {
            if (timelineRef.current) {
                timelineRef.current.destroy();
                timelineRef.current = null;
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
                if (curr.batch_id !== next.batch_id) {
                    const setupStart = new Date(curr.end);
                    const setupEnd = new Date(next.start);
                    const durationMins = Math.round((setupEnd.getTime() - setupStart.getTime()) / 60000);
                    if (durationMins > 0) {
                        setups.push({
                            id: `setup_${curr.id}_${next.id}`,
                            batch_id: 'Замывка',
                            operation_name: '🧼 Замывка',
                            equipment_id: eqId,
                            product_id: '—',
                            start: setupStart.toISOString(),
                            end: setupEnd.toISOString(),
                            duration_minutes: durationMins,
                            item_type: 'setup',
                            setup_type: curr.product_id === next.product_id ? 'same_pf' : 'diff_pf',
                        });
                    }
                }
            }
        });
        return setups;
    };

    const generateWeekends = (tasksData: TaskData[], equipment: string[]): TaskData[] => {
        if (tasksData.length === 0 || equipment.length === 0) return [];
        const weekends: TaskData[] = [];
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
                setEditFormData({ start: taskData.start, end: taskData.end });
                setEditDialogOpen(true);
            }
        },
        [tasks, isReadOnly]
    );

    useEffect(() => {
        handleTaskEditRef.current = handleTaskEdit;
    }, [handleTaskEdit]);

    const renderTimeline = useCallback(
        (tasksData: TaskData[], equipment: string[]) => {
            if (!containerRef.current) return;
            if (timelineRef.current) {
                timelineRef.current.destroy();
                timelineRef.current = null;
            }

            let filteredTasks = tasksData.filter((task) => task.item_type === 'task' || !task.item_type);

            if (showOnlyBlocked) {
                filteredTasks = filteredTasks.filter((task) => task.is_lab_blocked === true);
            }

            if (showOnlySlowCooling) {
                filteredTasks = filteredTasks.filter((task) => task.cooling_mode === 'slow');
            }

            // Итерация 8: фильтр «Только не промаркированные»
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
                filteredTasks = filteredTasks.filter((task) => equipmentFilter.includes(task.equipment_id));
            }

            if (productFilter.length > 0) {
                filteredTasks = filteredTasks.filter((task) => productFilter.includes(task.product_id));
            }

            setFilteredCount(filteredTasks.length);

            const setups = showSetups ? generateSetups(filteredTasks) : [];
            const weekends = showDowntimes ? generateWeekends(filteredTasks, equipment) : [];
            const allItems = [...filteredTasks, ...setups, ...weekends];

            if (allItems.length === 0) {
                if (containerRef.current) {
                    containerRef.current.innerHTML = '';
                }
                return;
            }

            const groupsArray = equipment.map((eq: string) => ({
                id: eq,
                content: `<b>${eq}</b>`,
            }));

            const itemsArray = allItems.map((task: TaskData) => {
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
                           ${task.lab_block_reason ? `<div style="color: #e74c3c; font-size: 11px; margin-top: 2px;">Причина: ${task.lab_block_reason}</div>` : ''}`
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

                    // Итерация 8: бейдж ЧЗ для LINE_FILL
                    let czBadge = '';
                    if (task.task_role === 'LINE_FILL' && task.cz_status) {
                        const czLabel =
                            task.cz_status === 'COMPLETED' ? '🟢 ЧЗ завершено' :
                                task.cz_status === 'IN_PROGRESS' ? '🔵 ЧЗ в работе' :
                                    task.cz_status === 'PENDING' ? '🟡 ЧЗ ожидает' :
                                        '⚪ ЧЗ не требуется';
                        czBadge = `
                            <div style="margin-top: 4px; font-size: 11px;">
                                <b>${czLabel}</b>
                                ${task.cz_marked_qty != null ? `<br>Промаркировано: ${task.cz_marked_qty}` : ''}
                            </div>
                        `;
                    }

                    title = `
            <div style="padding: 8px; min-width: 280px;">
              <b style="font-size: 14px; color: ${isBlocked ? '#e74c3c' : '#2c3e50'};">
                ${isBlocked ? '🔒 ' : ''}${isSlowCooling ? '⏳ ' : ''}${task.operation_name}
              </b><br>
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
                    const setupColor = task.setup_type === 'same_pf' ? '#95a5a6' : '#e67e22';
                    const setupLabel = task.setup_type === 'same_pf' ? 'тот же ПФ (30 мин)' : 'другой ПФ (90 мин)';
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
                <b>Длительность:</b> ${task.duration_minutes} мин (${(task.duration_minutes / 60).toFixed(1)} ч)<br>
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
              <div style="font-weight: bold; color: ${task.is_lab_blocked ? '#e74c3c' : (task.cooling_mode === 'slow' ? '#e67e22' : '#2c3e50')}; margin-bottom: 2px;">
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

            const groups = new DataSet(groupsArray);
            const items = new DataSet(itemsArray);

            const options = {
                groupOrder: 'content' as const,
                editable: {
                    add: false,
                    updateTime: !isReadOnly,
                    updateGroup: !isReadOnly,
                    remove: false,
                },
                // === C2 UX-оптимизация ===
                moveable: false,          // ← НЕ тащить timeline мышью
                selectable: true,         // ← клик по задаче выделяет её
                multiselect: false,       // ← не выбирать много задач
                // === Конец ===
                margin: { item: 2, axis: 5 },
                orientation: 'top' as const,
                stack: false,
                showCurrentTime: true,
                zoomMin: 1000 * 60 * 60 * 4,
                zoomMax: 1000 * 60 * 60 * 24 * 14,
                format: {
                    minorLabels: { hour: 'HH:mm', weekday: 'D MMM' },
                    majorLabels: { day: 'D MMMM YYYY' },
                },
                locale: 'ru',
                tooltip: {
                    followMouse: true,
                    overflowMethod: 'cap' as const,
                    delay: 100,
                },
                snap: (date: Date) => {
                    const minutes = 15;
                    const ms = 1000 * 60 * minutes;
                    return new Date(Math.round(date.getTime() / ms) * ms);
                },
                onMove: async (item: any, callback: (item: any) => void) => {
                    // Итерация 9 (C2): drag-and-drop через API.
                    //
                    // Логика:
                    //   1. Режим просмотра → откат (callback со старым временем).
                    //   2. Найти оригинальную задачу в state.
                    //   3. Сравнить новое время со старым.
                    //   4. Если изменилось — вызвать API moveTask.
                    //   5. При успехе — обновить state + callback.
                    //   6. При ошибке — откат + показать ошибку.

                    // 1. Режим просмотра — не сохраняем
                    if (isReadOnly) {
                        const original = tasks.find((t) => t.id === item.id);
                        if (original) {
                            callback({
                                ...item,
                                start: original.start,
                                end: original.end,
                            });
                        } else {
                            callback(item);
                        }
                        return;
                    }

                    // 2. Найти оригинальную задачу
                    const task = tasks.find((t) => t.id === item.id);
                    if (!task) {
                        callback(item);
                        return;
                    }

                    // 3. Сравнить время
                    const newStart = new Date(item.start).toISOString();
                    const newEnd = new Date(item.end).toISOString();
                    const oldStart = new Date(task.start).toISOString();
                    const oldEnd = new Date(task.end).toISOString();

                    if (newStart === oldStart && newEnd === oldEnd) {
                        // Ничего не изменилось — просто подтверждаем
                        callback(item);
                        return;
                    }

                    // 4. Вызвать API
                    try {
                        await rescheduleApi.moveTask(item.id, newStart, newEnd);

                        // 5. Обновить локальный state
                        setTasks((prev) =>
                            prev.map((t) =>
                                t.id === item.id
                                    ? { ...t, start: newStart, end: newEnd }
                                    : t
                            )
                        );

                        callback(item);

                        console.log(
                            `[C2] Задача "${task.operation_name}" перемещена: ` +
                            `${new Date(oldStart).toLocaleString('ru-RU')} → ` +
                            `${new Date(newStart).toLocaleString('ru-RU')}`
                        );
                    } catch (err: any) {
                        // 6. Откат при ошибке
                        const detail = err.response?.data?.detail;
                        const msg = typeof detail === 'string'
                            ? detail
                            : 'Ошибка перемещения задачи';

                        setError(msg);

                        callback({
                            ...item,
                            start: task.start,
                            end: task.end,
                        });
                    }
                },
                // onMoving: (item: any) => item,
            };

            timelineRef.current = new Timeline(containerRef.current, items, groups, options);

            timelineRef.current.on('click', (props: any) => {
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

            timelineRef.current.fit();
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
            tasks,       // ← добавлено для C2 (onMove ищет задачу в state)
            setError,    // ← добавлено для C2 (обработка ошибок API)
        ]
    );

    useEffect(() => {
        if (tasks.length > 0 && equipmentList.length > 0) {
            renderTimeline(tasks, equipmentList);
        }
    }, [tasks, equipmentList, renderTimeline]);

    const handleZoomIn = () => {
        if (timelineRef.current) {
            const range = timelineRef.current.getWindow();
            const center = (range.start.getTime() + range.end.getTime()) / 2;
            const interval = (range.end.getTime() - range.start.getTime()) * 0.2;
            timelineRef.current.setWindow(new Date(center - interval), new Date(center + interval));
        }
    };

    const handleZoomOut = () => {
        if (timelineRef.current) {
            const range = timelineRef.current.getWindow();
            const center = (range.start.getTime() + range.end.getTime()) / 2;
            const interval = (range.end.getTime() - range.start.getTime()) * 0.3;
            timelineRef.current.setWindow(new Date(center - interval), new Date(center + interval));
        }
    };

    const handleGoToToday = () => {
        if (timelineRef.current) {
            timelineRef.current.focus();
        }
    };

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
                        ? { ...t, start: editFormData.start, end: editFormData.end }
                        : t
                )
            );
            setEditDialogOpen(false);
        } catch (err: any) {
            console.error('Error saving task:', err);
        }
    };

    const formatDateForInput = (isoString: string) => {
        const date = new Date(isoString);
        const pad = (n: number) => n.toString().padStart(2, '0');
        return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
    };

    if (loading) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', mt: 8 }}>
                <CircularProgress />
            </Box>
        );
    }

    return (
        <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2, flexWrap: 'wrap', gap: 2 }}>
                <Typography variant="h4" component="h1" sx={{ fontWeight: 600, color: '#2c3e50' }}>
                    Диаграмма Ганта
                </Typography>
                <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                    <Button variant="outlined" startIcon={<RefreshIcon />} onClick={loadGanttData}>
                        Обновить
                    </Button>
                    <Button variant="contained" color="success" startIcon={<DownloadIcon />} onClick={handleExport}>
                        Экспорт в Excel
                    </Button>
                </Box>
            </Box>

            {error && (
                <Alert severity="warning" sx={{ mb: 2 }}>
                    {error}
                    <br />
                    <Typography variant="body2" sx={{ mt: 1 }}>
                        💡 Перейдите на вкладку <b>"Планирование"</b> и нажмите <b>"Построить план"</b>, либо выберите сохраненную версию.
                    </Typography>
                </Alert>
            )}

            {!error && (
                <>
                    <Card sx={{ mb: 2, p: 2, bgcolor: '#f8f9fa' }}>
                        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, alignItems: 'center' }}>
                            <Chip
                                label={
                                    hasActiveFilters
                                        ? `Показано: ${filteredCount} / ${stats.totalTasks}`
                                        : `Всего задач: ${stats.totalTasks}`
                                }
                                color={hasActiveFilters ? 'warning' : 'primary'}
                                variant={hasActiveFilters ? 'filled' : 'outlined'}
                            />
                            <Chip label={`Makespan: ${stats.makespanHours.toFixed(1)} ч`} color="secondary" variant="outlined" />
                            <Chip label={`Оборудование: ${stats.equipmentCount}`} variant="outlined" />
                            {stats.blockedCount > 0 && (
                                <Chip
                                    icon={<LockIcon />}
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
                            {/* Итерация 8: ЧЗ-статистика */}
                            {stats.czIncompleteCount > 0 && (
                                <Chip
                                    icon={<QrCodeScannerIcon />}
                                    label={`📷 Не промаркировано: ${stats.czIncompleteCount}`}
                                    color="info"
                                    variant="filled"
                                />
                            )}

                            {isReadOnly && (
                                <Chip
                                    icon={<LockIcon />}
                                    label={`Просмотр: ${currentPlanName}`}
                                    color="info"
                                    variant="filled"
                                />
                            )}

                            <Box sx={{ display: 'flex', gap: 1.5, ml: 'auto', flexWrap: 'wrap' }}>
                                {Object.entries(OPERATION_COLORS)
                                    .slice(0, 5)
                                    .map(([name, color]) => (
                                        <Box key={name} sx={{ display: 'flex', alignItems: 'center', gap: 0.5, fontSize: '0.85rem' }}>
                                            <Box sx={{ width: 12, height: 12, bgcolor: color, borderRadius: '2px' }} />
                                            {name}
                                        </Box>
                                    ))}
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, fontSize: '0.85rem' }}>
                                    <Box sx={{ width: 12, height: 12, bgcolor: '#ffebee', border: '2px solid #e74c3c', borderRadius: '2px' }} />
                                    🔒 Заблокировано
                                </Box>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, fontSize: '0.85rem' }}>
                                    <Box sx={{ width: 12, height: 12, bgcolor: '#fff3e0', border: '2px dashed #e67e22', borderRadius: '2px' }} />
                                    ⏳ Замедленное охлаждение
                                </Box>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, fontSize: '0.85rem' }}>
                                    <Box sx={{ width: 12, height: 12, bgcolor: '#e3f2fd', border: '2px dotted #1976d2', borderRadius: '2px' }} />
                                    📷 ЧЗ не завершено
                                </Box>
                            </Box>
                        </Box>

                        <Box sx={{ display: 'flex', gap: 2, mt: 2, flexWrap: 'wrap', alignItems: 'center' }}>
                            <TextField
                                size="small"
                                placeholder="Поиск задач..."
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                sx={{ minWidth: 250 }}
                                slotProps={{
                                    input: {
                                        startAdornment: (
                                            <InputAdornment position="start">
                                                <SearchIcon />
                                            </InputAdornment>
                                        ),
                                    },
                                }}
                            />

                            <FormControl size="small" variant="outlined" sx={{ minWidth: 200 }}>
                                <InputLabel>Оборудование</InputLabel>
                                <Select
                                    multiple
                                    value={equipmentFilter}
                                    onChange={(e) => setEquipmentFilter(e.target.value as string[])}
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

                            <FormControl size="small" variant="outlined" sx={{ minWidth: 200 }}>
                                <InputLabel>Продукты</InputLabel>
                                <Select
                                    multiple
                                    value={productFilter}
                                    onChange={(e) => setProductFilter(e.target.value as string[])}
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
                                label={<Typography variant="body2" sx={{ fontWeight: showOnlyBlocked ? 600 : 400 }}>🔒 Только заблокированные</Typography>}
                            />

                            <FormControlLabel
                                control={
                                    <Checkbox
                                        checked={showOnlySlowCooling}
                                        onChange={(e) => setShowOnlySlowCooling(e.target.checked)}
                                        size="small"
                                        color="warning"
                                    />
                                }
                                label={<Typography variant="body2" sx={{ fontWeight: showOnlySlowCooling ? 600 : 400 }}>⏳ Только замедленное охлаждение</Typography>}
                            />

                            {/* Итерация 8: фильтр «Только не промаркированные» */}
                            <FormControlLabel
                                control={
                                    <Checkbox
                                        checked={showOnlyCzIncomplete}
                                        onChange={(e) => setShowOnlyCzIncomplete(e.target.checked)}
                                        size="small"
                                        color="info"
                                    />
                                }
                                label={<Typography variant="body2" sx={{ fontWeight: showOnlyCzIncomplete ? 600 : 400 }}>📷 Только не промаркированные</Typography>}
                            />

                            <Button
                                size="small"
                                variant="outlined"
                                color="inherit"
                                startIcon={<FilterAltOffIcon />}
                                onClick={handleResetFilters}
                                disabled={!hasActiveFilters}
                                sx={{ textTransform: 'none' }}
                            >
                                Сбросить фильтры
                            </Button>

                            <ToggleButtonGroup size="small" aria-label="zoom">
                                <ToggleButton value="zoomOut" onClick={handleZoomOut}>
                                    <ZoomOutIcon />
                                </ToggleButton>
                                <ToggleButton value="today" onClick={handleGoToToday}>
                                    <TodayIcon />
                                </ToggleButton>
                                <ToggleButton value="zoomIn" onClick={handleZoomIn}>
                                    <ZoomInIcon />
                                </ToggleButton>
                            </ToggleButtonGroup>
                        </Box>
                    </Card>

                    {hasActiveFilters && filteredCount === 0 && (
                        <Alert
                            severity="info"
                            icon={<ClearIcon />}
                            sx={{ mb: 2 }}
                            action={
                                <Button color="inherit" size="small" onClick={handleResetFilters}>
                                    Сбросить
                                </Button>
                            }
                        >
                            По заданным фильтрам ничего не найдено. Попробуйте ослабить условия.
                        </Alert>
                    )}

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
                                        '&:hover': { opacity: 1 },
                                    },
                                    '& .item-downtime': {
                                        '&:hover': { opacity: 0.9 },
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

                    <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block', textAlign: 'center' }}>
                        💡 Все операции по реактору в одной строке • Пунктир = замывки • Фиолетовый фон = выходные • 🔒 = заблокировано лабораторией • ⏳ = замедленное охлаждение • 📷 = ЧЗ не завершено
                        {isReadOnly ? ' • Режим просмотра (редактирование недоступно)' : ' • Двойной клик для редактирования'}
                        • Колесико мыши для масштабирования
                    </Typography>
                </>
            )}

            <Dialog open={editDialogOpen} onClose={() => setEditDialogOpen(false)} maxWidth="sm" fullWidth>
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
                                onChange={(e) => setEditFormData({ ...editFormData, start: e.target.value })}
                                slotProps={{
                                    inputLabel: { shrink: true },
                                    htmlInput: { step: 300 },
                                }}
                            />
                            <TextField
                                margin="dense"
                                label="Конец"
                                type="datetime-local"
                                fullWidth
                                value={formatDateForInput(editFormData.end)}
                                onChange={(e) => setEditFormData({ ...editFormData, end: e.target.value })}
                                slotProps={{
                                    inputLabel: { shrink: true },
                                    htmlInput: { step: 300 },
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