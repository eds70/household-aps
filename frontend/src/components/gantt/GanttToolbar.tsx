// frontend/src/components/gantt/GanttToolbar.tsx
import React from 'react';
import {
    AppBar,
    Box,
    Chip,
    Divider,
    IconButton,
    InputAdornment,
    TextField,
    ToggleButton,
    ToggleButtonGroup,
    Toolbar,
    Tooltip,
    Typography,
} from '@mui/material';
import {
    ArrowBack,
    ArrowForward,
    CenterFocusStrong,
    FileDownload,
    FilterList,
    Lock,
    LockOpen,
    PlayArrow,
    Refresh,
    Search,
    Settings as SettingsIcon,
    Today,
    ViewStream as ViewStreamIcon,
    Visibility as VisibilityIcon,
    ZoomIn,
    ZoomOut,
} from '@mui/icons-material';
import type {GroupByMode} from '../../types';

interface GanttToolbarProps {
    totalTasks: number;
    filteredCount: number;
    makespanHours: number;
    equipmentCount: number;
    batchCount: number;

    hasActiveFilters: boolean;
    searchQuery: string;

    onSearchChange: (value: string) => void;
    onToggleFilters: (event: React.MouseEvent<HTMLElement>) => void;

    onPanLeft: () => void;
    onPanRight: () => void;
    onZoomIn: () => void;
    onZoomOut: () => void;
    onFitAll: () => void;
    onGoToToday: () => void;

    onOpenAudit: () => void;
    onRefresh: () => void;
    onExport: () => void;

    onRecalculate?: () => void;
    recalculating: boolean;
    planDirty: boolean;

    groupByMode: GroupByMode;
    onGroupByModeChange: (mode: GroupByMode) => void;

    // Скобки партий
    showBatchBrackets: boolean;
    onToggleBatchBrackets: () => void;

    localEditMode: boolean;
    onLocalEditModeChange: (value: boolean) => void;

    onOpenDisplaySettings: () => void;
}

const GanttToolbar: React.FC<GanttToolbarProps> = ({
                                                       totalTasks,
                                                       filteredCount,
                                                       makespanHours,
                                                       equipmentCount,
                                                       batchCount,
                                                       hasActiveFilters,
                                                       searchQuery,
                                                       onSearchChange,
                                                       onToggleFilters,
                                                       onPanLeft,
                                                       onPanRight,
                                                       onZoomIn,
                                                       onZoomOut,
                                                       onFitAll,
                                                       onGoToToday,
                                                       onOpenAudit,
                                                       onRefresh,
                                                       onExport,
                                                       onRecalculate,
                                                       recalculating,
                                                       planDirty,
                                                       groupByMode,
                                                       onGroupByModeChange,
                                                       showBatchBrackets,
                                                       onToggleBatchBrackets,
                                                       localEditMode,
                                                       onLocalEditModeChange,
                                                       onOpenDisplaySettings,
                                                   }) => {
    return (
        <AppBar
            position="static"
            color="default"
            elevation={1}
            sx={{ borderBottom: '1px solid #e0e0e0', flexShrink: 0, bgcolor: '#fff' }}
        >
            <Toolbar variant="dense" sx={{ gap: 1, minHeight: 48 }}>
                <Typography variant="h6" sx={{ fontWeight: 600, fontSize: '1rem', mr: 2 }}>
                    Диаграмма Ганта
                </Typography>

                {/* Режим редактирования */}
                <Tooltip title={localEditMode ? 'Режим редактирования' : 'Режим просмотра'}>
                    <IconButton size="small" onClick={() => onLocalEditModeChange(!localEditMode)} color={localEditMode ? 'primary' : 'default'}>
                        {localEditMode ? <LockOpen fontSize="small" /> : <Lock fontSize="small" />}
                    </IconButton>
                </Tooltip>

                <Divider orientation="vertical" flexItem sx={{ mx: 1 }} />

                {/* Группировка */}
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Typography variant="caption" color="text.secondary">Группировка</Typography>
                    <ToggleButtonGroup
                        size="small"
                        exclusive
                        value={groupByMode}
                        onChange={(_, val) => val && onGroupByModeChange(val)}
                        sx={{ height: 28 }}
                    >
                        <ToggleButton value="equipment">По оборудованию</ToggleButton>
                        <ToggleButton value="batch">По партиям</ToggleButton>
                    </ToggleButtonGroup>
                </Box>

                {/* Скобки партий (только в режиме "По оборудованию") */}
                {groupByMode === 'equipment' && (
                    <Tooltip title={showBatchBrackets ? 'Скрыть скобки партий' : 'Показать скобки партий'}>
                        <IconButton
                            size="small"
                            onClick={onToggleBatchBrackets}
                            color={showBatchBrackets ? 'secondary' : 'default'}
                        >
                            <ViewStreamIcon fontSize="small" />
                        </IconButton>
                    </Tooltip>
                )}

                <Divider orientation="vertical" flexItem sx={{ mx: 1 }} />

                {/* Статистика */}
                <Chip size="small" label={`${totalTasks} задач`} variant="outlined" />
                {filteredCount !== totalTasks && <Chip size="small" label={`${filteredCount} показ.`} color="primary" variant="outlined" />}
                <Chip size="small" label={`${makespanHours.toFixed(1)} ч`} variant="outlined" />
                <Chip size="small" label={`${equipmentCount} ед.`} variant="outlined" />
                <Chip size="small" label={`${batchCount} парт.`} color="secondary" variant="outlined" />

                <Box sx={{ flexGrow: 1 }} />

                {/* Поиск */}
                <TextField
                    size="small"
                    placeholder="Поиск..."
                    value={searchQuery}
                    onChange={(e) => onSearchChange(e.target.value)}
                    slotProps={{
                        input: {
                            startAdornment: (
                                <InputAdornment position="start">
                                    <Search fontSize="small" />
                                </InputAdornment>
                            ),
                        }
                    }}
                    sx={{ width: 200, '& .MuiInputBase-root': { height: 32 } }}
                />

                <Tooltip title="Фильтры">
                    <IconButton size="small" onClick={onToggleFilters} color={hasActiveFilters ? 'primary' : 'default'}>
                        <FilterList fontSize="small" />
                    </IconButton>
                </Tooltip>

                <Divider orientation="vertical" flexItem sx={{ mx: 1 }} />

                {/* Навигация */}
                <Tooltip title="Влево"><IconButton size="small" onClick={onPanLeft}><ArrowBack fontSize="small" /></IconButton></Tooltip>
                <Tooltip title="Вправо"><IconButton size="small" onClick={onPanRight}><ArrowForward fontSize="small" /></IconButton></Tooltip>
                <Tooltip title="Приблизить"><IconButton size="small" onClick={onZoomIn}><ZoomIn fontSize="small" /></IconButton></Tooltip>
                <Tooltip title="Отдалить"><IconButton size="small" onClick={onZoomOut}><ZoomOut fontSize="small" /></IconButton></Tooltip>
                <Tooltip title="Показать весь план"><IconButton size="small" onClick={onFitAll}><CenterFocusStrong fontSize="small" /></IconButton></Tooltip>
                <Tooltip title="Сегодня"><IconButton size="small" onClick={onGoToToday}><Today fontSize="small" /></IconButton></Tooltip>

                <Divider orientation="vertical" flexItem sx={{ mx: 1 }} />

                {/* Настройки отображения */}
                <Tooltip title="Настройки отображения (Связи, элементы, миникарта)">
                    <IconButton size="small" onClick={onOpenDisplaySettings}>
                        <SettingsIcon fontSize="small" />
                    </IconButton>
                </Tooltip>

                <Tooltip title="Аудит">
                    <IconButton size="small" onClick={onOpenAudit}><VisibilityIcon fontSize="small" /></IconButton>
                </Tooltip>

                <Tooltip title="Обновить">
                    <IconButton size="small" onClick={onRefresh}><Refresh fontSize="small" /></IconButton>
                </Tooltip>

                <Tooltip title="Экспорт">
                    <IconButton size="small" onClick={onExport}><FileDownload fontSize="small" /></IconButton>
                </Tooltip>

                {onRecalculate && (
                    <Tooltip title={planDirty ? 'Есть несохраненные изменения. Пересчитать?' : 'Пересчитать план'}>
                        <span>
                            <IconButton
                                size="small"
                                color={planDirty ? 'warning' : 'primary'}
                                onClick={onRecalculate}
                                disabled={recalculating}
                            >
                                <PlayArrow fontSize="small" />
                            </IconButton>
                        </span>
                    </Tooltip>
                )}
            </Toolbar>
        </AppBar>
    );
};

export default GanttToolbar;