// frontend/src/components/gantt/GanttFiltersBar.tsx
/**
 * Панель активных фильтров на Ганте (Итерация 13.17 + 13.18).
 *
 * Показывает чипы со всеми активными фильтрами:
 *  - 📌 Партия
 *  - Оборудование
 *  - Продукты
 *  - 🔒 Только заблокированные
 *  - ⏳ Только замедленное охлаждение
 *  - 📷 Только не промаркированные
 *  - 📌 Только закреплённые (Итерация 13.18)
 *
 * Плюс кнопка «Сбросить».
 *
 * Рендерится только если hasActiveFilters === true.
 */
import React from 'react';
import {Button, Chip, Paper, Typography} from '@mui/material';
import {FilterAltOff as FilterAltOffIcon} from '@mui/icons-material';

export interface GanttFiltersBarProps {
    // Активен ли хотя бы один фильтр
    hasActiveFilters: boolean;

    // Значения фильтров
    batchFilter: string | null;
    equipmentFilter: string[];
    productFilter: string[];
    showOnlyBlocked: boolean;
    showOnlySlowCooling: boolean;
    showOnlyCzIncomplete: boolean;
    /** Итерация 13.18: фильтр «только закреплённые». */
    showOnlyPinned: boolean;

    // Колбэки удаления конкретного фильтра
    onClearBatchFilter: () => void;
    onClearEquipmentFilter: () => void;
    onClearProductFilter: () => void;
    onClearOnlyBlocked: () => void;
    onClearOnlySlowCooling: () => void;
    onClearOnlyCzIncomplete: () => void;
    /** Итерация 13.18: сброс фильтра «только закреплённые». */
    onClearOnlyPinned: () => void;

    // Сброс всех фильтров
    onResetAll: () => void;
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
                                                         }) => {
    if (!hasActiveFilters) return null;

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
                bgcolor: '#fff8e1',
            }}
        >
            <Typography
                variant="caption"
                sx={{alignSelf: 'center', mr: 1, fontWeight: 600}}
            >
                Фильтры:
            </Typography>

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

            {/* Итерация 13.18: чип «только закреплённые» */}
            {showOnlyPinned && (
                <Chip
                    label="📌 Только закреплённые"
                    size="small"
                    color="primary"
                    onDelete={onClearOnlyPinned}
                />
            )}

            <Button
                size="small"
                onClick={onResetAll}
                startIcon={<FilterAltOffIcon/>}
            >
                Сбросить
            </Button>
        </Paper>
    );
};

export default GanttFiltersBar;