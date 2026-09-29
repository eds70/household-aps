// frontend/src/components/gantt/GanttFiltersPopover.tsx
/**
 * Popover с настройкой фильтров на Ганте (Итерация 13.17 + 13.18).
 *
 * Содержит:
 *  - Select: оборудование (мультивыбор).
 *  - Select: продукты (мультивыбор).
 *  - Select: партия (одиночный).
 *  - Checkbox: показывать замывки.
 *  - Checkbox: показывать выходные (фон).
 *  - Checkbox: показывать все связи (если showDependencies).
 *  - Checkbox: только заблокированные.
 *  - Checkbox: только замедленное охлаждение.
 *  - Checkbox: только не промаркированные.
 *  - Checkbox: только закреплённые (Итерация 13.18).
 *  - Кнопка «Сбросить все фильтры».
 */
import React from 'react';
import {
    Box,
    Button,
    Checkbox,
    Divider,
    FormControl,
    FormControlLabel,
    InputLabel,
    MenuItem,
    Popover,
    Select,
    Typography,
} from '@mui/material';
import {FilterAltOff as FilterAltOffIcon} from '@mui/icons-material';

export interface GanttFiltersPopoverProps {
    // Управление popover
    open: boolean;
    anchorEl: HTMLElement | null;
    onClose: () => void;

    // Данные для выпадающих списков
    equipmentList: string[];
    productList: string[];
    availableBatches: string[];

    // Значения фильтров
    equipmentFilter: string[];
    productFilter: string[];
    batchFilter: string | null;
    showSetups: boolean;
    showDowntimes: boolean;
    showAllDependencies: boolean;
    showOnlyBlocked: boolean;
    showOnlySlowCooling: boolean;
    showOnlyCzIncomplete: boolean;
    /** Итерация 13.18: показывать только закреплённые задачи. */
    showOnlyPinned: boolean;

    // Флаг: показывать ли блок «все связи» (зависит от showDependencies снаружи)
    showDependencies: boolean;

    // Активен ли хотя бы один фильтр (для disabled кнопки «Сбросить»)
    hasActiveFilters: boolean;

    // Колбэки изменения
    onEquipmentFilterChange: (value: string[]) => void;
    onProductFilterChange: (value: string[]) => void;
    onBatchFilterChange: (value: string | null) => void;
    onShowSetupsChange: (value: boolean) => void;
    onShowDowntimesChange: (value: boolean) => void;
    onShowAllDependenciesChange: (value: boolean) => void;
    onShowOnlyBlockedChange: (value: boolean) => void;
    onShowOnlySlowCoolingChange: (value: boolean) => void;
    onShowOnlyCzIncompleteChange: (value: boolean) => void;
    /** Итерация 13.18: изменение фильтра «только закреплённые». */
    onShowOnlyPinnedChange: (value: boolean) => void;

    // Сброс всех фильтров
    onResetAll: () => void;
}

const GanttFiltersPopover: React.FC<GanttFiltersPopoverProps> = ({
                                                                     open,
                                                                     anchorEl,
                                                                     onClose,
                                                                     equipmentList,
                                                                     productList,
                                                                     availableBatches,
                                                                     equipmentFilter,
                                                                     productFilter,
                                                                     batchFilter,
                                                                     showSetups,
                                                                     showDowntimes,
                                                                     showAllDependencies,
                                                                     showOnlyBlocked,
                                                                     showOnlySlowCooling,
                                                                     showOnlyCzIncomplete,
                                                                     showOnlyPinned,
                                                                     showDependencies,
                                                                     hasActiveFilters,
                                                                     onEquipmentFilterChange,
                                                                     onProductFilterChange,
                                                                     onBatchFilterChange,
                                                                     onShowSetupsChange,
                                                                     onShowDowntimesChange,
                                                                     onShowAllDependenciesChange,
                                                                     onShowOnlyBlockedChange,
                                                                     onShowOnlySlowCoolingChange,
                                                                     onShowOnlyCzIncompleteChange,
                                                                     onShowOnlyPinnedChange,
                                                                     onResetAll,
                                                                 }) => {
    return (
        <Popover
            open={open}
            anchorEl={anchorEl}
            onClose={onClose}
            anchorOrigin={{vertical: 'bottom', horizontal: 'right'}}
            transformOrigin={{vertical: 'top', horizontal: 'right'}}
        >
            <Box
                sx={{
                    p: 2,
                    minWidth: 340,
                    maxHeight: '80vh',
                    overflow: 'auto',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 2,
                }}
            >
                <Typography variant="subtitle2" sx={{fontWeight: 600}}>
                    🎛 Фильтры
                </Typography>

                <FormControl size="small" variant="outlined" fullWidth>
                    <InputLabel>Оборудование</InputLabel>
                    <Select
                        multiple
                        value={equipmentFilter}
                        onChange={(e) =>
                            onEquipmentFilterChange(
                                typeof e.target.value === 'string'
                                    ? e.target.value.split(',')
                                    : e.target.value,
                            )
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

                <FormControl size="small" variant="outlined" fullWidth>
                    <InputLabel>Продукты</InputLabel>
                    <Select
                        multiple
                        value={productFilter}
                        onChange={(e) =>
                            onProductFilterChange(
                                typeof e.target.value === 'string'
                                    ? e.target.value.split(',')
                                    : e.target.value,
                            )
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

                <FormControl size="small" variant="outlined" fullWidth>
                    <InputLabel>Партия</InputLabel>
                    <Select
                        value={batchFilter || ''}
                        label="Партия"
                        variant="outlined"
                        onChange={(e) =>
                            onBatchFilterChange(e.target.value || null)
                        }
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
                <Typography variant="caption" color="text.secondary">
                    Отображение:
                </Typography>

                <FormControlLabel
                    control={
                        <Checkbox
                            checked={showSetups}
                            onChange={(e) => onShowSetupsChange(e.target.checked)}
                            size="small"
                        />
                    }
                    label={<Typography variant="body2">🧼 Замывки</Typography>}
                />

                <FormControlLabel
                    control={
                        <Checkbox
                            checked={showDowntimes}
                            onChange={(e) => onShowDowntimesChange(e.target.checked)}
                            size="small"
                        />
                    }
                    label={<Typography variant="body2">📅 Выходные (фон)</Typography>}
                />

                {showDependencies && (
                    <FormControlLabel
                        control={
                            <Checkbox
                                checked={showAllDependencies}
                                onChange={(e) =>
                                    onShowAllDependenciesChange(e.target.checked)
                                }
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
                <Typography variant="caption" color="text.secondary">
                    Только проблемные:
                </Typography>

                <FormControlLabel
                    control={
                        <Checkbox
                            checked={showOnlyBlocked}
                            onChange={(e) => onShowOnlyBlockedChange(e.target.checked)}
                            size="small"
                            color="error"
                        />
                    }
                    label={
                        <Typography variant="body2">
                            🔒 Только заблокированные
                        </Typography>
                    }
                />

                <FormControlLabel
                    control={
                        <Checkbox
                            checked={showOnlySlowCooling}
                            onChange={(e) =>
                                onShowOnlySlowCoolingChange(e.target.checked)
                            }
                            size="small"
                            color="warning"
                        />
                    }
                    label={
                        <Typography variant="body2">
                            ⏳ Только замедленное охлаждение
                        </Typography>
                    }
                />

                <FormControlLabel
                    control={
                        <Checkbox
                            checked={showOnlyCzIncomplete}
                            onChange={(e) =>
                                onShowOnlyCzIncompleteChange(e.target.checked)
                            }
                            size="small"
                            color="info"
                        />
                    }
                    label={
                        <Typography variant="body2">
                            📷 Только не промаркированные
                        </Typography>
                    }
                />

                {/* Итерация 13.18: фильтр «только закреплённые» */}
                <FormControlLabel
                    control={
                        <Checkbox
                            checked={showOnlyPinned}
                            onChange={(e) =>
                                onShowOnlyPinnedChange(e.target.checked)
                            }
                            size="small"
                            color="primary"
                        />
                    }
                    label={
                        <Typography variant="body2">
                            📌 Только закреплённые
                        </Typography>
                    }
                />

                <Divider/>

                <Button
                    variant="outlined"
                    size="small"
                    startIcon={<FilterAltOffIcon/>}
                    onClick={onResetAll}
                    disabled={!hasActiveFilters}
                >
                    Сбросить все фильтры
                </Button>
            </Box>
        </Popover>
    );
};

export default GanttFiltersPopover;