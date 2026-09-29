// frontend/src/components/gantt/RecalcSettingsDialog.tsx
/**
 * Диалог, показываемый при попытке пересчёта, если у плана
 * нет plan_settings (Итерация 13.17).
 *
 * Предлагает открыть PlanSettingsWizard.
 *
 * Итерация 13.17 (9e): добавлена кнопка «Пересчитать без изменений» —
 * на случай, если пользователь хочет просто пересчитать план
 * с текущими настройками (без открытия мастера).
 */
import React from 'react';
import {Alert, Box, Button, Typography} from '@mui/material';
import {Autorenew as RecalcIcon, Settings as SettingsIcon,} from '@mui/icons-material';
import DraggableDialog from '../common/DraggableDialog';

interface RecalcSettingsDialogProps {
    open: boolean;
    onClose: () => void;
    /** Открыть мастер настроек плана. */
    onOpenWizard: () => void;
    /** Пересчитать без изменений (прямой вызов reschedule). */
    onForceRecalc?: () => void;
    planName?: string;
    /** Идёт ли пересчёт в данный момент. */
    recalculating?: boolean;
}

const RecalcSettingsDialog: React.FC<RecalcSettingsDialogProps> = ({
                                                                       open,
                                                                       onClose,
                                                                       onOpenWizard,
                                                                       onForceRecalc,
                                                                       planName,
                                                                       recalculating = false,
                                                                   }) => {
    return (
        <DraggableDialog
            open={open}
            onClose={onClose}
            title={
                <Box sx={{display: 'flex', alignItems: 'center', gap: 1}}>
                    <SettingsIcon color="warning" />
                    <Typography variant="h6" component="div" sx={{fontWeight: 600}}>
                        Настройки плана не заполнены
                    </Typography>
                </Box>
            }
            initialWidth={620}
            initialHeight="auto"
            minWidth={480}
            minHeight={280}
            actions={
                <>
                    <Button onClick={onClose} disabled={recalculating}>
                        Отмена
                    </Button>
                    {onForceRecalc && (
                        <Button
                            onClick={onForceRecalc}
                            variant="outlined"
                            color="primary"
                            disabled={recalculating}
                            startIcon={<RecalcIcon />}
                        >
                            {recalculating ? 'Пересчёт...' : 'Пересчитать без изменений'}
                        </Button>
                    )}
                    <Button
                        onClick={() => {
                            onClose();
                            onOpenWizard();
                        }}
                        variant="contained"
                        startIcon={<SettingsIcon />}
                        disabled={recalculating}
                    >
                        Открыть мастер настроек
                    </Button>
                </>
            }
        >
            <Box sx={{display: 'flex', flexDirection: 'column', gap: 2}}>
                <Alert severity="warning">
                    <Typography variant="body2">
                        Для пересчёта плана нужны настройки. Они хранятся
                        в таблице <code>plan_settings</code> и не были заполнены
                        для плана{planName ? ` «${planName}»` : ''}.
                    </Typography>
                </Alert>
                <Typography variant="body2">
                    Откройте мастер настроек плана, заполните параметры
                    (горизонт, режим смен, охлаждение, оптимизация)
                    и сохраните. После этого кнопка «Пересчитать»
                    станет доступной.
                </Typography>
                {onForceRecalc && (
                    <Alert severity="info">
                        <Typography variant="body2">
                            <b>Альтернатива:</b> можно пересчитать план
                            с текущими настройками из <code>app_settings</code> —
                            без открытия мастера. Это подойдёт, если
                            вы уверены, что глобальные настройки корректны.
                        </Typography>
                    </Alert>
                )}
            </Box>
        </DraggableDialog>
    );
};

export default RecalcSettingsDialog;