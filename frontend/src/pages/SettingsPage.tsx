// frontend/src/pages/SettingsPage.tsx
import React, {useCallback, useEffect, useMemo, useState} from 'react';
import {
    Accordion,
    AccordionDetails,
    AccordionSummary,
    Alert,
    Box,
    Button,
    Checkbox,
    Chip,
    CircularProgress,
    Dialog,
    DialogActions,
    DialogContent,
    DialogContentText,
    DialogTitle,
    FormControl,
    FormControlLabel,
    InputLabel,
    MenuItem,
    Select,
    TextField,
    Tooltip,
    Typography,
} from '@mui/material';
import {
    ExpandMore as ExpandMoreIcon,
    Lock as LockIcon,
    Refresh as RefreshIcon,
    Save as SaveIcon,
    Settings as SettingsIcon,
    Warning as WarningIcon,
} from '@mui/icons-material';
import {settingsApi} from '../services/api';
import type {SettingSpec, SettingsSchema} from '../types';

// ==========================================
// Компонент: отдельное поле настройки
// ==========================================

interface SettingFieldProps {
    spec: SettingSpec;
    value: any;
    onChange: (key: string, value: any) => void;
    disabled?: boolean;
}

const SettingField: React.FC<SettingFieldProps> = ({
                                                       spec,
                                                       value,
                                                       onChange,
                                                       disabled = false,
                                                   }) => {
    const isDisabled = disabled || spec.is_system;

    const labelWithIcon = (
        <Box sx={{display: 'flex', alignItems: 'center', gap: 0.5}}>
            {spec.label}
            {spec.is_system && (
                <Tooltip title="Системная настройка (управляется программно)">
                    <LockIcon fontSize="small" sx={{color: 'text.secondary'}}/>
                </Tooltip>
            )}
        </Box>
    );

    // ==========================================
    // bool
    // ==========================================
    if (spec.value_type === 'bool') {
        return (
            <FormControlLabel
                control={
                    <Checkbox
                        checked={!!value}
                        onChange={(e) => onChange(spec.key, e.target.checked)}
                        disabled={isDisabled}
                    />
                }
                label={labelWithIcon}
            />
        );
    }

    // ==========================================
    // select
    // ==========================================
    if (spec.value_type === 'select' && spec.options) {
        return (
            <FormControl fullWidth size="small" disabled={isDisabled}>
                <InputLabel>{spec.label}</InputLabel>
                <Select
                    value={value ?? ''}
                    label={spec.label}
                    onChange={(e) => onChange(spec.key, e.target.value)}
                >
                    {spec.options.map((opt) => (
                        <MenuItem key={opt.value} value={opt.value}>
                            {opt.label}
                        </MenuItem>
                    ))}
                </Select>
                {spec.description && (
                    <Typography variant="caption" color="text.secondary" sx={{mt: 0.5, ml: 1.5}}>
                        {spec.description}
                    </Typography>
                )}
            </FormControl>
        );
    }

    // ==========================================
    // int / float
    // ==========================================
    if (spec.value_type === 'int' || spec.value_type === 'float') {
        return (
            <TextField
                fullWidth
                size="small"
                type="number"
                label={spec.label}
                value={value ?? ''}
                onChange={(e) => {
                    const raw = e.target.value;
                    if (raw === '') {
                        onChange(spec.key, null);
                    } else {
                        onChange(
                            spec.key,
                            spec.value_type === 'int' ? parseInt(raw, 10) : parseFloat(raw),
                        );
                    }
                }}
                disabled={isDisabled}
                slotProps={{
                    htmlInput: {
                        min: spec.min_value ?? undefined,
                        max: spec.max_value ?? undefined,
                        step: spec.value_type === 'float' ? 0.01 : 1,
                    },
                }}
                helperText={
                    spec.description
                    + (spec.min_value != null || spec.max_value != null
                        ? ` (${spec.min_value ?? '−∞'}…${spec.max_value ?? '∞'})`
                        : '')
                }
            />
        );
    }

    // ==========================================
    // json (read-only)
    // ==========================================
    if (spec.value_type === 'json') {
        return (
            <TextField
                fullWidth
                size="small"
                label={labelWithIcon}
                value={typeof value === 'string' ? value : JSON.stringify(value, null, 2)}
                multiline
                rows={3}
                disabled
                slotProps={{
                    input: {
                        style: {fontFamily: 'monospace', fontSize: '0.85rem'},
                    },
                }}
                helperText={spec.description || 'Управляется режимом смен'}
            />
        );
    }

    // ==========================================
    // str (по умолчанию)
    // ==========================================
    return (
        <TextField
            fullWidth
            size="small"
            label={spec.label}
            value={value ?? ''}
            onChange={(e) => onChange(spec.key, e.target.value)}
            disabled={isDisabled}
            helperText={spec.description}
        />
    );
};

// ==========================================
// Основная страница
// ==========================================

const SettingsPage: React.FC = () => {
    const [schema, setSchema] = useState<SettingsSchema | null>(null);
    const [values, setValues] = useState<Record<string, any>>({});
    const [originalValues, setOriginalValues] = useState<Record<string, any>>({});
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);

    // Диалог смены режима смен
    const [shiftModeDialogOpen, setShiftModeDialogOpen] = useState(false);
    const [pendingShiftMode, setPendingShiftMode] = useState<string | null>(null);

    // ==========================================
    // Загрузка данных
    // ==========================================
    const loadData = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const [schemaData, valuesData] = await Promise.all([
                settingsApi.getSchema(),
                settingsApi.getAll(),
            ]);
            setSchema(schemaData);
            setValues(valuesData);
            setOriginalValues(valuesData);
        } catch (err: any) {
            const detail = err.response?.data?.detail;
            setError(typeof detail === 'string' ? detail : 'Ошибка загрузки настроек');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        loadData();
    }, [loadData]);

    // ==========================================
    // Изменение значения
    // ==========================================
    const handleChange = (key: string, value: any) => {
        // Особый случай: смена режима смен — показываем предупреждение
        if (key === 'shift_mode' && value !== originalValues['shift_mode']) {
            setPendingShiftMode(value);
            setShiftModeDialogOpen(true);
            return;
        }
        setValues((prev) => ({...prev, [key]: value}));
    };

    // ==========================================
    // Применение режима смен
    // ==========================================
    const handleConfirmShiftMode = async () => {
        if (!pendingShiftMode) return;
        setShiftModeDialogOpen(false);
        try {
            await settingsApi.changeShiftMode(pendingShiftMode);
            setSuccess(
                `Режим смен изменён на "${pendingShiftMode}". Не забудьте пересчитать план.`,
            );
            await loadData();
        } catch (err: any) {
            const detail = err.response?.data?.detail;
            setError(typeof detail === 'string' ? detail : 'Ошибка смены режима');
        } finally {
            setPendingShiftMode(null);
        }
    };

    // ==========================================
    // Сохранение всех изменений
    // ==========================================
    const handleSave = async () => {
        setSaving(true);
        setError(null);
        setSuccess(null);
        try {
            // Отправляем только изменённые (кроме shift_mode — он уже применён)
            const updates: Record<string, any> = {};
            for (const [key, val] of Object.entries(values)) {
                if (key === 'shift_mode') continue;
                if (val !== originalValues[key]) {
                    updates[key] = val;
                }
            }

            if (Object.keys(updates).length === 0) {
                setSuccess('Нет изменений для сохранения');
                return;
            }

            await settingsApi.updateBulk(updates);
            setSuccess(`Сохранено настроек: ${Object.keys(updates).length}`);
            await loadData();
        } catch (err: any) {
            const detail = err.response?.data?.detail;
            setError(typeof detail === 'string' ? detail : 'Ошибка сохранения');
        } finally {
            setSaving(false);
        }
    };

    // ==========================================
    // Сброс к значениям из БД
    // ==========================================
    const handleReset = () => {
        setValues({...originalValues});
        setSuccess(null);
        setError(null);
    };

    // ==========================================
    // Группировка по категориям
    // ==========================================
    const groupedSettings = useMemo(() => {
        if (!schema) return {};
        const groups: Record<string, SettingSpec[]> = {};
        for (const s of schema.settings) {
            if (!groups[s.category]) groups[s.category] = [];
            groups[s.category].push(s);
        }
        // Сортируем по display_order
        for (const cat of Object.keys(groups)) {
            groups[cat].sort((a, b) => a.display_order - b.display_order);
        }
        return groups;
    }, [schema]);

    // ==========================================
    // Подсчёт изменений
    // ==========================================
    const changedCount = useMemo(() => {
        let count = 0;
        for (const [key, val] of Object.entries(values)) {
            if (key === 'shift_mode') continue;
            if (val !== originalValues[key]) count++;
        }
        return count;
    }, [values, originalValues]);

    // ==========================================
    // Рендер
    // ==========================================
    if (loading && !schema) {
        return (
            <Box sx={{display: 'flex', justifyContent: 'center', mt: 8}}>
                <CircularProgress/>
            </Box>
        );
    }

    return (
        <Box sx={{height: '100%', display: 'flex', flexDirection: 'column', minHeight: 0}}>
            {/* Заголовок */}
            <Box
                sx={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    mb: 2,
                    flexWrap: 'wrap',
                    gap: 2,
                }}
            >
                <Box sx={{display: 'flex', alignItems: 'center', gap: 2}}>
                    <SettingsIcon color="primary" sx={{fontSize: 32}}/>
                    <Typography variant="h4" component="h1" sx={{fontWeight: 600, color: '#2c3e50'}}>
                        Настройки
                    </Typography>
                    {changedCount > 0 && (
                        <Chip
                            label={`Изменено: ${changedCount}`}
                            color="warning"
                            variant="filled"
                        />
                    )}
                </Box>
                <Box sx={{display: 'flex', gap: 1}}>
                    <Button
                        variant="outlined"
                        startIcon={<RefreshIcon/>}
                        onClick={loadData}
                        disabled={loading}
                    >
                        Обновить
                    </Button>
                    <Button
                        variant="outlined"
                        onClick={handleReset}
                        disabled={changedCount === 0 || saving}
                    >
                        Сбросить
                    </Button>
                    <Button
                        variant="contained"
                        startIcon={<SaveIcon/>}
                        onClick={handleSave}
                        disabled={changedCount === 0 || saving}
                    >
                        {saving ? 'Сохранение...' : 'Сохранить'}
                    </Button>
                </Box>
            </Box>

            {error && (
                <Alert severity="error" sx={{mb: 2}} onClose={() => setError(null)}>
                    {error}
                </Alert>
            )}

            {success && (
                <Alert severity="success" sx={{mb: 2}} onClose={() => setSuccess(null)}>
                    {success}
                </Alert>
            )}

            {/* Аккордеоны категорий */}
            <Box sx={{flexGrow: 1, overflow: 'auto', minHeight: 0}}>
                {schema?.categories.map((cat) => {
                    const catSettings = groupedSettings[cat.key] || [];
                    if (catSettings.length === 0) return null;

                    return (
                        <Accordion
                            key={cat.key}
                            defaultExpanded={cat.key === 'planning' || cat.key === 'shifts'}
                            sx={{
                                mb: 1,
                                boxShadow: '0 2px 6px rgba(0,0,0,0.08)',
                            }}
                        >
                            <AccordionSummary expandIcon={<ExpandMoreIcon/>}>
                                <Box sx={{display: 'flex', alignItems: 'center', gap: 1.5, width: '100%'}}>
                                    <Typography sx={{fontWeight: 600}}>{cat.label}</Typography>
                                    <Chip
                                        label={`${catSettings.length}`}
                                        size="small"
                                        variant="outlined"
                                    />
                                </Box>
                            </AccordionSummary>
                            <AccordionDetails>
                                <Box sx={{display: 'flex', flexDirection: 'column', gap: 2}}>
                                    {catSettings.map((spec) => (
                                        <SettingField
                                            key={spec.key}
                                            spec={spec}
                                            value={values[spec.key]}
                                            onChange={handleChange}
                                        />
                                    ))}
                                </Box>
                            </AccordionDetails>
                        </Accordion>
                    );
                })}
            </Box>

            <Typography variant="caption" color="text.secondary" sx={{mt: 1, display: 'block', textAlign: 'center'}}>
                💡 Изменения вступят в силу при следующем построении плана • Смена режима смен пересоздаст смены в БД
            </Typography>

            {/* Диалог смены режима */}
            <Dialog open={shiftModeDialogOpen} onClose={() => setShiftModeDialogOpen(false)}>
                <DialogTitle sx={{display: 'flex', alignItems: 'center', gap: 1}}>
                    <WarningIcon color="warning"/>
                    Смена режима смен
                </DialogTitle>
                <DialogContent>
                    <DialogContentText>
                        Вы хотите изменить режим смен на <b>{pendingShiftMode}</b>.
                        <br/><br/>
                        Это приведёт к:
                        <ul>
                            <li>Пересозданию всех смен в БД на новый горизонт.</li>
                            <li>Потере текущей привязки задач к сменам.</li>
                            <li>Необходимости пересчитать план заново.</li>
                        </ul>
                        Продолжить?
                    </DialogContentText>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setShiftModeDialogOpen(false)}>Отмена</Button>
                    <Button onClick={handleConfirmShiftMode} variant="contained" color="warning">
                        Применить
                    </Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
};

export default SettingsPage;