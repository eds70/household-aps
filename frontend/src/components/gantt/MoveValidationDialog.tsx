// frontend/src/components/gantt/MoveValidationDialog.tsx
/**
 * Диалог, показывающий причину запрета перемещения задачи
 * (Итерация 13.17).
 *
 * Открывается, когда backend вернул 400/409 с detail.reason.
 *
 * Итерация 13.17 (9d): добавлена кнопка «Показать задачу» —
 * если валидация заблокирована конкретной задачей, можно
 * перейти к ней на Ганте (центрирование + подсветка).
 */
import React from 'react';
import {Alert, Box, Button, Chip, Typography,} from '@mui/material';
import {
    Block as BlockIcon,
    Error as ErrorIcon,
    PushPin as PushPinIcon,
    Visibility as VisibilityIcon,
} from '@mui/icons-material';
import DraggableDialog from '../common/DraggableDialog';
import type {ValidationErrorState} from '../../types';

interface MoveValidationDialogProps {
    state: ValidationErrorState;
    onClose: () => void;
    /** Опционально: кнопка "Показать задачу". */
    onNavigateToTask?: (taskId: string) => void;
}

const STATUS_LABELS: Record<string, string> = {
    PLANNED: 'Запланирована',
    IN_PROGRESS: 'В работе',
    DONE: 'Выполнена',
    CANCELLED: 'Отменена',
};

const MoveValidationDialog: React.FC<MoveValidationDialogProps> = ({
                                                                       state,
                                                                       onClose,
                                                                       onNavigateToTask,
                                                                   }) => {
    const {open, reason, details, blockedTask} = state;

    const isBlockedByTask = !!blockedTask;
    const canNavigate = isBlockedByTask && !!onNavigateToTask;

    return (
        <DraggableDialog
            open={open}
            onClose={onClose}
            title={
                <Box sx={{display: 'flex', alignItems: 'center', gap: 1}}>
                    {isBlockedByTask
                        ? <PushPinIcon color="warning" />
                        : <BlockIcon color="error" />}
                    <Typography variant="h6" component="div" sx={{fontWeight: 600}}>
                        {isBlockedByTask ? 'Изменение заблокировано' : 'Перемещение запрещено'}
                    </Typography>
                </Box>
            }
            initialWidth={620}
            initialHeight="auto"
            minWidth={480}
            minHeight={280}
            actions={
                <>
                    {canNavigate && (
                        <Button
                            onClick={() => {
                                onNavigateToTask!(blockedTask!.task_id);
                                onClose();
                            }}
                            variant="outlined"
                            color="warning"
                            startIcon={<VisibilityIcon />}
                            sx={{ mr: 'auto' }}
                        >
                            Показать задачу
                        </Button>
                    )}
                    <Button onClick={onClose} variant="contained">
                        Понятно
                    </Button>
                </>
            }
        >
            <Box sx={{display: 'flex', flexDirection: 'column', gap: 2}}>
                <Alert
                    severity={isBlockedByTask ? 'warning' : 'error'}
                    icon={isBlockedByTask ? <PushPinIcon /> : <ErrorIcon />}
                >
                    <Typography variant="body1" sx={{fontWeight: 600, mb: details.length > 0 ? 1 : 0}}>
                        {reason}
                    </Typography>
                    {details.length > 0 && (
                        <Box component="ul" sx={{pl: 2, m: 0}}>
                            {details.map((d, i) => (
                                <li key={i}>
                                    <Typography variant="body2">{d}</Typography>
                                </li>
                            ))}
                        </Box>
                    )}
                </Alert>

                {blockedTask && (
                    <Box
                        sx={{
                            bgcolor: '#fff8e1',
                            border: '1px solid #ffe082',
                            borderRadius: 1,
                            p: 1.5,
                        }}
                    >
                        <Typography variant="caption" color="text.secondary" sx={{display: 'block', mb: 0.5}}>
                            Мешающая задача
                        </Typography>
                        <Box sx={{display: 'flex', alignItems: 'center', gap: 1, mb: 0.5}}>
                            <Typography variant="body2" sx={{fontWeight: 600}}>
                                {blockedTask.operation_name}
                            </Typography>
                            {blockedTask.status && (
                                <Chip
                                    size="small"
                                    variant="outlined"
                                    label={STATUS_LABELS[blockedTask.status] || blockedTask.status}
                                />
                            )}
                        </Box>
                        <Typography variant="caption" sx={{fontFamily: 'monospace', color: 'text.secondary'}}>
                            ID: {blockedTask.task_id.substring(0, 8)}
                        </Typography>
                    </Box>
                )}

                <Typography variant="caption" color="text.secondary">
                    💡 Изменение не было применено. Попробуйте:
                    {' '}
                    {blockedTask
                        ? 'открепить мешающую задачу или сдвинуть её вручную.'
                        : 'изменить время или длительность задачи.'}
                </Typography>
            </Box>
        </DraggableDialog>
    );
};

export default MoveValidationDialog;