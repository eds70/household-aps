// frontend/src/components/gantt/GanttTaskDialog.tsx
/**
 * Диалог расширенной информации о задаче Ганта (Итерация 13.17 + 13.18).
 *
 * Содержит:
 *  - Редактирование времени (start/end).
 *  - Карточку партии (информация о batch), включая статус закрепления.
 *  - Таблицу всех операций партии.
 *  - Баннер для свёрнутой группы LINE_FILL с кнопкой «Развернуть N частей».
 *
 * Не знает про API. Всё — через props.
 */
import React from 'react';
import {
    Alert,
    Box,
    Button,
    Chip,
    Paper,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    TextField,
    Typography,
} from '@mui/material';
import {UnfoldMore as UnfoldMoreIcon,} from '@mui/icons-material';
import DraggableDialog from '../common/DraggableDialog';
import {NON_BATCH_VALUES} from './constants';
import {isGroupTask} from '../../utils/ganttGroups';
import type {TaskData} from '../../types';

export interface GanttTaskDialogProps {
    /** Открыт ли диалог. */
    open: boolean;
    /** Задача, по которой открыт диалог. */
    task: TaskData | null;
    /** Все операции этой партии (уже отсортированы по start). */
    batchTasks: TaskData[];
    /** Режим readonly (просмотр сохранённого плана). */
    isReadOnly: boolean;

    /** Значения формы редактирования (ISO-строки). */
    editFormData: {start: string; end: string};
    /** Изменение значений формы. */
    onEditFormChange: (data: {start: string; end: string}) => void;

    /** Закрыть диалог. */
    onClose: () => void;
    /** Сохранить время. */
    onSave: () => void;
    /** Применить фильтр «только эта партия». */
    onFilterByBatch: (batchId: string) => void;

    /** Итерация 13.17 (9f): развернуть/свернуть группу LINE_FILL. */
    onToggleGroup?: (groupKey: string) => void;
}

// ==========================================
// Утилита форматирования
// ==========================================

const formatDateForInput = (isoString: string): string => {
    const date = new Date(isoString);
    const pad = (n: number) => n.toString().padStart(2, '0');
    return (
        `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
        `T${pad(date.getHours())}:${pad(date.getMinutes())}`
    );
};

const GanttTaskDialog: React.FC<GanttTaskDialogProps> = ({
                                                             open,
                                                             task,
                                                             batchTasks,
                                                             isReadOnly,
                                                             editFormData,
                                                             onEditFormChange,
                                                             onClose,
                                                             onSave,
                                                             onFilterByBatch,
                                                             onToggleGroup,
                                                         }) => {
    // Итерация 13.17 (9f): является ли задача свёрнутой группой?
    const isGroup = task ? isGroupTask(task) : false;
    const groupKey = isGroup && task
        ? task.id.replace('__group__', '')
        : null;
    const groupPartsCount = isGroup && task?.depends_on_task_ids
        ? task.depends_on_task_ids.length
        : 0;

    const isPinned = task?.is_pinned === true;

    return (
        <DraggableDialog
            open={open}
            onClose={onClose}
            title={
                <Box
                    sx={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 1,
                        width: '100%',
                    }}
                >
                    <Typography
                        variant="h6"
                        component="div"
                        sx={{fontWeight: 600}}
                    >
                        {task?.operation_name || 'Задача'}
                    </Typography>
                    {task?.batch_id &&
                        !NON_BATCH_VALUES.has(task.batch_id) && (
                            <Chip
                                size="small"
                                label={`📌 ${task.batch_id.substring(0, 8)}`}
                                color="secondary"
                                variant="outlined"
                            />
                        )}
                    {isPinned && (
                        <Chip
                            size="small"
                            label="📌 Закреплена"
                            color="primary"
                            variant="filled"
                        />
                    )}
                    {isGroup && (
                        <Chip
                            size="small"
                            icon={<UnfoldMoreIcon />}
                            label={`Группа · ${groupPartsCount} частей`}
                            color="info"
                            variant="filled"
                        />
                    )}
                </Box>
            }
            titleExtra={
                <Typography
                    variant="caption"
                    sx={{color: 'text.secondary', fontSize: '0.7rem', mr: 4}}
                >
                    🖱 Перетащите заголовок / угол
                </Typography>
            }
            initialWidth={700}
            initialHeight={600}
            minWidth={480}
            minHeight={400}
            actions={
                <>
                    <Button onClick={onClose}>Закрыть</Button>
                    {!isReadOnly && !isGroup && (
                        <Button onClick={onSave} variant="contained">
                            Сохранить время
                        </Button>
                    )}
                </>
            }
        >
            {task && (
                <Box
                    sx={{
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 2,
                    }}
                >
                    {/* ==========================================
                        Итерация 13.17 (9f): баннер для группы
                    ========================================== */}
                    {isGroup && (
                        <Alert
                            severity="info"
                            icon={<UnfoldMoreIcon />}
                        >
                            <Typography variant="body2" sx={{mb: 1}}>
                                Это свёрнутая группа из{' '}
                                <b>{groupPartsCount}</b> частей операции
                                «{task.operation_name.split(' · ')[0]}».
                                Кликните на задаче на Ганте или нажмите
                                кнопку ниже, чтобы развернуть.
                            </Typography>
                            {onToggleGroup && groupKey && (
                                <Button
                                    size="small"
                                    variant="outlined"
                                    startIcon={<UnfoldMoreIcon />}
                                    onClick={() => {
                                        onToggleGroup(groupKey);
                                        onClose();
                                    }}
                                >
                                    Развернуть {groupPartsCount} частей
                                </Button>
                            )}
                        </Alert>
                    )}

                    {/* ==========================================
                        Итерация 13.18: предупреждение про pinned
                    ========================================== */}
                    {isPinned && !isGroup && !isReadOnly && (
                        <Alert severity="info">
                            <Typography variant="body2">
                                Задача <b>закреплена</b>. Перемещение запрещено.
                                Изменение длительности разрешено.
                                Чтобы переместить — сначала открепите задачу
                                (в контекстном меню).
                            </Typography>
                        </Alert>
                    )}

                    {/* ==========================================
                        Блок 1: Редактирование времени
                        (для группы — не показываем)
                    ========================================== */}
                    {!isReadOnly && !isGroup && (
                        <Box>
                            <Typography
                                variant="subtitle2"
                                sx={{
                                    fontWeight: 700,
                                    mb: 1,
                                    color: '#2c3e50',
                                }}
                            >
                                ⏱ Редактирование времени
                            </Typography>
                            <Box
                                sx={{
                                    display: 'flex',
                                    flexDirection: 'column',
                                    gap: 2,
                                }}
                            >
                                <TextField
                                    margin="dense"
                                    label="Начало"
                                    type="datetime-local"
                                    fullWidth
                                    value={formatDateForInput(
                                        editFormData.start,
                                    )}
                                    onChange={(e) =>
                                        onEditFormChange({
                                            ...editFormData,
                                            start: e.target.value,
                                        })
                                    }
                                    slotProps={{
                                        inputLabel: {shrink: true},
                                        htmlInput: {step: 300},
                                    }}
                                />
                                <TextField
                                    margin="dense"
                                    label="Конец"
                                    type="datetime-local"
                                    fullWidth
                                    value={formatDateForInput(
                                        editFormData.end,
                                    )}
                                    onChange={(e) =>
                                        onEditFormChange({
                                            ...editFormData,
                                            end: e.target.value,
                                        })
                                    }
                                    slotProps={{
                                        inputLabel: {shrink: true},
                                        htmlInput: {step: 300},
                                    }}
                                />
                            </Box>
                        </Box>
                    )}

                    {isReadOnly && !isGroup && (
                        <Alert severity="info">
                            Режим просмотра: редактирование недоступно.
                        </Alert>
                    )}

                    {/* ==========================================
                        Блок 2: Карточка партии
                    ========================================== */}
                    {task.batch_id && !NON_BATCH_VALUES.has(task.batch_id) ? (
                        <Box
                            sx={{
                                bgcolor: '#f8f9fa',
                                border: '1px solid #e0e0e0',
                                borderRadius: 1,
                                p: 1.5,
                            }}
                        >
                            <Typography
                                variant="subtitle2"
                                sx={{
                                    fontWeight: 700,
                                    mb: 1,
                                    color: '#2c3e50',
                                }}
                            >
                                📦 Информация о партии
                            </Typography>
                            <Box
                                sx={{
                                    display: 'grid',
                                    gridTemplateColumns: {
                                        xs: '1fr',
                                        sm: '1fr 1fr',
                                    },
                                    gap: 1,
                                }}
                            >
                                <Box>
                                    <Typography
                                        variant="caption"
                                        color="text.secondary"
                                    >
                                        Партия
                                    </Typography>
                                    <Typography
                                        variant="body2"
                                        sx={{
                                            fontFamily: 'monospace',
                                            fontSize: '0.8rem',
                                        }}
                                    >
                                        {task.batch_id}
                                    </Typography>
                                </Box>
                                <Box>
                                    <Typography
                                        variant="caption"
                                        color="text.secondary"
                                    >
                                        Продукт
                                    </Typography>
                                    <Typography
                                        variant="body2"
                                        sx={{fontWeight: 600}}
                                    >
                                        {task.product_id}
                                    </Typography>
                                </Box>
                                <Box>
                                    <Typography
                                        variant="caption"
                                        color="text.secondary"
                                    >
                                        Роль задачи
                                    </Typography>
                                    <Typography variant="body2">
                                        {task.task_role || '—'}
                                    </Typography>
                                </Box>
                                <Box>
                                    <Typography
                                        variant="caption"
                                        color="text.secondary"
                                    >
                                        Оборудование
                                    </Typography>
                                    <Typography variant="body2">
                                        {task.equipment_id}
                                    </Typography>
                                </Box>

                                {/* Итерация 13.18: статус закрепления */}
                                <Box>
                                    <Typography
                                        variant="caption"
                                        color="text.secondary"
                                    >
                                        Закрепление
                                    </Typography>
                                    <Typography variant="body2">
                                        {isPinned
                                            ? '📌 Закреплена'
                                            : '— Не закреплена'}
                                    </Typography>
                                </Box>

                                <Box>
                                    <Typography
                                        variant="caption"
                                        color="text.secondary"
                                    >
                                        Лаборатория
                                    </Typography>
                                    <Box sx={{mt: 0.25}}>
                                        <Chip
                                            size="small"
                                            label={
                                                task.is_lab_blocked
                                                    ? '🔒 Заблокировано'
                                                    : task.lab_status ===
                                                    'APPROVED'
                                                        ? '✅ Одобрено'
                                                        : task.lab_status ===
                                                        'PENDING_LAB'
                                                            ? '🧪 Ожидает лабу'
                                                            : '— Не требуется'
                                            }
                                            color={
                                                task.is_lab_blocked
                                                    ? 'error'
                                                    : task.lab_status ===
                                                    'APPROVED'
                                                        ? 'success'
                                                        : task.lab_status ===
                                                        'PENDING_LAB'
                                                            ? 'info'
                                                            : 'default'
                                            }
                                            variant={
                                                task.is_lab_blocked
                                                    ? 'filled'
                                                    : 'outlined'
                                            }
                                        />
                                    </Box>
                                    {task.lab_block_reason && (
                                        <Typography
                                            variant="caption"
                                            sx={{
                                                color: 'error.main',
                                                display: 'block',
                                                mt: 0.5,
                                            }}
                                        >
                                            Причина: {task.lab_block_reason}
                                        </Typography>
                                    )}
                                </Box>
                                <Box>
                                    <Typography
                                        variant="caption"
                                        color="text.secondary"
                                    >
                                        Честный Знак
                                    </Typography>
                                    <Box sx={{mt: 0.25}}>
                                        {task.task_role === 'LINE_FILL' ? (
                                            <Box>
                                                <Chip
                                                    size="small"
                                                    label={
                                                        task.cz_status ===
                                                        'COMPLETED'
                                                            ? '🟢 Завершено'
                                                            : task.cz_status ===
                                                            'IN_PROGRESS'
                                                                ? '🔵 В работе'
                                                                : task.cz_status ===
                                                                'PENDING'
                                                                    ? '🟡 Ожидает'
                                                                    : '⚪ Не требуется'
                                                    }
                                                    color={
                                                        task.cz_status ===
                                                        'COMPLETED'
                                                            ? 'success'
                                                            : task.cz_status ===
                                                            'IN_PROGRESS'
                                                                ? 'info'
                                                                : task.cz_status ===
                                                                'PENDING'
                                                                    ? 'warning'
                                                                    : 'default'
                                                    }
                                                    variant="outlined"
                                                />
                                                {task.cz_marked_qty !=
                                                    null && (
                                                        <Typography
                                                            variant="caption"
                                                            sx={{
                                                                display: 'block',
                                                                mt: 0.5,
                                                            }}
                                                        >
                                                            Промаркировано:{' '}
                                                            {task.cz_marked_qty}
                                                        </Typography>
                                                    )}
                                            </Box>
                                        ) : (
                                            <Typography variant="body2">
                                                —
                                            </Typography>
                                        )}
                                    </Box>
                                </Box>
                                <Box>
                                    <Typography
                                        variant="caption"
                                        color="text.secondary"
                                    >
                                        Режим охлаждения
                                    </Typography>
                                    <Typography variant="body2">
                                        {task.cooling_mode === 'slow'
                                            ? '⏳ Замедлено (×1.3)'
                                            : task.cooling_mode === 'fast'
                                                ? '❄️ Обычное'
                                                : '—'}
                                    </Typography>
                                </Box>
                                <Box>
                                    <Typography
                                        variant="caption"
                                        color="text.secondary"
                                    >
                                        Длительность
                                    </Typography>
                                    <Typography variant="body2">
                                        {task.duration_minutes} мин
                                    </Typography>
                                </Box>
                                <Box>
                                    <Typography
                                        variant="caption"
                                        color="text.secondary"
                                    >
                                        Начало / Конец
                                    </Typography>
                                    <Typography
                                        variant="body2"
                                        sx={{fontSize: '0.8rem'}}
                                    >
                                        {new Date(
                                            task.start,
                                        ).toLocaleString('ru-RU')}
                                        <br/>
                                        {new Date(task.end).toLocaleString(
                                            'ru-RU',
                                        )}
                                    </Typography>
                                </Box>
                            </Box>

                            {task.depends_on_task_ids &&
                                task.depends_on_task_ids.length > 0 && (
                                    <Box sx={{mt: 1.5}}>
                                        <Typography
                                            variant="caption"
                                            color="text.secondary"
                                        >
                                            {isGroup
                                                ? 'Части группы'
                                                : 'Зависит от задач'}:{' '}
                                            {
                                                task.depends_on_task_ids
                                                    .length
                                            }
                                        </Typography>
                                        <Box
                                            sx={{
                                                display: 'flex',
                                                gap: 0.5,
                                                flexWrap: 'wrap',
                                                mt: 0.5,
                                            }}
                                        >
                                            {task.depends_on_task_ids
                                                .slice(0, 5)
                                                .map((id) => (
                                                    <Chip
                                                        key={id}
                                                        size="small"
                                                        label={id.substring(
                                                            0,
                                                            8,
                                                        )}
                                                        variant="outlined"
                                                    />
                                                ))}
                                            {task.depends_on_task_ids
                                                .length > 5 && (
                                                <Chip
                                                    size="small"
                                                    label={`+${
                                                        task
                                                            .depends_on_task_ids
                                                            .length - 5
                                                    }`}
                                                    variant="outlined"
                                                />
                                            )}
                                        </Box>
                                    </Box>
                                )}

                            <Box
                                sx={{
                                    mt: 1.5,
                                    display: 'flex',
                                    gap: 1,
                                    flexWrap: 'wrap',
                                }}
                            >
                                <Button
                                    variant="contained"
                                    size="small"
                                    color="secondary"
                                    onClick={() =>
                                        onFilterByBatch(task.batch_id)
                                    }
                                >
                                    📌 Показать только эту партию
                                </Button>
                            </Box>
                        </Box>
                    ) : (
                        <Alert severity="info" icon={false}>
                            Задача не привязана к партии (
                            {task.batch_id || 'нет'})
                        </Alert>
                    )}

                    {/* ==========================================
                        Блок 3: Все операции партии
                        (для группы — не показываем список)
                    ========================================== */}
                    {!isGroup && batchTasks.length > 1 && (
                        <Box>
                            <Typography
                                variant="subtitle2"
                                sx={{
                                    fontWeight: 700,
                                    mb: 1,
                                    color: '#2c3e50',
                                }}
                            >
                                🔧 Все операции партии ({batchTasks.length})
                            </Typography>
                            <TableContainer
                                component={Paper}
                                variant="outlined"
                            >
                                <Table size="small" stickyHeader>
                                    <TableHead>
                                        <TableRow>
                                            <TableCell
                                                sx={{fontWeight: 600}}
                                            >
                                                Операция
                                            </TableCell>
                                            <TableCell
                                                sx={{fontWeight: 600}}
                                            >
                                                Оборудование
                                            </TableCell>
                                            <TableCell
                                                sx={{fontWeight: 600}}
                                            >
                                                Роль
                                            </TableCell>
                                            <TableCell
                                                sx={{fontWeight: 600}}
                                                align="right"
                                            >
                                                Длит.
                                            </TableCell>
                                            <TableCell
                                                sx={{fontWeight: 600}}
                                            >
                                                Начало
                                            </TableCell>
                                        </TableRow>
                                    </TableHead>
                                    <TableBody>
                                        {batchTasks.map((t) => {
                                            const isCurrent =
                                                t.id === task.id;
                                            return (
                                                <TableRow
                                                    key={t.id}
                                                    hover
                                                    selected={isCurrent}
                                                    sx={{
                                                        cursor: 'pointer',
                                                        bgcolor: isCurrent
                                                            ? '#e3f2fd'
                                                            : undefined,
                                                    }}
                                                >
                                                    <TableCell>
                                                        <Typography
                                                            variant="caption"
                                                            sx={{
                                                                fontWeight:
                                                                    isCurrent
                                                                        ? 700
                                                                        : 400,
                                                            }}
                                                        >
                                                            {t.is_pinned ? '📌 ' : ''}
                                                            {
                                                                t.operation_name
                                                            }
                                                        </Typography>
                                                    </TableCell>
                                                    <TableCell>
                                                        <Typography variant="caption">
                                                            {t.equipment_id}
                                                        </Typography>
                                                    </TableCell>
                                                    <TableCell>
                                                        <Typography variant="caption">
                                                            {t.task_role ||
                                                                '—'}
                                                        </Typography>
                                                    </TableCell>
                                                    <TableCell align="right">
                                                        <Typography variant="caption">
                                                            {
                                                                t.duration_minutes
                                                            }{' '}
                                                            мин
                                                        </Typography>
                                                    </TableCell>
                                                    <TableCell>
                                                        <Typography variant="caption">
                                                            {new Date(
                                                                t.start,
                                                            ).toLocaleString(
                                                                'ru-RU',
                                                            )}
                                                        </Typography>
                                                    </TableCell>
                                                </TableRow>
                                            );
                                        })}
                                    </TableBody>
                                </Table>
                            </TableContainer>
                        </Box>
                    )}
                </Box>
            )}
        </DraggableDialog>
    );
};

export default GanttTaskDialog;