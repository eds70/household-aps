// frontend/src/components/gantt/GanttFiltersBar.tsx
/**
 * Панель активных фильтров на Ганте
 * (Итерация 13.17 + 13.18 + 14.1).
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
 * Итерация 14.1:
 *  - Добавлен чип активного режима группировки
 *    («По оборудованию» / «По партиям»), если он отличается
 *    от режима по умолчанию.
 *  - Добавлен чип «Скобки партий скрыты», если режим 'equipment',
 *    но showBatchBrackets = false.
 *  - Эти чипы помогают пользователю быстро понять, что
 *    диаграмма отображается не в «классическом» виде.
 *
 * Рендерится только если hasActiveFilters === true
 * ИЛИ активен нестандартный режим отображения.
 */
import React from 'react';
import {Button, Chip, Paper, Typography} from '@mui/material';
import {FilterAltOff as FilterAltOffIcon, ViewStream as ViewStreamIcon,} from '@mui/icons-material';
import type {GroupByMode} from '../../types';

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

    // ==========================================
    // ИТЕРАЦИЯ 14.1: РЕЖИМЫ ОТОБРАЖЕНИЯ
    // ==========================================

    /**
     * Текущий режим группировки.
     * Чип показывается, если режим отличается от 'equipment'.
     */
    groupByMode: GroupByMode;

    /**
     * Показывать ли скобки партий.
     * Чип «Скобки партий скрыты» показывается, если
     * groupByMode === 'equipment' и showBatchBrackets = false.
     */
    showBatchBrackets: boolean;

    /**
     * Колбэк сброса режима группировки к 'equipment'.
     * Вызывается при клике на чип «По партиям».
     */
    onResetGroupByMode: () => void;

    /**
     * Колбэк включения скобок партий.
     * Вызывается при клике на чип «Скобки партий скрыты».
     */
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
    // ==========================================
    // ИТЕРАЦИЯ 14.1: есть ли нестандартный режим отображения
    // ==========================================
    const isBatchMode = groupByMode === 'batch';
    const isBracketsHidden =
        groupByMode === 'equipment' && !showBatchBrackets;

    const hasModeBadges = isBatchMode || isBracketsHidden;

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

            {/* ==========================================
                ИТЕРАЦИЯ 14.1: чип активного режима группировки
                (показывается только в режиме 'batch')
            ========================================== */}
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

            {/* ==========================================
                ИТЕРАЦИЯ 14.1: чип «Скобки партий скрыты»
                (только в режиме 'equipment')
            ========================================== */}
            {isBracketsHidden && (
                <Chip
                    icon={<ViewStreamIcon fontSize="small" />}
                    label="Скобки партий скрыты"
                    size="small"
                    variant="outlined"
                    color="default"
                    onClick={onEnableBatchBrackets}
                    title="Показать цветные рамки вокруг партий"
                    sx={{cursor: 'pointer'}}
                />
            )}

            {/* ==========================================
                Фильтры (без изменений с 13.17 / 13.18)
            ========================================== */}

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

            {/* Кнопка сброса — только если есть активные фильтры */}
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