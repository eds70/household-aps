// frontend/src/pages/PlanSettingsWizard.tsx
import React, {useCallback, useEffect, useMemo, useState} from 'react';
import {
    Alert,
    Box,
    Button,
    Checkbox,
    Chip,
    CircularProgress,
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
import DraggableDialog from '../components/common/DraggableDialog';
import {planSettingsApi, scheduleApi, settingsApi} from '../services/api';
import type {SettingSpec, SettingsSchema} from '../types';

// ==========================================
// Шаги
// ==========================================

interface WizardStep {
    key: string;
    label: string;
    description: string;
    categories: string[];
}

const WIZARD_STEPS: WizardStep[] = [
    {
        key: 'meta',
        label: 'Метаданные',
        description: 'Наименование и комментарий плана.',
        categories: [],
    },
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

export type WizardMode = 'create' | 'edit';

interface PlanSettingsWizardProps {
    open: boolean;
    onClose: () => void;
    mode?: WizardMode;
    versionId?: string | null;
    onSaved?: (
        versionId: string,
        action: 'save' | 'save-and-build' | 'create-and-build',
    ) => void;
}

// ==========================================
// Компонент
// ==========================================

const PlanSettingsWizard: React.FC<PlanSettingsWizardProps> = ({
                                                                   open,
                                                                   onClose,
                                                                   mode = 'edit',
                                                                   versionId,
                                                                   onSaved,
                                                               }) => {
    const isCreateMode = mode === 'create';
    const isEditMode = !isCreateMode;

    // Метаданные плана
    const [planName, setPlanName] = useState('');
    const [planComment, setPlanComment] = useState('');
    const [planVersionType, setPlanVersionType] = useState('MONTHLY');

    // Снапшот исходных метаданных для отслеживания изменений
    const [originalMeta, setOriginalMeta] = useState<{
        name: string;
        comment: string;
        version_type: string;
    }>({name: '', comment: '', version_type: 'MONTHLY'});

    // Настройки
    const [schema, setSchema] = useState<SettingsSchema | null>(null);
    const [values, setValues] = useState<Record<string, any>>({});
    const [originalValues, setOriginalValues] = useState<Record<string, any>>({});
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);

    const [activeStep, setActiveStep] = useState(isCreateMode ? 0 : 1);

    // ==========================================
    // Загрузка
    // ==========================================
    const loadData = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const schemaData = await settingsApi.getSchema();
            setSchema(schemaData);

            if (isEditMode && versionId) {
                const planData = await planSettingsApi.getForVersion(versionId);
                setValues(planData.settings);
                setOriginalValues(planData.settings);

                // Метаданные
                const meta = {
                    name: planData.metadata?.name || '',
                    comment: planData.metadata?.comment || '',
                    version_type: planData.metadata?.version_type || 'MONTHLY',
                };
                setPlanName(meta.name);
                setPlanComment(meta.comment);
                setPlanVersionType(meta.version_type);
                setOriginalMeta(meta);
            } else {
                const globalData = await settingsApi.getAll();
                setValues(globalData);
                setOriginalValues(globalData);
            }
        } catch (err: any) {
            const detail = err.response?.data?.detail;
            setError(typeof detail === 'string' ? detail : 'Ошибка загрузки');
        } finally {
            setLoading(false);
        }
    }, [isEditMode, versionId]);

    useEffect(() => {
        if (open) {
            setActiveStep(isCreateMode ? 0 : 1);
            setPlanName('');
            setPlanComment('');
            setPlanVersionType('MONTHLY');
            setOriginalMeta({name: '', comment: '', version_type: 'MONTHLY'});
            setError(null);
            setSuccess(null);
            loadData();
        }
    }, [open, loadData, isCreateMode]);

    // ==========================================
    // Изменение настроек
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
    // Изменение метаданных
    // ==========================================
    const metadataChanged = useMemo(() => {
        if (isCreateMode) return false;
        return (
            planName !== originalMeta.name ||
            planComment !== originalMeta.comment
            // version_type в edit-режиме не меняется
        );
    }, [isCreateMode, planName, planComment, originalMeta]);

    // ==========================================
    // Текущий шаг
    // ==========================================
    const currentStepSettings = useMemo<SettingSpec[]>(() => {
        if (!schema) return [];
        const step = WIZARD_STEPS[activeStep];
        if (!step || step.categories.length === 0) return [];
        return schema.settings
            .filter((s) => step.categories.includes(s.category))
            .sort((a, b) => a.display_order - b.display_order);
    }, [schema, activeStep]);

    // ==========================================
    // Создание нового плана
    // ==========================================
    const handleCreatePlan = async (): Promise<string | null> => {
        if (!planName.trim()) {
            setError('Введите название плана');
            return null;
        }
        const newVersion = await scheduleApi.createVersion({
            name: planName.trim(),
            version_type: planVersionType,
            comment: planComment || undefined,
        });
        return newVersion.id;
    };

    // ==========================================
    // Сохранение настроек
    // ==========================================
    const handleSaveSettings = async (targetVersionId: string) => {
        const updates: Record<string, any> = {};
        for (const key of changedKeys) {
            const spec = schema?.settings.find((s) => s.key === key);
            if (spec?.is_system) continue;
            updates[key] = values[key];
        }
        await planSettingsApi.updateForVersion(targetVersionId, {settings: updates});
        setOriginalValues(values);
        return Object.keys(updates).length;
    };

    // ==========================================
    // Сохранение метаданных
    // ==========================================
    const handleSaveMetadata = async (targetVersionId: string) => {
        if (!metadataChanged) return false;
        await planSettingsApi.updateForVersion(targetVersionId, {
            name: planName.trim(),
            comment: planComment,
        });
        setOriginalMeta({
            name: planName.trim(),
            comment: planComment,
            version_type: originalMeta.version_type,
        });
        return true;
    };

    // ==========================================
    // Главный обработчик
    // ==========================================
    const handleSave = async (alsoBuild: boolean = false) => {
        setSaving(true);
        setError(null);
        setSuccess(null);
        try {
            let targetVersionId: string | null = null;

            if (isCreateMode) {
                targetVersionId = await handleCreatePlan();
                if (!targetVersionId) {
                    setSaving(false);
                    return;
                }
                await handleSaveSettings(targetVersionId);
                setSuccess(`План "${planName}" создан`);
            } else {
                if (!versionId) {
                    setError('versionId не передан');
                    setSaving(false);
                    return;
                }
                targetVersionId = versionId;
                const settingsCount = await handleSaveSettings(versionId);
                const metaSaved = await handleSaveMetadata(versionId);
                if (settingsCount === 0 && !metaSaved) {
                    setSuccess('Нет изменений для сохранения');
                } else {
                    setSuccess(
                        `Сохранено: настроек ${settingsCount}` +
                        (metaSaved ? ', метаданные обновлены' : ''),
                    );
                }
            }

            if (onSaved && targetVersionId) {
                const action = isCreateMode
                    ? 'create-and-build'
                    : (alsoBuild ? 'save-and-build' : 'save');
                onSaved(targetVersionId, action);
            }

            if (alsoBuild && targetVersionId) {
                await scheduleApi.build({});
            }
        } catch (err: any) {
            const detail = err.response?.data?.detail;
            setError(typeof detail === 'string' ? detail : 'Ошибка сохранения');
        } finally {
            setSaving(false);
        }
    };

    // ==========================================
    // Сброс к глобальным (только edit)
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
    // Рендер поля настройки
    // ==========================================
    const renderField = (spec: SettingSpec) => {
        const value = values[spec.key];
        const isChanged = changedKeys.includes(spec.key);
        const isDisabled = spec.is_system;

        const labelNode = (
            <Box sx={{display: 'flex', alignItems: 'center', gap: 0.5}}>
                {spec.label}
                {isChanged && (
                    <Chip label="изменено" size="small" color="warning"
                          sx={{height: 18, fontSize: '0.65rem'}}/>
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
                            <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>
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
                        min={0} max={1} step={0.05} disabled={isDisabled}
                        marks={[{value: 0, label: '0'}, {value: 0.5, label: '0.5'}, {value: 1, label: '1'}]}
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
                    fullWidth size="small" type="number"
                    label={labelNode}
                    value={value ?? ''}
                    onChange={(e) => {
                        const raw = e.target.value;
                        if (raw === '') handleChange(spec.key, null);
                        else handleChange(spec.key, spec.value_type === 'int'
                            ? parseInt(raw, 10)
                            : parseFloat(raw));
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
                            ? ` (${spec.min_value ?? '−∞'}…${spec.max_value ?? '∞'})` : '')
                    }
                />
            );
        }

        if (spec.value_type === 'json') {
            return (
                <TextField
                    key={spec.key}
                    fullWidth size="small"
                    label={labelNode}
                    value={typeof value === 'string' ? value : JSON.stringify(value, null, 2)}
                    multiline rows={3} disabled
                    slotProps={{input: {style: {fontFamily: 'monospace', fontSize: '0.85rem'}}}}
                    helperText={spec.description || 'Управляется режимом смен'}
                />
            );
        }

        return (
            <TextField
                key={spec.key}
                fullWidth size="small"
                label={labelNode}
                value={value ?? ''}
                onChange={(e) => handleChange(spec.key, e.target.value)}
                disabled={isDisabled}
                helperText={spec.description}
            />
        );
    };

    // ==========================================
    // Шаг «Метаданные»
    // ==========================================
    const renderMetaStep = () => (
        <Box sx={{display: 'flex', flexDirection: 'column', gap: 2.5}}>
            <TextField
                label="Наименование плана"
                fullWidth required size="small"
                value={planName}
                onChange={(e) => setPlanName(e.target.value)}
                placeholder="Например: План на октябрь 2026"
                helperText="Отображается в списке планов и на верхней плашке."
                error={!planName.trim()}
            />

            <FormControl fullWidth size="small" variant="outlined" disabled={isEditMode}>
                <InputLabel>Тип плана</InputLabel>
                <Select
                    value={planVersionType}
                    label="Тип плана"
                    variant="outlined"
                    onChange={(e) => setPlanVersionType(e.target.value)}
                >
                    <MenuItem value="MONTHLY">Месячный (ОКП)</MenuItem>
                    <MenuItem value="SHIFT">Посменный</MenuItem>
                    <MenuItem value="WHAT_IF">Сценарий "что если"</MenuItem>
                </Select>
                {isEditMode && (
                    <Typography variant="caption" color="text.secondary" sx={{mt: 0.5, ml: 1.5}}>
                        Тип существующего плана изменить нельзя.
                    </Typography>
                )}
            </FormControl>

            <TextField
                label="Комментарий"
                fullWidth multiline rows={3} size="small"
                value={planComment}
                onChange={(e) => setPlanComment(e.target.value)}
                placeholder="Произвольные заметки к плану"
                helperText="Необязательно."
            />
        </Box>
    );

    // ==========================================
    // Кнопки
    // ==========================================
    const currentStep = WIZARD_STEPS[activeStep];
    const isMetaStep = currentStep?.key === 'meta';

    const canSave = isCreateMode
        ? !!planName.trim()
        : (changedKeys.length > 0 || metadataChanged);

    const totalChanges = changedKeys.length + (metadataChanged ? 1 : 0);

    const renderActions = () => (
        <Box sx={{display: 'flex', justifyContent: 'space-between', width: '100%', alignItems: 'center'}}>
            <Box>
                {isEditMode && versionId && (
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
                <Button onClick={handleBack} disabled={activeStep === 0 || saving}
                        startIcon={<ArrowBackIcon/>} sx={{textTransform: 'none'}}>
                    Назад
                </Button>
                <Button onClick={handleNext} disabled={activeStep === WIZARD_STEPS.length - 1 || saving}
                        endIcon={<ArrowForwardIcon/>} sx={{textTransform: 'none'}}>
                    Далее
                </Button>
                <Divider orientation="vertical" flexItem sx={{mx: 1}}/>
                <Button
                    onClick={() => handleSave(false)}
                    variant="outlined"
                    startIcon={<SaveIcon/>}
                    disabled={saving || !canSave}
                    sx={{textTransform: 'none'}}
                >
                    {isCreateMode ? 'Создать план' : 'Сохранить'}
                </Button>
                <Button
                    onClick={() => handleSave(true)}
                    variant="contained"
                    startIcon={saving ? <CircularProgress size={18}/> : <CheckIcon/>}
                    disabled={saving || !canSave}
                    sx={{textTransform: 'none'}}
                >
                    {isCreateMode ? 'Создать и построить план' : 'Сохранить и построить план'}
                </Button>
            </Box>
        </Box>
    );

    // ==========================================
    // Рендер
    // ==========================================
    return (
        <DraggableDialog
            open={open}
            onClose={onClose}
            draggable resizable
            closeOnBackdropClick={false}
            showCloseButton
            initialWidth={900}
            initialHeight={640}
            minWidth={640}
            minHeight={400}
            title={
                <Box sx={{display: 'flex', alignItems: 'center', gap: 1.5}}>
                    <SettingsIcon color="primary"/>
                    <Box sx={{flexGrow: 1, minWidth: 0}}>
                        <Typography variant="h6" component="div" sx={{fontWeight: 600}}>
                            {isCreateMode ? 'Новый план' : 'Мастер настроек плана'}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                            {isCreateMode
                                ? 'Заполните метаданные и настройки — план создастся сразу.'
                                : 'Настройки привязаны к конкретному плану и не влияют на другие.'}
                        </Typography>
                    </Box>
                </Box>
            }
            titleExtra={
                <>
                    {isEditMode && totalChanges > 0 && (
                        <Chip
                            label={`Изменено: ${totalChanges}`}
                            color="warning"
                            size="small"
                        />
                    )}
                </>
            }
            actions={renderActions()}
        >
            {loading ? (
                <Box sx={{display: 'flex', justifyContent: 'center', py: 6}}>
                    <CircularProgress/>
                </Box>
            ) : (
                <Box sx={{display: 'flex', minHeight: 0}}>
                    <Box sx={{
                        width: 260, flexShrink: 0,
                        borderRight: '1px solid #e0e0e0',
                        bgcolor: '#f8f9fa', p: 1.5, overflowY: 'auto',
                    }}>
                        <Stepper activeStep={activeStep} orientation="vertical" nonLinear>
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

                    <Box sx={{flexGrow: 1, p: 3, overflowY: 'auto', minWidth: 0}}>
                        <Typography variant="h6" sx={{fontWeight: 600, mb: 0.5}}>
                            {currentStep?.label}
                        </Typography>
                        <Typography variant="caption" color="text.secondary"
                                    sx={{display: 'block', mb: 2}}>
                            {currentStep?.description}
                        </Typography>
                        <Divider sx={{mb: 2}}/>

                        {isMetaStep ? renderMetaStep() : (
                            <Box sx={{display: 'flex', flexDirection: 'column', gap: 2.5}}>
                                {currentStepSettings.map(renderField)}
                            </Box>
                        )}
                    </Box>
                </Box>
            )}

            {error && (
                <Box sx={{mt: 2}}>
                    <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>
                </Box>
            )}
            {success && (
                <Box sx={{mt: 2}}>
                    <Alert severity="success" onClose={() => setSuccess(null)}>{success}</Alert>
                </Box>
            )}
        </DraggableDialog>
    );
};

export default PlanSettingsWizard;