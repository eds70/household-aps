// frontend/src/components/gantt/GanttToolbar.tsx
/**
 * Верхняя панель (тулбар) диаграммы Ганта
 * (Итерация 13.17 + 13.19 + 14.1 + 14.2 + 15.2).
 *
 * Итерация 13.19: кнопка «Пересчитать» становится активной ТОЛЬКО
 * если planDirty === true (есть несохранённые изменения,
 * влияющие на расчёт).
 *
 * Итерация 14.1:
 *   - Добавлен переключатель режима группировки
 *     («По оборудованию» / «По партиям»).
 *   - Добавлен чекбокс «Скобки партий» (только в режиме 'equipment').
 *   - Добавлен чип с количеством партий на диаграмме.
 *
 * Итерация 14.2:
 *   - Добавлен ToggleButtonGroup «🔒 Просмотр / ✏️ Редактирование»,
 *     позволяющий переключать режим редактирования прямо на Ганте,
 *     не закрывая план.
 *   - Кнопка «Пересчитать» теперь рендерится всегда, когда передан
 *     onRecalculate (не только в readonly-режиме).
 *
 * Итерация 15.2 (НОВОЕ):
 *   - Рядом с переключателем 🔒/✏️ добавлена контекстная подсказка
 *     <Hint id="gantt.edit_mode"/> (Popover с markdown-телом).
 *   - Рядом с селектом «Группировка» добавлена подсказка
 *     <Hint id="gantt.brackets"/> — про скобки партий.
 *   - Рядом с кнопкой «Пересчитать» добавлена подсказка
 *     <Hint id="planning.recalc"/> — про условия активации кнопки.
 */
import React from 'react';
import {
    Checkbox,
    Chip,
    Divider,
    FormControl,
    FormControlLabel,
    IconButton,
    InputAdornment,
    InputLabel,
    MenuItem,
    Paper,
    Select,
    TextField,
    ToggleButton,
    ToggleButtonGroup,
    Tooltip,
    Typography,
} from '@mui/material';
import {
    AccountTree as AccountTreeIcon,
    ArrowBack as ArrowBackIcon,
    ArrowForward as ArrowForwardIcon,
    Autorenew as RecalcIcon,
    Download as DownloadIcon,
    Edit as EditIcon,
    FilterAlt as FilterAltIcon,
    FitScreen as FitScreenIcon,
    History as HistoryIcon,
    Lock as LockIcon,
    Map as MapIcon,
    Refresh as RefreshIcon,
    Search as SearchIcon,
    Today as TodayIcon,
    ViewStream as ViewStreamIcon,
    ZoomIn as ZoomInIcon,
    ZoomOut as ZoomOutIcon,
} from '@mui/icons-material';
import type {GroupByMode} from '../../types';
import Hint from '../help/Hint';

export interface GanttToolbarProps {
    // Статистика
    totalTasks: number;
    filteredCount: number;
    makespanHours: number;
    equipmentCount: number;
    hasActiveFilters: boolean;

    /**
     * Итерация 14.1: количество партий на диаграмме.
     * Показывается в чипе рядом с оборудованием.
     */
    batchCount: number;

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

    // ==========================================
    // ИТЕРАЦИЯ 14.1: РЕЖИМЫ ОТОБРАЖЕНИЯ
    // ==========================================

    /**
     * Режим группировки строк.
     *   - 'equipment' — по оборудованию.
     *   - 'batch' — по партиям.
     */
    groupByMode: GroupByMode;
    onGroupByModeChange: (mode: GroupByMode) => void;

    /**
     * Показывать ли фантомные скобки партий
     * (доступно только в режиме 'equipment').
     */
    showBatchBrackets: boolean;
    onToggleBatchBrackets: () => void;

    // ==========================================
    // ИТЕРАЦИЯ 14.2: РЕЖИМ РЕДАКТИРОВАНИЯ
    // ==========================================

    /**
     * Локальный режим редактирования.
     * Если true — задачи можно таскать/ресайзить.
     * Если false — readonly.
     */
    localEditMode: boolean;

    /** Колбэк переключения режима. */
    onLocalEditModeChange: (value: boolean) => void;
}

const GanttToolbar: React.FC<GanttToolbarProps> = ({
                                                       totalTasks,
                                                       filteredCount,
                                                       makespanHours,
                                                       equipmentCount,
                                                       hasActiveFilters,
                                                       batchCount,
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
                                                       groupByMode,
                                                       onGroupByModeChange,
                                                       showBatchBrackets,
                                                       onToggleBatchBrackets,
                                                       localEditMode,
                                                       onLocalEditModeChange,
                                                   }) => {
    // В режиме 'batch' скобки партий недоступны — они там не нужны
    const bracketsAvailable = groupByMode === 'equipment';

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

            {/* ==========================================
                ИТЕРАЦИЯ 14.2 (compact): Переключатель режима.
                Только иконки — текст в tooltip.
            ========================================== */}
            <ToggleButtonGroup
                size="small"
                value={localEditMode ? 'edit' : 'view'}
                exclusive
                onChange={(_, value) => {
                    if (value !== null) {
                        onLocalEditModeChange(value === 'edit');
                    }
                }}
                sx={{
                    ml: 0.5,
                    // Компактные кнопки: 28×28 вместо 40×40 (MUI default)
                    '& .MuiToggleButton-root': {
                        padding: '4px 6px',
                        minWidth: 32,
                        borderColor: '#bdc3c7',
                        '&.Mui-selected': {
                            backgroundColor: '#3498db',
                            color: '#ffffff',
                            '&:hover': {
                                backgroundColor: '#2980b9',
                            },
                        },
                    },
                }}
            >
                <Tooltip title="Режим просмотра. Переключите в «Редактирование», чтобы двигать задачи." arrow>
                    <ToggleButton value="view" aria-label="Режим просмотра">
                        <LockIcon sx={{fontSize: 16}} />
                    </ToggleButton>
                </Tooltip>
                <Tooltip title="Режим редактирования. Задачи можно перетаскивать, изменения сохранятся после «Пересчитать»." arrow>
                    <ToggleButton value="edit" aria-label="Режим редактирования">
                        <EditIcon sx={{fontSize: 16}} />
                    </ToggleButton>
                </Tooltip>
            </ToggleButtonGroup>

            {/* ==========================================
                ИТЕРАЦИЯ 15.2: контекстная подсказка
                про режим редактирования.
            ========================================== */}
            <Hint id="gantt.edit_mode" size="small" />

            <Divider orientation="vertical" flexItem sx={{mx: 0.5}} />

            {/* ==========================================
                ИТЕРАЦИЯ 14.1: Переключатель режима группировки
            ========================================== */}
            <FormControl
                size="small"
                variant="outlined"
                sx={{minWidth: 170}}
            >
                <InputLabel id="gantt-group-by-label">Группировка</InputLabel>
                <Select
                    labelId="gantt-group-by-label"
                    value={groupByMode}
                    label="Группировка"
                    variant="outlined"
                    onChange={(e) =>
                        onGroupByModeChange(e.target.value as GroupByMode)
                    }
                    startAdornment={
                        <InputAdornment position="start" sx={{ml: 0.5}}>
                            <ViewStreamIcon fontSize="small"/>
                        </InputAdornment>
                    }
                >
                    <MenuItem value="equipment">
                        По оборудованию
                    </MenuItem>
                    <MenuItem value="batch">
                        По партиям
                    </MenuItem>
                </Select>
            </FormControl>

            {/* ==========================================
                ИТЕРАЦИЯ 15.2: контекстная подсказка
                про скобки партий.
            ========================================== */}
            <Hint id="gantt.brackets" size="small" />

            {/* ==========================================
                ИТЕРАЦИЯ 14.1: Чекбокс «Скобки партий»
                (только в режиме 'equipment')
            ========================================== */}
            {bracketsAvailable && (
                <Tooltip
                    title={
                        showBatchBrackets
                            ? 'Скрыть цветные рамки вокруг партий'
                            : 'Показать цветные рамки вокруг партий (помогают видеть партию как целое)'
                    }
                >
                    <FormControlLabel
                        control={
                            <Checkbox
                                size="small"
                                checked={showBatchBrackets}
                                onChange={onToggleBatchBrackets}
                            />
                        }
                        label={
                            <Typography
                                variant="caption"
                                sx={{userSelect: 'none'}}
                            >
                                Скобки партий
                            </Typography>
                        }
                    />
                </Tooltip>
            )}

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

            {/* ==========================================
                ИТЕРАЦИЯ 14.1: Чип с количеством партий
            ========================================== */}
            {batchCount > 0 && (
                <Tooltip title="Количество партий на диаграмме">
                    <Chip
                        label={`${batchCount} парт.`}
                        size="small"
                        variant="outlined"
                        sx={{borderColor: '#9b59b6', color: '#8e44ad'}}
                    />
                </Tooltip>
            )}

            {/* Поиск */}
            <TextField
                size="small"
                placeholder="Поиск..."
                value={searchQuery}
                onChange={(e) => onSearchChange(e.target.value)}
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

            {/* Кнопка «Фильтры» */}
            <Tooltip title="Фильтры">
                <IconButton
                    size="small"
                    onClick={onToggleFilters}
                    color={hasActiveFilters ? 'warning' : 'default'}
                >
                    <FilterAltIcon/>
                </IconButton>
            </Tooltip>

            {/* ==========================================
                ИТЕРАЦИЯ 14.2: кнопка «Пересчитать»
                Рендерится всегда, когда передан onRecalculate.
                Активна, когда planDirty === true.

                ИТЕРАЦИЯ 15.2: рядом с кнопкой — подсказка
                <Hint id="planning.recalc"/>.
            ========================================== */}
            {onRecalculate && (
                <>
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
                                <RecalcIcon/>
                            </IconButton>
                        </span>
                    </Tooltip>
                    <Hint id="planning.recalc" size="small" />
                </>
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
                        <ArrowBackIcon fontSize="small"/>
                    </IconButton>
                </Tooltip>
                <Tooltip title="Сдвинуть вправо">
                    <IconButton size="small" onClick={onPanRight}>
                        <ArrowForwardIcon fontSize="small"/>
                    </IconButton>
                </Tooltip>
                <Divider orientation="vertical" flexItem sx={{mx: 0.25}}/>
                <Tooltip title="Приблизить">
                    <IconButton size="small" onClick={onZoomIn}>
                        <ZoomInIcon fontSize="small"/>
                    </IconButton>
                </Tooltip>
                <Tooltip title="Отдалить">
                    <IconButton size="small" onClick={onZoomOut}>
                        <ZoomOutIcon fontSize="small"/>
                    </IconButton>
                </Tooltip>
                <Divider orientation="vertical" flexItem sx={{mx: 0.25}}/>
                <Tooltip title="Показать весь план">
                    <IconButton size="small" onClick={onFitAll}>
                        <FitScreenIcon fontSize="small"/>
                    </IconButton>
                </Tooltip>
                <Tooltip title="Перейти к сегодня">
                    <IconButton size="small" onClick={onGoToToday}>
                        <TodayIcon fontSize="small"/>
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
                    <MapIcon/>
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
                    <AccountTreeIcon/>
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

            {/* Действия */}
            <Tooltip title="История изменений">
                <IconButton size="small" onClick={onOpenAudit}>
                    <HistoryIcon/>
                </IconButton>
            </Tooltip>
            <Tooltip title="Обновить">
                <IconButton size="small" onClick={onRefresh}>
                    <RefreshIcon/>
                </IconButton>
            </Tooltip>
            <Tooltip title="Экспорт в Excel">
                <IconButton size="small" color="success" onClick={onExport}>
                    <DownloadIcon/>
                </IconButton>
            </Tooltip>
        </Paper>
    );
};

export default GanttToolbar;