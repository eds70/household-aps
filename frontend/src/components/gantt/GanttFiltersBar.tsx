// frontend/src/components/gantt/GanttFiltersBar.tsx
/**
 * Панель активных фильтров на Ганте.
 *
 * Показывает чипы со всеми активными фильтрами.
 *
 * Итерация 14.1: добавлен чип активного режима группировки.
 *
 * Итерация 45: удален чип «Скобки партий скрыты»
 * (по просьбе пользователя для разгрузки интерфейса).
 *
 * Итерация 49: добавлен onEnableBatchBrackets (для быстрого включения скобок).
 */
import React from 'react';
import {Button, Chip, Paper, Typography} from '@mui/material';
import {FilterAltOff as FilterAltOffIcon, ViewStream as ViewStreamIcon,} from '@mui/icons-material';
import type {GroupByMode} from '../../types';

export interface GanttFiltersBarProps {
    hasActiveFilters: boolean;

    batchFilter: string | null;
    equipmentFilter: string[];
    productFilter: string[];
    showOnlyBlocked: boolean;
    showOnlySlowCooling: boolean;
    showOnlyCzIncomplete: boolean;
    showOnlyPinned: boolean;

    onClearBatchFilter: () => void;
    onClearEquipmentFilter: () => void;
    onClearProductFilter: () => void;
    onClearOnlyBlocked: () => void;
    onClearOnlySlowCooling: () => void;
    onClearOnlyCzIncomplete: () => void;
    onClearOnlyPinned: () => void;

    onResetAll: () => void;

    groupByMode: GroupByMode;
    showBatchBrackets: boolean;
    onResetGroupByMode: () => void;
    onEnableBatchBrackets: () => void;
}

const GanttFiltersBar: React.FC<GanttFiltersBarProps> = ({
                                                             hasActiveFilters,
                                                             batchFilter,
                                                             equipmentFilter,
                                                             productFilter,
                                                             showOnlyBlocked,
                                                             showOnlySlowCooling,
                                                             showOnlyCzIncomplete,
                                                             showOnlyPinned,
                                                             onClearBatchFilter,
                                                             onClearEquipmentFilter,
                                                             onClearProductFilter,
                                                             onClearOnlyBlocked,
                                                             onClearOnlySlowCooling,
                                                             onClearOnlyCzIncomplete,
                                                             onClearOnlyPinned,
                                                             onResetAll,
                                                             groupByMode,
                                                             showBatchBrackets,
                                                             onResetGroupByMode,
                                                             onEnableBatchBrackets,
                                                         }) => {
    const isBatchMode = groupByMode === 'batch';
    const hasModeBadges = isBatchMode;

    // Если нет ни фильтров, ни нестандартного режима — не показываем панель
    if (!hasActiveFilters && !hasModeBadges) return null;

    return (
        <Paper
            elevation={0}
            sx={{
                display: 'flex',
                gap: 0.5,
                mb: 1,
                p: 0.5,
                flexShrink: 0,
                flexWrap: 'wrap',
                alignItems: 'center',
                bgcolor: '#fff8e1',
            }}
        >
            <Typography
                variant="caption"
                sx={{alignSelf: 'center', mr: 1, fontWeight: 600}}
            >
                {hasActiveFilters ? 'Фильтры:' : 'Отображение:'}
            </Typography>

            {/* Чип активного режима группировки */}
            {isBatchMode && (
                <Chip
                    icon={<ViewStreamIcon fontSize="small" />}
                    label="Группировка: По партиям"
                    size="small"
                    color="secondary"
                    onDelete={onResetGroupByMode}
                    deleteIcon={<FilterAltOffIcon />}
                    title="Вернуть группировку по оборудованию"
                />
            )}

            {!showBatchBrackets && (
                <Chip
                    label="Скобки партий скрыты"
                    size="small"
                    variant="outlined"
                    onClick={onEnableBatchBrackets}
                    title="Показать скобки партий"
                    sx={{ cursor: 'pointer' }}
                />
            )}

            {batchFilter && (
                <Chip
                    label={`📌 Партия: ${batchFilter.substring(0, 8)}`}
                    size="small"
                    color="secondary"
                    onDelete={onClearBatchFilter}
                />
            )}

            {equipmentFilter.length > 0 && (
                <Chip
                    label={`Оборуд.: ${equipmentFilter.join(', ')}`}
                    size="small"
                    onDelete={onClearEquipmentFilter}
                />
            )}

            {productFilter.length > 0 && (
                <Chip
                    label={`Продукты: ${productFilter.join(', ')}`}
                    size="small"
                    onDelete={onClearProductFilter}
                />
            )}

            {showOnlyBlocked && (
                <Chip
                    label="🔒 Только заблокированные"
                    size="small"
                    color="error"
                    onDelete={onClearOnlyBlocked}
                />
            )}

            {showOnlySlowCooling && (
                <Chip
                    label="⏳ Только замедленное охлаждение"
                    size="small"
                    color="warning"
                    onDelete={onClearOnlySlowCooling}
                />
            )}

            {showOnlyCzIncomplete && (
                <Chip
                    label="📷 Только не промаркированные"
                    size="small"
                    color="info"
                    onDelete={onClearOnlyCzIncomplete}
                />
            )}

            {showOnlyPinned && (
                <Chip
                    label="📌 Только закреплённые"
                    size="small"
                    color="primary"
                    onDelete={onClearOnlyPinned}
                />
            )}

            {hasActiveFilters && (
                <Button
                    size="small"
                    onClick={onResetAll}
                    startIcon={<FilterAltOffIcon/>}
                >
                    Сбросить
                </Button>
            )}
        </Paper>
    );
};

export default GanttFiltersBar;