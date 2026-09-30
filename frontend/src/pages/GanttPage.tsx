// frontend/src/pages/GanttPage.tsx
// Итерация 13.10: выходные — фоновые полосы (type: 'background').
// Итерация 13.15: если у плана нет снапшотов (has_snapshot=false),
//   показываем предупреждение вместо диаграммы.
// Итерация 13.16: расширенный диалог задачи переведён на DraggableDialog.
// Итерация 13.17: полный рефакторинг — вынесены модули.
// Итерация 13.18 (fix #5): tooltip теперь отображается и при resize,
//   и при move. Прокинут onItemChange в useGanttTimeline.
// Итерация 13.19: readonly-режим через usePlan().currentVersionId;
//   кнопка «Пересчитать» активна только при planDirty === true.
//   onForceRecalc в RecalcSettingsDialog вызывает форс-режим
//   (skipSettingsCheck=true), чтобы не зацикливаться на пустых
//   plan_settings.
// Итерация 13.20: RecalcProgressDialog — модальное окно прогресса
//   пересчёта. Показывается, пока solver работает. Таймер и спиннер,
//   блокировка Esc/backdrop/UI.
// Итерация 13.21: после успешного пересчёта показываем Alert,
//   если старая версия не была архивирована (replace_blocked=true).
//   Также сбрасываем planDirty, даже если архивация не удалась —
//   пользователь уже увидел актуальный результат.

import React, {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {useNavigate, useSearchParams} from 'react-router-dom';
import {Alert, Box, Button, Chip, CircularProgress, Paper, Snackbar, Typography,} from '@mui/material';
import {Archive as ArchiveIcon, WarningAmber as WarningIcon,} from '@mui/icons-material';

import type {Timeline} from 'vis-timeline/standalone';
import 'vis-timeline/styles/vis-timeline-graph2d.min.css';
import {API_BASE_URL} from '../config';
import {usePlan} from '../context/PlainContext';
import type {RescheduleResponse, TaskData, ValidationErrorState,} from '../types';
import GanttToolbar from '../components/gantt/GanttToolbar';
import GanttFiltersBar from '../components/gantt/GanttFiltersBar';
import GanttFiltersPopover from '../components/gantt/GanttFiltersPopover';
import GanttTaskDialog from '../components/gantt/GanttTaskDialog';
import TaskContextMenu from '../components/gantt/TaskContextMenu';
import MoveValidationDialog from '../components/gantt/MoveValidationDialog';
import DragTooltip from '../components/gantt/DragTooltip';
import RecalcSettingsDialog from '../components/gantt/RecalcSettingsDialog';
import RecalcProgressDialog from '../components/gantt/RecalcProgressDialog';
import PlanSettingsWizard, {type WizardMode} from './PlanSettingsWizard';

import {NON_BATCH_VALUES, STORAGE_KEYS} from '../components/gantt/constants';
import {useGanttData} from '../hooks/useGanttData';
import {useGanttDependencies} from '../hooks/useGanttDependencies';
import {useGanttFilters} from '../hooks/useGanttFilters';
import {useGanttTimeline} from '../hooks/useGanttTimeline';
import {useGanttViewport} from '../hooks/useGanttViewport';
import {useExpandedGroups} from '../hooks/useExpandedGroups';
import {useGanttActions} from '../hooks/useGanttActions';

// ==========================================
// Итерация 13.20: тип операции пересчёта
// ==========================================
type RecalcOperation = 'recalc' | 'force-recalc';

const RECALC_OPERATION_LABELS: Record<RecalcOperation, string> = {
    'recalc': 'Пересчёт плана',
    'force-recalc': 'Пересчёт плана (принудительный)',
};

const RECALC_OPERATION_HINTS: Record<RecalcOperation, string> = {
    'recalc': 'Solver пересчитывает план с учётом внесённых изменений.',
    'force-recalc': 'Solver пересчитывает план с текущими глобальными настройками.',
};

const GanttPage: React.FC = () => {
    const navigate = useNavigate();

    const [searchParams] = useSearchParams();
    const urlVersionId = searchParams.get('version_id');

    // --- Refs ---
    const containerRef = useRef<HTMLDivElement>(null);
    const minimapContainerRef = useRef<HTMLDivElement>(null);
    const svgOverlayRef = useRef<SVGSVGElement | null>(null);
    const timelineRef = useRef<Timeline | null>(null);
    const minimapRef = useRef<Timeline | null>(null);
    const handleTaskEditRef = useRef<(taskId: string) => void>(() => {});

    const minimapSyncingRef = useRef<boolean>(false);

    // --- Plan context ---
    const {
        currentVersionId: contextVersionId,
        currentPlanName: contextPlanName,
        currentPlanHasSnapshot: contextHasSnapshot,
        planDirty,
        clearPlanDirty,
        clearPlan,
        setPlan,
    } = usePlan();

    const currentVersionId = urlVersionId || contextVersionId;
    const currentPlanName = urlVersionId
        ? `Просмотр из URL`
        : contextPlanName;
    const currentPlanHasSnapshot = urlVersionId
        ? true
        : contextHasSnapshot;

    // ==========================================
    // Итерация 13.19: readonly включается, если план открыт
    // (через URL или через контекст).
    // ==========================================
    const isReadOnly =
        urlVersionId !== null ||
        contextVersionId !== null;

    const isEmptyPlan =
        currentVersionId !== null && !currentPlanHasSnapshot;

    // ==========================================
    // Данные Ганта
    // ==========================================
    const {
        loading,
        error,
        setError,
        stats,
        tasks,
        setTasks,
        equipmentList,
        productList,
        refresh: loadGanttData,
    } = useGanttData(currentVersionId);

    const [filteredCount, setFilteredCount] = useState(0);

    const [showMinimap, setShowMinimap] = useState<boolean>(() => {
        return localStorage.getItem(STORAGE_KEYS.minimap) === '1';
    });
    const [showDependencies, setShowDependencies] = useState<boolean>(() => {
        return localStorage.getItem(STORAGE_KEYS.showDependencies) !== '0';
    });
    const [showAllDependencies, setShowAllDependencies] = useState<boolean>(() => {
        return localStorage.getItem(STORAGE_KEYS.showAllDependencies) === '1';
    });
    const [filtersAnchorEl, setFiltersAnchorEl] = useState<HTMLElement | null>(null);
    const filtersOpen = Boolean(filtersAnchorEl);

    const [searchQuery, setSearchQuery] = useState('');
    const [equipmentFilter, setEquipmentFilter] = useState<string[]>([]);
    const [productFilter, setProductFilter] = useState<string[]>([]);
    const [showSetups, setShowSetups] = useState(true);
    const [showDowntimes, setShowDowntimes] = useState(true);
    const [showOnlyBlocked, setShowOnlyBlocked] = useState(false);
    const [showOnlySlowCooling, setShowOnlySlowCooling] = useState(false);
    const [showOnlyCzIncomplete, setShowOnlyCzIncomplete] = useState(false);
    const [showOnlyPinned, setShowOnlyPinned] = useState(false);
    const [batchFilter, setBatchFilter] = useState<string | null>(null);

    const [editDialogOpen, setEditDialogOpen] = useState(false);
    const [selectedTask, setSelectedTask] = useState<TaskData | null>(null);
    const [editFormData, setEditFormData] = useState({start: '', end: ''});

    const [contextMenuPosition, setContextMenuPosition] = useState<{ top: number; left: number } | null>(null);
    const [contextMenuTask, setContextMenuTask] = useState<TaskData | null>(null);

    const [validationError, setValidationError] = useState<ValidationErrorState>({
        open: false,
        reason: '',
        details: [],
    });

    const [recalcSettingsDialogOpen, setRecalcSettingsDialogOpen] = useState(false);
    const [wizardOpen, setWizardOpen] = useState(false);
    const [wizardMode, setWizardMode] = useState<WizardMode>('edit');
    const [wizardVersionId, setWizardVersionId] = useState<string | null>(null);

    // ==========================================
    // Итерация 13.20: операция пересчёта (для прогресс-диалога)
    // null — прогресс не показывается.
    // ==========================================
    const [recalcOperation, setRecalcOperation] = useState<RecalcOperation | null>(null);

    // ==========================================
    // Итерация 13.21: снекбар для уведомления об архивации
    // ==========================================
    const [archiveSnackbar, setArchiveSnackbar] = useState<{
        open: boolean;
        message: string;
        severity: 'info' | 'warning';
        whatifIds: string[];
    }>({
        open: false,
        message: '',
        severity: 'info',
        whatifIds: [],
    });

    const expandedGroups = useExpandedGroups(currentVersionId);

    // ==========================================
    // Связи, фильтры, viewport
    // ==========================================
    const deps = useGanttDependencies({
        containerRef,
        svgRef: svgOverlayRef,
        timelineRef,
        tasks,
        showDependencies,
        showAllDependencies,
    });

    const filters = useGanttFilters(tasks, {
        searchQuery,
        equipmentFilter,
        productFilter,
        batchFilter,
        showOnlyBlocked,
        showOnlySlowCooling,
        showOnlyCzIncomplete,
        showOnlyPinned,
    });

    const viewport = useGanttViewport({
        timelineRef,
        versionId: currentVersionId,
    });

    // ==========================================
    // Действия на Ганте
    // ==========================================
    const actions = useGanttActions({
        tasks,
        setTasks,
        versionId: currentVersionId,
        setError,
        setValidationError,
        onOpenTaskDialog: (task) => {
            setSelectedTask(task);
            setEditFormData({start: task.start, end: task.end});
            setEditDialogOpen(true);
        },
        // Итерация 13.21: onRecalcSuccess получает полный Response
        onRecalcSuccess: (newVersionId, response: RescheduleResponse) => {
            // Итерация 13.19: сбрасываем флаг «грязный»
            clearPlanDirty();
            setPlan(
                newVersionId,
                `Пересчитано ${new Date().toLocaleString('ru-RU')}`,
                true,
            );

            // Итерация 13.21: показываем снекбар о результате архивации
            if (response.replace_archived) {
                setArchiveSnackbar({
                    open: true,
                    message: 'Старая версия перемещена в архив',
                    severity: 'info',
                    whatifIds: [],
                });
            } else if (response.replace_blocked) {
                setArchiveSnackbar({
                    open: true,
                    message: response.replace_blocked_reason
                        || 'Старая версия не архивирована (используется в what-if)',
                    severity: 'warning',
                    whatifIds: response.used_by_whatif || [],
                });
            }

            // Итерация 13.20: закрываем прогресс-диалог
            setRecalcOperation(null);

            if (urlVersionId) {
                navigate(`/gantt?version_id=${newVersionId}`, {replace: true});
            } else {
                void loadGanttData();
            }
        },
        onRecalcNeedsSettings: () => {
            setRecalcSettingsDialogOpen(true);
        },
        timelineRef,
        showOnlyPinned,
        onFilteredCountChange: setFilteredCount,
    });

    // ==========================================
    // Итерация 13.20: обёртки над actions, чтобы показать прогресс
    // ==========================================
    const handleRecalculate = useCallback(async () => {
        setRecalcOperation('recalc');
        try {
            await actions.recalculate();
        } finally {
            // Если onRecalcSuccess не сработал (ошибка или отмена) —
            // всё равно закрыть прогресс-диалог
            setRecalcOperation(null);
        }
    }, [actions]);

    const handleForceRecalculate = useCallback(async () => {
        setRecalcOperation('force-recalc');
        try {
            await actions.handleForceRecalculate();
        } finally {
            setRecalcOperation(null);
        }
    }, [actions]);

    // ==========================================
    // Список партий
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
            .filter(
                (t) =>
                    t.batch_id === selectedTask.batch_id &&
                    (!t.item_type || t.item_type === 'task'),
            )
            .sort(
                (a, b) =>
                    new Date(a.start).getTime() - new Date(b.start).getTime(),
            );
    }, [tasks, selectedTask]);

    // ==========================================
    // localStorage
    // ==========================================
    useEffect(() => {
        localStorage.setItem(STORAGE_KEYS.minimap, showMinimap ? '1' : '0');
    }, [showMinimap]);

    useEffect(() => {
        localStorage.setItem(
            STORAGE_KEYS.showDependencies,
            showDependencies ? '1' : '0',
        );
    }, [showDependencies]);

    useEffect(() => {
        localStorage.setItem(
            STORAGE_KEYS.showAllDependencies,
            showAllDependencies ? '1' : '0',
        );
    }, [showAllDependencies]);

    // ==========================================
    // Cleanup
    // ==========================================
    useEffect(() => {
        return () => {
            if (timelineRef.current) {
                timelineRef.current.destroy();
                timelineRef.current = null;
            }
            if (minimapRef.current) {
                minimapRef.current.destroy();
                minimapRef.current = null;
            }
        };
    }, []);

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
        setShowOnlyPinned(false);
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
        [tasks, isReadOnly],
    );

    useEffect(() => {
        handleTaskEditRef.current = handleTaskEdit;
    }, [handleTaskEdit]);

    // ==========================================
    // Контекстное меню
    // ==========================================
    const handleContextMenu = useCallback(
        (event: React.MouseEvent) => {
            if (!timelineRef.current) return;

            const target = event.target as HTMLElement;
            const itemEl = target.closest('.vis-item.vis-range');
            if (!itemEl) {
                setContextMenuPosition(null);
                setContextMenuTask(null);
                return;
            }

            const visItem = (itemEl as any)['vis-item'];
            if (!visItem || !visItem.id) return;

            const taskId = String(visItem.id);

            if (taskId.startsWith('__group__')) {
                event.preventDefault();
                const groupKey = taskId.substring('__group__'.length);
                expandedGroups.toggleGroup(groupKey);
                return;
            }

            const task = tasks.find((t) => t.id === taskId);
            if (!task) return;

            if (task.item_type === 'setup' || task.item_type === 'downtime') {
                return;
            }

            event.preventDefault();
            setContextMenuPosition({top: event.clientY, left: event.clientX});
            setContextMenuTask(task);
        },
        [tasks, expandedGroups],
    );

    const handleCloseContextMenu = useCallback(() => {
        setContextMenuPosition(null);
        setContextMenuTask(null);
    }, []);

    // ==========================================
    // Навигация к задаче
    // ==========================================
    const handleNavigateToTask = useCallback(
        (taskId: string) => {
            const timeline = timelineRef.current;
            if (!timeline) return;

            const task = tasks.find((t) => t.id === taskId);
            if (!task) {
                setError(`Задача ${taskId.substring(0, 8)} не найдена на текущем Ганте`);
                return;
            }

            try {
                timeline.focus(taskId, {
                    animation: {duration: 500, easingFunction: 'easeInOutQuad'},
                    zoom: false,
                });
            } catch {
                const start = new Date(task.start).getTime();
                const end = new Date(task.end).getTime();
                const center = (start + end) / 2;
                const halfWindow = 1000 * 60 * 60 * 6;
                try {
                    timeline.setWindow(
                        new Date(center - halfWindow),
                        new Date(center + halfWindow),
                        {animation: {duration: 500, easingFunction: 'easeInOutQuad'}},
                    );
                } catch {
                    // ignore
                }
            }

            setTimeout(() => {
                const all = containerRef.current?.querySelectorAll<HTMLElement>('.vis-item.vis-range');
                all?.forEach((item) => {
                    const vi = (item as any)['vis-item'];
                    if (vi && String(vi.id) === taskId) {
                        item.classList.add('task-flash-highlight');
                        setTimeout(
                            () => item.classList.remove('task-flash-highlight'),
                            2000,
                        );
                    }
                });
            }, 550);
        },
        [tasks, setError],
    );

    // ==========================================
    // Мастер настроек
    // ==========================================
    const handleOpenWizardEdit = useCallback(() => {
        if (isReadOnly) return;
        if (!currentVersionId) return;
        setWizardMode('edit');
        setWizardVersionId(currentVersionId);
        setWizardOpen(true);
    }, [currentVersionId, isReadOnly]);

    const handleToggleGroup = useCallback(
        (groupKey: string) => {
            expandedGroups.toggleGroup(groupKey);
        },
        [expandedGroups],
    );

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
                        : t,
                ),
            );
            setEditDialogOpen(false);
        } catch (err) {
            console.error('Error saving task:', err);
        }
    };

    // ==========================================
    // Рендер Timeline
    // ==========================================
    const timeline = useGanttTimeline({
        containerRef,
        minimapContainerRef,
        timelineRef,
        minimapRef,
        tasks,
        isReadOnly,
        showMinimap,
        showDependencies,
        showAllDependencies,
        showSetups,
        showDowntimes,
        versionId: currentVersionId,
        expandedGroups: expandedGroups.expanded,
        onToggleGroup: handleToggleGroup,
        viewportRef: viewport.viewportRef,
        suppressViewportSyncRef: viewport.suppressViewportSyncRef,
        minimapSyncingRef,
        saveViewportToStorage: viewport.saveViewportToStorage,
        persistCurrentViewport: viewport.persistCurrentViewport,
        deps,
        filters,
        onTaskEdit: (taskId) => handleTaskEditRef.current(taskId),
        onBatchClick: setBatchFilter,
        onMoveTask: actions.handleMove,
        onError: setError,
        setFilteredCount,
        onItemChange: actions.handleItemChange,
    });

    // ==========================================
    // Стабилизация renderTimeline
    // ==========================================
    const renderTimelineRef = useRef(timeline.renderTimeline);

    useEffect(() => {
        renderTimelineRef.current = timeline.renderTimeline;
    }, [timeline.renderTimeline]);

    const renderedRef = useRef<string>('');

    useEffect(() => {
        if (tasks.length === 0 || equipmentList.length === 0) return;

        const firstTask = tasks[0];
        const lastTask = tasks[tasks.length - 1];

        const key = [
            currentVersionId || 'draft',
            tasks.length,
            equipmentList.length,
            firstTask?.id || '',
            lastTask?.id || '',
            searchQuery,
            equipmentFilter.join(','),
            productFilter.join(','),
            batchFilter || '',
            showOnlyBlocked ? '1' : '0',
            showOnlySlowCooling ? '1' : '0',
            showOnlyCzIncomplete ? '1' : '0',
            showOnlyPinned ? '1' : '0',
            showSetups ? '1' : '0',
            showDowntimes ? '1' : '0',
            showAllDependencies ? '1' : '0',
        ].join('|');

        if (renderedRef.current === key) {
            return;
        }

        renderedRef.current = key;
        renderTimelineRef.current(tasks, equipmentList);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [
        tasks,
        equipmentList,
        currentVersionId,
        searchQuery,
        equipmentFilter,
        productFilter,
        batchFilter,
        showOnlyBlocked,
        showOnlySlowCooling,
        showOnlyCzIncomplete,
        showOnlyPinned,
        showSetups,
        showDowntimes,
        showAllDependencies,
    ]);

    if (loading) {
        return (
            <Box sx={{display: 'flex', justifyContent: 'center', mt: 8}}>
                <CircularProgress/>
            </Box>
        );
    }

    if (isEmptyPlan) {
        return (
            <Box
                sx={{
                    height: '100%',
                    display: 'flex',
                    flexDirection: 'column',
                    minHeight: 0,
                    p: 4,
                }}
            >
                <Alert
                    severity="warning"
                    icon={<WarningIcon fontSize="inherit"/>}
                    sx={{mb: 2}}
                >
                    <Typography variant="h6" sx={{fontWeight: 600, mb: 1}}>
                        План «{currentPlanName}» пуст
                    </Typography>
                    <Typography variant="body2">
                        Этот план был создан до Итерации 13.15, и снапшоты
                        справочников для него не заполнены. Диаграмма Ганта
                        недоступна.
                    </Typography>
                    <Typography variant="body2" sx={{mt: 1.5, fontWeight: 600}}>
                        Что делать:
                    </Typography>
                    <Box component="ul" sx={{mt: 0.5, mb: 1, pl: 3}}>
                        <li>
                            <Typography variant="body2">
                                Закрыть план и создать новый через мастер — снапшоты
                                заполнятся автоматически.
                            </Typography>
                        </li>
                        <li>
                            <Typography variant="body2">
                                Либо удалить этот план (кнопка 🗑 в списке планов)
                                и создать заново.
                            </Typography>
                        </li>
                    </Box>
                    <Box sx={{mt: 2, display: 'flex', gap: 1, flexWrap: 'wrap'}}>
                        <Button
                            variant="contained"
                            onClick={() => navigate('/schedule')}
                        >
                            Перейти к планированию
                        </Button>
                        <Button
                            variant="outlined"
                            color="warning"
                            onClick={() => {
                                if (urlVersionId) {
                                    navigate('/schedule');
                                } else {
                                    clearPlan();
                                    navigate('/schedule');
                                }
                            }}
                        >
                            Закрыть план
                        </Button>
                    </Box>
                </Alert>
            </Box>
        );
    }

    return (
        <Box sx={{height: '100%', display: 'flex', flexDirection: 'column', minHeight: 0}}>
            <GanttToolbar
                totalTasks={stats.totalTasks}
                filteredCount={filteredCount}
                makespanHours={stats.makespanHours}
                equipmentCount={stats.equipmentCount}
                hasActiveFilters={filters.hasActiveFilters}
                isReadOnly={isReadOnly}
                currentPlanName={currentPlanName}
                searchQuery={searchQuery}
                onSearchChange={setSearchQuery}
                onToggleFilters={handleToggleFilters}
                onPanLeft={viewport.handlePanLeft}
                onPanRight={viewport.handlePanRight}
                onZoomIn={viewport.handleZoomIn}
                onZoomOut={viewport.handleZoomOut}
                onFitAll={viewport.handleFitAll}
                onGoToToday={viewport.handleGoToToday}
                showMinimap={showMinimap}
                onToggleMinimap={() => setShowMinimap((v) => !v)}
                showDependencies={showDependencies}
                onToggleDependencies={() => setShowDependencies((v) => !v)}
                showAllDependencies={showAllDependencies}
                onToggleAllDependencies={() => setShowAllDependencies((v) => !v)}
                onOpenAudit={handleOpenAudit}
                onRefresh={() => void loadGanttData()}
                onExport={handleExport}
                onRecalculate={
                    isReadOnly
                        ? () => void handleRecalculate()
                        : undefined
                }
                recalculating={actions.recalculating}
                planDirty={planDirty}
            />

            {error && (
                <Alert severity="warning" sx={{mb: 1, flexShrink: 0}} onClose={() => setError(null)}>
                    {error}
                </Alert>
            )}

            <GanttFiltersBar
                hasActiveFilters={filters.hasActiveFilters}
                batchFilter={batchFilter}
                equipmentFilter={equipmentFilter}
                productFilter={productFilter}
                showOnlyBlocked={showOnlyBlocked}
                showOnlySlowCooling={showOnlySlowCooling}
                showOnlyCzIncomplete={showOnlyCzIncomplete}
                showOnlyPinned={showOnlyPinned}
                onClearBatchFilter={() => setBatchFilter(null)}
                onClearEquipmentFilter={() => setEquipmentFilter([])}
                onClearProductFilter={() => setProductFilter([])}
                onClearOnlyBlocked={() => setShowOnlyBlocked(false)}
                onClearOnlySlowCooling={() => setShowOnlySlowCooling(false)}
                onClearOnlyCzIncomplete={() => setShowOnlyCzIncomplete(false)}
                onClearOnlyPinned={() => setShowOnlyPinned(false)}
                onResetAll={handleResetFilters}
            />

            <Box
                className="gantt-container"
                onContextMenu={handleContextMenu}
                sx={{
                    flexGrow: 1,
                    minHeight: 0,
                    position: 'relative',
                    border: '1px solid #e0e0e0',
                    borderRadius: 1,
                    overflow: 'hidden',
                    bgcolor: 'white',
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
                        '& .task-flash-highlight': {
                            zIndex: 25,
                            boxShadow: '0 0 0 3px #f39c12, 0 4px 16px rgba(243, 156, 18, 0.6)',
                            transition: 'box-shadow 0.3s',
                        },
                        '& .vis-item.item-group': {
                            borderStyle: 'dashed',
                            borderWidth: 2,
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

            <GanttFiltersPopover
                open={filtersOpen}
                anchorEl={filtersAnchorEl}
                onClose={handleCloseFilters}
                equipmentList={equipmentList}
                productList={productList}
                availableBatches={availableBatches}
                equipmentFilter={equipmentFilter}
                productFilter={productFilter}
                batchFilter={batchFilter}
                showSetups={showSetups}
                showDowntimes={showDowntimes}
                showAllDependencies={showAllDependencies}
                showOnlyBlocked={showOnlyBlocked}
                showOnlySlowCooling={showOnlySlowCooling}
                showOnlyCzIncomplete={showOnlyCzIncomplete}
                showOnlyPinned={showOnlyPinned}
                showDependencies={showDependencies}
                hasActiveFilters={filters.hasActiveFilters}
                onEquipmentFilterChange={setEquipmentFilter}
                onProductFilterChange={setProductFilter}
                onBatchFilterChange={setBatchFilter}
                onShowSetupsChange={setShowSetups}
                onShowDowntimesChange={setShowDowntimes}
                onShowAllDependenciesChange={setShowAllDependencies}
                onShowOnlyBlockedChange={setShowOnlyBlocked}
                onShowOnlySlowCoolingChange={setShowOnlySlowCooling}
                onShowOnlyCzIncompleteChange={setShowOnlyCzIncomplete}
                onShowOnlyPinnedChange={setShowOnlyPinned}
                onResetAll={handleResetFilters}
            />

            <GanttTaskDialog
                open={editDialogOpen}
                task={selectedTask}
                batchTasks={selectedBatchTasks}
                isReadOnly={isReadOnly}
                editFormData={editFormData}
                onEditFormChange={setEditFormData}
                onClose={() => setEditDialogOpen(false)}
                onSave={handleSaveTask}
                onFilterByBatch={(batchId) => {
                    setBatchFilter(batchId);
                    setEditDialogOpen(false);
                }}
                onToggleGroup={handleToggleGroup}
            />

            <TaskContextMenu
                anchorPosition={contextMenuPosition}
                task={contextMenuTask}
                isReadOnly={isReadOnly}
                onOpenTaskCard={(task) => handleTaskEditRef.current(task.id)}
                onFilterByBatch={(task) => {
                    if (task.batch_id) setBatchFilter(task.batch_id);
                }}
                onShowBatchOperations={actions.handleShowBatchOperations}
                onPinTask={actions.handlePinTask}
                onUnpinTask={actions.handleUnpinTask}
                onShiftTask={actions.handleShiftTask}
                onCopyTaskId={actions.handleCopyTaskId}
                onCopyBatchId={actions.handleCopyBatchId}
                onClose={handleCloseContextMenu}
            />

            <MoveValidationDialog
                state={validationError}
                onClose={() => setValidationError({open: false, reason: '', details: []})}
                onNavigateToTask={handleNavigateToTask}
            />

            <DragTooltip state={actions.dragTooltip} />

            <RecalcSettingsDialog
                open={recalcSettingsDialogOpen}
                onClose={() => setRecalcSettingsDialogOpen(false)}
                onOpenWizard={handleOpenWizardEdit}
                onForceRecalc={() => {
                    setRecalcSettingsDialogOpen(false);
                    void handleForceRecalculate();
                }}
                planName={currentPlanName}
                recalculating={actions.recalculating}
            />

            {/* ==========================================
                Итерация 13.20: прогресс-диалог пересчёта.
                Показывается, пока recalcOperation !== null.
                Автоматически закрывается:
                  - при успехе (onRecalcSuccess → setRecalcOperation(null));
                  - при ошибке (finally в handleRecalculate).
            ========================================== */}
            <RecalcProgressDialog
                open={recalcOperation !== null}
                operationLabel={
                    recalcOperation
                        ? RECALC_OPERATION_LABELS[recalcOperation]
                        : 'Пересчёт плана'
                }
                operationHint={
                    recalcOperation
                        ? RECALC_OPERATION_HINTS[recalcOperation]
                        : undefined
                }
                timeoutSeconds={600}
            />

            {/* ==========================================
                Итерация 13.21: снекбар о результате архивации.
                - info: старая версия успешно архивирована;
                - warning: старая версия не архивирована, потому что
                  используется в what-if сценарии.
            ========================================== */}
            <Snackbar
                open={archiveSnackbar.open}
                autoHideDuration={8000}
                onClose={() => setArchiveSnackbar((prev) => ({...prev, open: false}))}
                anchorOrigin={{vertical: 'bottom', horizontal: 'right'}}
            >
                <Alert
                    severity={archiveSnackbar.severity}
                    icon={archiveSnackbar.severity === 'info'
                        ? <ArchiveIcon />
                        : <WarningIcon />
                    }
                    onClose={() => setArchiveSnackbar((prev) => ({...prev, open: false}))}
                    sx={{maxWidth: 480}}
                >
                    <Typography variant="body2" sx={{fontWeight: 600}}>
                        {archiveSnackbar.severity === 'info'
                            ? 'Архивация'
                            : 'Старая версия не архивирована'}
                    </Typography>
                    <Typography variant="caption" sx={{display: 'block'}}>
                        {archiveSnackbar.message}
                    </Typography>
                    {archiveSnackbar.whatifIds.length > 0 && (
                        <Box sx={{mt: 0.5, display: 'flex', gap: 0.5, flexWrap: 'wrap'}}>
                            {archiveSnackbar.whatifIds.map((id) => (
                                <Chip
                                    key={id}
                                    label={id.substring(0, 8)}
                                    size="small"
                                    variant="outlined"
                                />
                            ))}
                        </Box>
                    )}
                </Alert>
            </Snackbar>

            <PlanSettingsWizard
                open={wizardOpen}
                onClose={() => setWizardOpen(false)}
                mode={wizardMode}
                versionId={wizardVersionId}
                onSaved={(_versionId, action) => {
                    if (action === 'save' || action === 'save-and-build') {
                        void handleRecalculate();
                    }
                }}
            />
        </Box>
    );
};

export default GanttPage;