// frontend/src/pages/PlanSettingsWizard.tsx
import React, {useCallback, useEffect, useMemo, useState} from 'react';
import {
    Alert,
    Box,
    Button,
    Checkbox,
    Chip,
    CircularProgress,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    Divider,
    FormControl,
    FormControlLabel,
    InputLabel,
    MenuItem,
    Select,
    Slider,
    Step,
    StepButton,
    StepLabel,
    Stepper,
    TextField,
    Tooltip,
    Typography,
} from '@mui/material';
import {
    ArrowBack as ArrowBackIcon,
    ArrowForward as ArrowForwardIcon,
    Check as CheckIcon,
    InfoOutlined as InfoIcon,
    RestartAlt as ResetIcon,
    Save as SaveIcon,
    Settings as SettingsIcon,
} from '@mui/icons-material';
import {planSettingsApi, scheduleApi, settingsApi} from '../services/api';
import type {SettingSpec, SettingsSchema} from '../types';

// ==========================================
// Описание шагов мастера
// ==========================================

interface WizardStep {
    key: string;
    label: string;
    description: string;
    categories: string[];
}

const WIZARD_STEPS: WizardStep[] = [
    {
        key: 'planning',
        label: 'Основные',
        description: 'Дата старта, горизонт, таймаут solver, макс. загрузка реактора.',
        categories: ['planning'],
    },
    {
        key: 'shifts',
        label: 'Режим смен',
        description: 'Режим смен (1x8 / 3x8 / 2x12). Влияет на разбиение длинных задач.',
        categories: ['shifts'],
    },
    {
        key: 'calendar',
        label: 'Календарь',
        description: 'Работа в выходные, ограничения на длительность задач.',
        categories: ['calendar'],
    },
    {
        key: 'cooling',
        label: 'Охлаждение',
        description: 'Деградация охлаждения, коэффициент замедления, ёмкость зоны.',
        categories: ['cooling'],
    },
    {
        key: 'resources',
        label: 'Ресурсы',
        description: 'Пулы операторов, использование ручной станции.',
        categories: ['resources'],
    },
    {
        key: 'materials-lab',
        label: 'Материалы и лаборатория',
        description: 'Учёт остатков сырья, блокировка партий лабораторией.',
        categories: ['materials', 'lab'],
    },
    {
        key: 'features',
        label: 'Маршруты и функции',
        description: 'Маршруты через танк, Advisor, сменное планирование, перепланирование.',
        categories: ['features'],
    },
    {
        key: 'cz',
        label: 'Честный Знак',
        description: 'Интеграция с ЧЗ, порог завершения маркировки.',
        categories: ['cz'],
    },
    {
        key: 'optimization',
        label: 'Оптимизация',
        description: '5 весов multi-objective целевой функции.',
        categories: ['optimization'],
    },
];

// ==========================================
// Пропсы
// ==========================================

interface PlanSettingsWizardProps {
    open: boolean;
    onClose: () => void;
    /** Если задан — работаем с существующим планом. */
    versionId?: string | null;
    /** Колбэк после сохранения. */
    onSaved?: (versionId: string, action: 'save' | 'save-and-build') => void;
}

// ==========================================
// Компонент
// ==========================================

const PlanSettingsWizard: React.FC<PlanSettingsWizardProps> = ({
                                                                   open,
                                                                   onClose,
                                                                   versionId,
                                                                   onSaved,
                                                               }) => {
    const isEditingExisting = !!versionId;

    const [schema, setSchema] = useState<SettingsSchema | null>(null);
    const [values, setValues] = useState<Record<string, any>>({});
    const [originalValues, setOriginalValues] = useState<Record<string, any>>({});
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);

    const [activeStep, setActiveStep] = useState(0);

    // ==========================================
    // Загрузка
    // ==========================================
    const loadData = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const schemaData = await settingsApi.getSchema();
            setSchema(schemaData);

            if (versionId) {
                const planData = await planSettingsApi.getForVersion(versionId);
                setValues(planData.settings);
                setOriginalValues(planData.settings);
            } else {
                const globalData = await settingsApi.getAll();
                setValues(globalData);
                setOriginalValues(globalData);
            }
        } catch (err: any) {
            const detail = err.response?.data?.detail;
            setError(typeof detail === 'string' ? detail : 'Ошибка загрузки настроек');
        } finally {
            setLoading(false);
        }
    }, [versionId]);

    useEffect(() => {
        if (open) {
            setActiveStep(0);
            loadData();
        }
    }, [open, loadData]);

    // ==========================================
    // Изменение значения
    // ==========================================
    const handleChange = (key: string, value: any) => {
        setValues((prev) => ({...prev, [key]: value}));
    };

    const changedKeys = useMemo(() => {
        const changed: string[] = [];
        for (const [k, v] of Object.entries(values)) {
            if (JSON.stringify(v) !== JSON.stringify(originalValues[k])) {
                changed.push(k);
            }
        }
        return changed;
    }, [values, originalValues]);

    // ==========================================
    // Настройки текущего шага
    // ==========================================
    const currentStepSettings = useMemo<SettingSpec[]>(() => {
        if (!schema) return [];
        const step = WIZARD_STEPS[activeStep];
        if (!step) return [];
        return schema.settings
            .filter((s) => step.categories.includes(s.category))
            .sort((a, b) => a.display_order - b.display_order);
    }, [schema, activeStep]);

    // ==========================================
    // Сохранение
    // ==========================================
    const handleSave = async (alsoBuild: boolean = false) => {
        if (!versionId) {
            setError('Внутренняя ошибка: versionId не передан.');
            return;
        }
        setSaving(true);
        setError(null);
        setSuccess(null);
        try {
            const updates: Record<string, any> = {};
            for (const key of changedKeys) {
                const spec = schema?.settings.find((s) => s.key === key);
                if (spec?.is_system) continue;
                updates[key] = values[key];
            }

            if (Object.keys(updates).length === 0) {
                setSuccess('Нет изменений для сохранения');
                setSaving(false);
                return;
            }

            await planSettingsApi.updateForVersion(versionId, updates);

            setOriginalValues(values);
            setSuccess(`Сохранено настроек: ${Object.keys(updates).length}`);

            if (onSaved) {
                onSaved(versionId, alsoBuild ? 'save-and-build' : 'save');
            }

            if (alsoBuild) {
                await scheduleApi.build({});
            }
        } catch (err: any) {
            const detail = err.response?.data?.detail;
            setError(typeof detail === 'string' ? detail : 'Ошибка сохранения настроек плана');
        } finally {
            setSaving(false);
        }
    };

    // ==========================================
    // Сброс к глобальным
    // ==========================================
    const handleReset = async () => {
        if (!versionId) return;
        if (!window.confirm('Сбросить все настройки плана к глобальным значениям?')) return;
        setSaving(true);
        try {
            await planSettingsApi.resetForVersion(versionId);
            await loadData();
            setSuccess('Настройки сброшены к глобальным');
        } catch (err: any) {
            const detail = err.response?.data?.detail;
            setError(typeof detail === 'string' ? detail : 'Ошибка сброса');
        } finally {
            setSaving(false);
        }
    };

    // ==========================================
    // Навигация
    // ==========================================
    const handleNext = () => setActiveStep((s) => Math.min(s + 1, WIZARD_STEPS.length - 1));
    const handleBack = () => setActiveStep((s) => Math.max(s - 1, 0));

    // ==========================================
    // Рендер одного поля
    // ==========================================
    const renderField = (spec: SettingSpec) => {
        const value = values[spec.key];
        const isChanged = changedKeys.includes(spec.key);
        const isDisabled = spec.is_system;

        const labelNode = (
            <Box sx={{display: 'flex', alignItems: 'center', gap: 0.5}}>
                {spec.label}
                {isChanged && (
                    <Chip
                        label="изменено"
                        size="small"
                        color="warning"
                        sx={{height: 18, fontSize: '0.65rem'}}
                    />
                )}
                {isDisabled && (
                    <Tooltip title="Системная настройка — управляется режимом смен">
                        <InfoIcon fontSize="small" color="disabled"/>
                    </Tooltip>
                )}
            </Box>
        );

        if (spec.value_type === 'bool') {
            return (
                <FormControlLabel
                    key={spec.key}
                    control={
                        <Checkbox
                            checked={!!value}
                            onChange={(e) => handleChange(spec.key, e.target.checked)}
                            disabled={isDisabled}
                        />
                    }
                    label={
                        <Box>
                            <Typography variant="body2">{labelNode}</Typography>
                            {spec.description && (
                                <Typography variant="caption" color="text.secondary" sx={{display: 'block'}}>
                                    {spec.description}
                                </Typography>
                            )}
                        </Box>
                    }
                />
            );
        }

        if (spec.value_type === 'select' && spec.options) {
            return (
                <FormControl key={spec.key} fullWidth size="small" disabled={isDisabled} variant="outlined">
                    <InputLabel>{spec.label}</InputLabel>
                    <Select
                        value={value ?? ''}
                        label={spec.label}
                        variant="outlined"
                        onChange={(e) => handleChange(spec.key, e.target.value)}
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

        if (
            spec.value_type === 'float' &&
            spec.min_value === 0 &&
            spec.max_value === 1 &&
            spec.category === 'optimization'
        ) {
            return (
                <Box key={spec.key}>
                    <Box sx={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
                        <Typography variant="body2">{labelNode}</Typography>
                        <Typography variant="body2" sx={{fontWeight: 600, fontFamily: 'monospace'}}>
                            {(typeof value === 'number' ? value : 0).toFixed(2)}
                        </Typography>
                    </Box>
                    <Slider
                        value={typeof value === 'number' ? value : 0}
                        onChange={(_, v) => handleChange(spec.key, v as number)}
                        min={0}
                        max={1}
                        step={0.05}
                        disabled={isDisabled}
                        marks={[
                            {value: 0, label: '0'},
                            {value: 0.5, label: '0.5'},
                            {value: 1, label: '1'},
                        ]}
                    />
                    {spec.description && (
                        <Typography variant="caption" color="text.secondary">
                            {spec.description}
                        </Typography>
                    )}
                </Box>
            );
        }

        if (spec.value_type === 'int' || spec.value_type === 'float') {
            return (
                <TextField
                    key={spec.key}
                    fullWidth
                    size="small"
                    type="number"
                    label={labelNode}
                    value={value ?? ''}
                    onChange={(e) => {
                        const raw = e.target.value;
                        if (raw === '') {
                            handleChange(spec.key, null);
                        } else {
                            handleChange(
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

        if (spec.value_type === 'json') {
            return (
                <TextField
                    key={spec.key}
                    fullWidth
                    size="small"
                    label={labelNode}
                    value={typeof value === 'string' ? value : JSON.stringify(value, null, 2)}
                    multiline
                    rows={3}
                    disabled
                    slotProps={{
                        input: {style: {fontFamily: 'monospace', fontSize: '0.85rem'}},
                    }}
                    helperText={spec.description || 'Управляется режимом смен'}
                />
            );
        }

        return (
            <TextField
                key={spec.key}
                fullWidth
                size="small"
                label={labelNode}
                value={value ?? ''}
                onChange={(e) => handleChange(spec.key, e.target.value)}
                disabled={isDisabled}
                helperText={spec.description}
            />
        );
    };

    // ==========================================
    // Рендер
    // ==========================================
    const currentStep = WIZARD_STEPS[activeStep];

    return (
        <Dialog
            open={open}
            onClose={() => !saving && onClose()}
            maxWidth="md"
            fullWidth
        >
            <DialogTitle sx={{display: 'flex', alignItems: 'center', gap: 1.5, pb: 1}}>
                <SettingsIcon color="primary"/>
                <Box sx={{flexGrow: 1}}>
                    <Typography variant="h6" component="div" sx={{fontWeight: 600}}>
                        Мастер настроек плана
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                        {isEditingExisting
                            ? 'Настройки привязаны к конкретному плану и не влияют на другие.'
                            : 'Настройки будут применены к новому плану.'}
                    </Typography>
                </Box>
                {changedKeys.length > 0 && (
                    <Chip
                        label={`Изменено: ${changedKeys.length}`}
                        color="warning"
                        variant="filled"
                    />
                )}
            </DialogTitle>

            <Divider/>

            <DialogContent sx={{p: 0}}>
                {loading ? (
                    <Box sx={{display: 'flex', justifyContent: 'center', py: 6}}>
                        <CircularProgress/>
                    </Box>
                ) : (
                    <Box sx={{display: 'flex', minHeight: 480}}>
                        <Box sx={{
                            width: 260,
                            flexShrink: 0,
                            borderRight: '1px solid #e0e0e0',
                            bgcolor: '#f8f9fa',
                            p: 1.5,
                        }}>
                            <Stepper
                                activeStep={activeStep}
                                orientation="vertical"
                                nonLinear
                            >
                                {WIZARD_STEPS.map((step, idx) => (
                                    <Step key={step.key} completed={idx < activeStep}>
                                        <StepButton onClick={() => setActiveStep(idx)}>
                                            <StepLabel>
                                                <Typography
                                                    variant="body2"
                                                    sx={{fontWeight: idx === activeStep ? 700 : 400}}
                                                >
                                                    {step.label}
                                                </Typography>
                                            </StepLabel>
                                        </StepButton>
                                    </Step>
                                ))}
                            </Stepper>
                        </Box>

                        <Box sx={{flexGrow: 1, p: 3, overflow: 'auto'}}>
                            <Typography variant="h6" sx={{fontWeight: 600, mb: 0.5}}>
                                {currentStep?.label}
                            </Typography>
                            <Typography variant="caption" color="text.secondary" sx={{display: 'block', mb: 2}}>
                                {currentStep?.description}
                            </Typography>

                            <Divider sx={{mb: 2}}/>

                            <Box sx={{display: 'flex', flexDirection: 'column', gap: 2.5}}>
                                {currentStepSettings.map(renderField)}
                            </Box>
                        </Box>
                    </Box>
                )}
            </DialogContent>

            <Divider/>

            <DialogActions sx={{p: 2, justifyContent: 'space-between'}}>
                <Box>
                    {isEditingExisting && (
                        <Button
                            onClick={handleReset}
                            startIcon={<ResetIcon/>}
                            color="warning"
                            disabled={saving}
                            sx={{textTransform: 'none'}}
                        >
                            Сбросить к глобальным
                        </Button>
                    )}
                </Box>
                <Box sx={{display: 'flex', gap: 1, alignItems: 'center'}}>
                    <Button
                        onClick={handleBack}
                        disabled={activeStep === 0 || saving}
                        startIcon={<ArrowBackIcon/>}
                        sx={{textTransform: 'none'}}
                    >
                        Назад
                    </Button>
                    <Button
                        onClick={handleNext}
                        disabled={activeStep === WIZARD_STEPS.length - 1 || saving}
                        endIcon={<ArrowForwardIcon/>}
                        sx={{textTransform: 'none'}}
                    >
                        Далее
                    </Button>
                    <Divider orientation="vertical" flexItem sx={{mx: 1}}/>
                    <Button
                        onClick={() => handleSave(false)}
                        variant="outlined"
                        startIcon={<SaveIcon/>}
                        disabled={saving || changedKeys.length === 0 || !isEditingExisting}
                        sx={{textTransform: 'none'}}
                    >
                        Сохранить
                    </Button>
                    <Button
                        onClick={() => handleSave(true)}
                        variant="contained"
                        startIcon={saving ? <CircularProgress size={18}/> : <CheckIcon/>}
                        disabled={saving || changedKeys.length === 0 || !isEditingExisting}
                        sx={{textTransform: 'none'}}
                    >
                        Сохранить и построить план
                    </Button>
                </Box>
            </DialogActions>

            {error && (
                <Box sx={{p: 2, pt: 0}}>
                    <Alert severity="error" onClose={() => setError(null)}>
                        {error}
                    </Alert>
                </Box>
            )}
            {success && (
                <Box sx={{p: 2, pt: 0}}>
                    <Alert severity="success" onClose={() => setSuccess(null)}>
                        {success}
                    </Alert>
                </Box>
            )}
        </Dialog>
    );
};

export default PlanSettingsWizard;