// frontend/src/components/common/ConfirmDialog.tsx
import React from 'react';
import {Box, Button, Typography} from '@mui/material';
import {ErrorOutlined as ErrorIcon, InfoOutlined as InfoIcon, Warning as WarningIcon,} from '@mui/icons-material';
import DraggableDialog from './DraggableDialog';

export interface ConfirmDialogProps {
    open: boolean;
    title: string;
    message: string | React.ReactNode;
    confirmText?: string;
    cancelText?: string;
    severity?: 'warning' | 'error' | 'info';
    onConfirm: () => void;
    onCancel: () => void;
    loading?: boolean;
}

export const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
                                                                open,
                                                                title,
                                                                message,
                                                                confirmText = 'Подтвердить',
                                                                cancelText = 'Закрыть',
                                                                severity = 'warning',
                                                                onConfirm,
                                                                onCancel,
                                                                loading = false,
                                                            }) => {
    const iconColor = severity === 'error' ? '#d32f2f' : severity === 'warning' ? '#ed6c02' : '#0288d1';

    const IconComponent = severity === 'error'
        ? ErrorIcon
        : severity === 'warning'
            ? WarningIcon
            : InfoIcon;

    return (
        <DraggableDialog
            open={open}
            onClose={onCancel}
            title={title}
            initialWidth={450}
            initialHeight="auto"
            minWidth={400}
            minHeight={200}
            actions={
                <>
                    <Button
                        onClick={onCancel}
                        disabled={loading}
                        sx={{textTransform: 'none'}}
                    >
                        {cancelText}
                    </Button>
                    <Button
                        onClick={onConfirm}
                        variant="contained"
                        color={severity === 'error' ? 'error' : 'primary'}
                        disabled={loading}
                        sx={{textTransform: 'none'}}
                    >
                        {loading ? 'Обработка...' : confirmText}
                    </Button>
                </>
            }
        >
            <Box sx={{ display: 'flex', gap: 2, alignItems: 'flex-start', mt: 1 }}>
                <IconComponent sx={{ color: iconColor, fontSize: 32, mt: 0.5 }} />
                <Box sx={{ flexGrow: 1 }}>
                    {typeof message === 'string' ? (
                        <Typography variant="body1">{message}</Typography>
                    ) : (
                        message
                    )}
                </Box>
            </Box>
        </DraggableDialog>
    );
};