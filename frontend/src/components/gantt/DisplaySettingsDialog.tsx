// frontend/src/components/gantt/DisplaySettingsDialog.tsx
import React from 'react';
import {Box, Checkbox, Divider, FormControlLabel, Typography} from '@mui/material';
import DraggableDialog from '../common/DraggableDialog';

interface DisplaySettingsDialogProps {
    open: boolean;
    onClose: () => void;
    settings: {
        showSetups: boolean;
        showDowntimes: boolean;
        showDependencies: boolean;
        showAllDependencies: boolean;
        enableLinkHover: boolean;
        showBatchBrackets: boolean;
        showMinimap: boolean;
    };
    onChange: (key: string, value: boolean) => void;
}

export const DisplaySettingsDialog: React.FC<DisplaySettingsDialogProps> = ({
                                                                                open,
                                                                                onClose,
                                                                                settings,
                                                                                onChange,
                                                                            }) => {
    const handleChange = (key: string) => (e: React.ChangeEvent<HTMLInputElement>) => {
        onChange(key, e.target.checked);
    };

    return (
        <DraggableDialog open={open} onClose={onClose} title="Настройки отображения">
            <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 1, minWidth: 300 }}>
                <Typography variant="subtitle2" color="text.secondary">Связи и зависимости</Typography>
                <FormControlLabel
                    control={<Checkbox checked={settings.showDependencies} onChange={handleChange('showDependencies')} />}
                    label="Показывать связи"
                />
                <FormControlLabel
                    control={<Checkbox checked={settings.showAllDependencies} onChange={handleChange('showAllDependencies')} />}
                    label="Показывать все связи сразу"
                />
                <FormControlLabel
                    control={<Checkbox checked={settings.enableLinkHover} onChange={handleChange('enableLinkHover')} />}
                    label="Интерактивные связи (тултип при наведении)"
                />

                <Divider sx={{ my: 1 }} />

                <Typography variant="subtitle2" color="text.secondary">Элементы диаграммы</Typography>
                <FormControlLabel
                    control={<Checkbox checked={settings.showSetups} onChange={handleChange('showSetups')} />}
                    label="Показывать замывки (Setup)"
                />
                <FormControlLabel
                    control={<Checkbox checked={settings.showDowntimes} onChange={handleChange('showDowntimes')} />}
                    label="Показывать выходные (Downtime)"
                />
                <FormControlLabel
                    control={<Checkbox checked={settings.showBatchBrackets} onChange={handleChange('showBatchBrackets')} />}
                    label="Скобки партий"
                />
                <FormControlLabel
                    control={<Checkbox checked={settings.showMinimap} onChange={handleChange('showMinimap')} />}
                    label="Показывать миникарту"
                />
            </Box>
        </DraggableDialog>
    );
};