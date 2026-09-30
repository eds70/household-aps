// frontend/src/components/gantt/GanttToolbar.tsx
/**
 * Верхняя панель (тулбар) диаграммы Ганта (Итерация 13.17 + 13.19).
 *
 * Итерация 13.19: кнопка «Пересчитать» становится активной ТОЛЬКО
 * если planDirty === true (есть несохранённые изменения,
 * влияющие на расчёт).
 */
import React from 'react';
import {Chip, Divider, IconButton, InputAdornment, Paper, TextField, Tooltip, Typography,} from '@mui/material';
import {
    AccountTree as AccountTreeIcon,
    ArrowBack as ArrowBackIcon,
    ArrowForward as ArrowForwardIcon,
    Autorenew as RecalcIcon,
    Download as DownloadIcon,
    FilterAlt as FilterAltIcon,
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

export interface GanttToolbarProps {
    // Статистика
    totalTasks: number;
    filteredCount: number;
    makespanHours: number;
    equipmentCount: number;
    hasActiveFilters: boolean;

    // Readonly
    isReadOnly: boolean;
    currentPlanName: string;

    // Поиск
    searchQuery: string;
    onSearchChange: (value: string) => void;

    // Фильтры
    onToggleFilters: (event: React.MouseEvent<HTMLElement>) => void;

    // Навигация
    onPanLeft: () => void;
    onPanRight: () => void;
    onZoomIn: () => void;
    onZoomOut: () => void;
    onFitAll: () => void;
    onGoToToday: () => void;

    // Миникарта
    showMinimap: boolean;
    onToggleMinimap: () => void;

    // Связи
    showDependencies: boolean;
    onToggleDependencies: () => void;
    showAllDependencies: boolean;
    onToggleAllDependencies: () => void;

    // Действия
    onOpenAudit: () => void;
    onRefresh: () => void;
    onExport: () => void;

    // Итерация 13.17 (9e): пересчёт плана
    onRecalculate?: () => void;
    recalculating?: boolean;

    /**
     * Итерация 13.19: есть ли несохранённые изменения, влияющие
     * на расчёт. Кнопка «Пересчитать» активна только при true.
     */
    planDirty: boolean;
}

const GanttToolbar: React.FC<GanttToolbarProps> = ({
                                                       totalTasks,
                                                       filteredCount,
                                                       makespanHours,
                                                       equipmentCount,
                                                       hasActiveFilters,
                                                       isReadOnly,
                                                       currentPlanName,
                                                       searchQuery,
                                                       onSearchChange,
                                                       onToggleFilters,
                                                       onPanLeft,
                                                       onPanRight,
                                                       onZoomIn,
                                                       onZoomOut,
                                                       onFitAll,
                                                       onGoToToday,
                                                       showMinimap,
                                                       onToggleMinimap,
                                                       showDependencies,
                                                       onToggleDependencies,
                                                       showAllDependencies,
                                                       onToggleAllDependencies,
                                                       onOpenAudit,
                                                       onRefresh,
                                                       onExport,
                                                       onRecalculate,
                                                       recalculating = false,
                                                       planDirty,
                                                   }) => {
    return (
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
                sx={{
                    fontWeight: 600,
                    fontSize: '1.1rem',
                    mr: 1,
                    whiteSpace: 'nowrap',
                }}
            >
                📊 Диаграмма Ганта
            </Typography>

            <Tooltip
                title={
                    hasActiveFilters
                        ? `Показано: ${filteredCount} из ${totalTasks}`
                        : 'Всего задач'
                }
            >
                <Chip
                    label={
                        hasActiveFilters
                            ? `${filteredCount}/${totalTasks}`
                            : `${totalTasks}`
                    }
                    size="small"
                    color={hasActiveFilters ? 'warning' : 'primary'}
                    variant="outlined"
                />
            </Tooltip>

            <Tooltip title="Makespan (часы)">
                <Chip
                    label={`${makespanHours.toFixed(1)} ч`}
                    size="small"
                    variant="outlined"
                />
            </Tooltip>

            <Tooltip title="Количество единиц оборудования">
                <Chip
                    label={`${equipmentCount} об.`}
                    size="small"
                    variant="outlined"
                />
            </Tooltip>

            {isReadOnly && (
                <Tooltip title={`Режим просмотра: ${currentPlanName}`}>
                    <Chip
                        icon={<LockIcon fontSize="small" />}
                        label="Просмотр"
                        size="small"
                        color="info"
                        variant="filled"
                    />
                </Tooltip>
            )}

            {/* Поиск */}
            <TextField
                size="small"
                placeholder="Поиск..."
                value={searchQuery}
                onChange={(e) => onSearchChange(e.target.value)}
                sx={{ width: 200, ml: 'auto' }}
                slotProps={{
                    input: {
                        startAdornment: (
                            <InputAdornment position="start">
                                <SearchIcon fontSize="small" />
                            </InputAdornment>
                        ),
                    },
                }}
            />

            {/* Кнопка «Фильтры» */}
            <Tooltip title="Фильтры">
                <IconButton
                    size="small"
                    onClick={onToggleFilters}
                    color={hasActiveFilters ? 'warning' : 'default'}
                >
                    <FilterAltIcon />
                </IconButton>
            </Tooltip>

            {/* Итерация 13.17 (9e): кнопка «Пересчитать» */}
            {/* Итерация 13.19: активна только при planDirty */}
            {isReadOnly && onRecalculate && (
                <Tooltip
                    title={
                        planDirty
                            ? 'Пересчитать план с учётом изменений'
                            : 'Нет изменений для пересчёта. Измените справочники, заказы, настройки или передвиньте задачу.'
                    }
                >
                    <span>
                        <IconButton
                            size="small"
                            onClick={onRecalculate}
                            color={planDirty ? 'primary' : 'default'}
                            disabled={recalculating || !planDirty}
                        >
                            <RecalcIcon />
                        </IconButton>
                    </span>
                </Tooltip>
            )}

            {/* Панель навигации */}
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
                <Tooltip title="Сдвинуть влево">
                    <IconButton size="small" onClick={onPanLeft}>
                        <ArrowBackIcon fontSize="small" />
                    </IconButton>
                </Tooltip>
                <Tooltip title="Сдвинуть вправо">
                    <IconButton size="small" onClick={onPanRight}>
                        <ArrowForwardIcon fontSize="small" />
                    </IconButton>
                </Tooltip>
                <Divider orientation="vertical" flexItem sx={{ mx: 0.25 }} />
                <Tooltip title="Приблизить">
                    <IconButton size="small" onClick={onZoomIn}>
                        <ZoomInIcon fontSize="small" />
                    </IconButton>
                </Tooltip>
                <Tooltip title="Отдалить">
                    <IconButton size="small" onClick={onZoomOut}>
                        <ZoomOutIcon fontSize="small" />
                    </IconButton>
                </Tooltip>
                <Divider orientation="vertical" flexItem sx={{ mx: 0.25 }} />
                <Tooltip title="Показать весь план">
                    <IconButton size="small" onClick={onFitAll}>
                        <FitScreenIcon fontSize="small" />
                    </IconButton>
                </Tooltip>
                <Tooltip title="Перейти к сегодня">
                    <IconButton size="small" onClick={onGoToToday}>
                        <TodayIcon fontSize="small" />
                    </IconButton>
                </Tooltip>
            </Paper>

            {/* Миникарта */}
            <Tooltip
                title={
                    showMinimap
                        ? 'Скрыть навигатор timeline'
                        : 'Показать навигатор timeline'
                }
            >
                <IconButton
                    size="small"
                    onClick={onToggleMinimap}
                    color={showMinimap ? 'primary' : 'default'}
                >
                    <MapIcon />
                </IconButton>
            </Tooltip>

            {/* Связи */}
            <Tooltip
                title={
                    showDependencies
                        ? showAllDependencies
                            ? 'Скрыть связи между задачами'
                            : 'Связи показываются при наведении на задачу'
                        : 'Показать связи между задачами'
                }
            >
                <IconButton
                    size="small"
                    onClick={onToggleDependencies}
                    color={showDependencies ? 'primary' : 'default'}
                >
                    <AccountTreeIcon />
                </IconButton>
            </Tooltip>

            {showDependencies && (
                <Tooltip
                    title={
                        showAllDependencies
                            ? 'Переключить в режим "по наведению"'
                            : 'Показать все связи (с задержкой при pan)'
                    }
                >
                    <Chip
                        size="small"
                        label={showAllDependencies ? '🔗 Все' : '📎 По hover'}
                        color={showAllDependencies ? 'secondary' : 'default'}
                        variant={showAllDependencies ? 'filled' : 'outlined'}
                        onClick={onToggleAllDependencies}
                        sx={{ cursor: 'pointer', fontSize: '0.7rem' }}
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

            <Divider orientation="vertical" flexItem sx={{ mx: 0.25 }} />

            {/* Действия */}
            <Tooltip title="История изменений">
                <IconButton size="small" onClick={onOpenAudit}>
                    <HistoryIcon />
                </IconButton>
            </Tooltip>
            <Tooltip title="Обновить">
                <IconButton size="small" onClick={onRefresh}>
                    <RefreshIcon />
                </IconButton>
            </Tooltip>
            <Tooltip title="Экспорт в Excel">
                <IconButton size="small" color="success" onClick={onExport}>
                    <DownloadIcon />
                </IconButton>
            </Tooltip>
        </Paper>
    );
};

export default GanttToolbar;