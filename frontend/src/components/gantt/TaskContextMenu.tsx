// frontend/src/components/gantt/TaskContextMenu.tsx
/**
 * Контекстное меню задачи на диаграмме Ганта (Итерация 13.17).
 *
 * Открывается по клику правой кнопкой мыши на задаче.
 * Содержит действия:
 *  - просмотровые (всегда): открыть карточку, фильтр по партии, операции партии, копирование ID;
 *  - изменяющие (только при !isReadOnly): закрепить/открепить, сдвиг ±1ч.
 *
 * Итерация 13.17 (9b): базовый функционал.
 * Итерация 13.17 (9f): поддержка свёрнутых групп.
 * Итерация 13.17 (9h): readonly-режим — скрываем изменяющие пункты.
 *                    Убран пункт «Отменить задачу» (не реализован на backend).
 */
import React from 'react';
import {Divider, ListItemIcon, ListItemText, Menu, MenuItem,} from '@mui/material';
import {
    ArrowBack as ArrowBackIcon,
    ArrowForward as ArrowForwardIcon,
    ContentCopy as ContentCopyIcon,
    FilterAlt as FilterAltIcon,
    Info as InfoIcon,
    ListAlt as ListAltIcon,
    PushPin as PushPinIcon,
    PushPinOutlined as PushPinOutlinedIcon,
} from '@mui/icons-material';
import type {TaskData} from './types';

export interface TaskContextMenuProps {
    /** Позиция меню (anchorPosition) или null, если закрыто. */
    anchorPosition: { top: number; left: number } | null;
    /** Задача, на которой открыто меню. */
    task: TaskData | null;
    /** Readonly-режим. */
    isReadOnly: boolean;

    // Просмотровые действия (всегда)
    onOpenTaskCard: (task: TaskData) => void;
    onFilterByBatch: (task: TaskData) => void;
    onShowBatchOperations: (task: TaskData) => void;
    onCopyTaskId: (task: TaskData) => void;
    onCopyBatchId: (task: TaskData) => void;

    // Изменяющие действия (только при !isReadOnly)
    onPinTask: (task: TaskData) => void;
    onUnpinTask: (task: TaskData) => void;
    onShiftTask: (task: TaskData, deltaMinutes: number) => void;

    /** Закрыть меню (без действия). */
    onClose: () => void;
}

const TaskContextMenu: React.FC<TaskContextMenuProps> = ({
                                                             anchorPosition,
                                                             task,
                                                             isReadOnly,
                                                             onOpenTaskCard,
                                                             onFilterByBatch,
                                                             onShowBatchOperations,
                                                             onCopyTaskId,
                                                             onCopyBatchId,
                                                             onPinTask,
                                                             onUnpinTask,
                                                             onShiftTask,
                                                             onClose,
                                                         }) => {
    const open = anchorPosition !== null && task !== null;

    const handle = (callback: (t: TaskData) => void) => {
        return () => {
            if (task) callback(task);
            onClose();
        };
    };

    if (!task) {
        return (
            <Menu
                open={false}
                onClose={onClose}
                anchorReference="anchorPosition"
            />
        );
    }

    // Не показываем меню для setup и downtime
    const isSetup = task.item_type === 'setup';
    const isDowntime = task.item_type === 'downtime';
    const isRealTask = !isSetup && !isDowntime;

    const isGroup = task.id.startsWith('__group__');

    const hasBatch =
        !!task.batch_id &&
        !['Замывка', 'Выходной'].includes(task.batch_id);

    return (
        <Menu
            open={open}
            onClose={onClose}
            anchorReference="anchorPosition"
            anchorPosition={anchorPosition ?? undefined}
            slotProps={{
                paper: {
                    sx: {
                        minWidth: 260,
                        boxShadow: '0 4px 16px rgba(0,0,0,0.2)',
                    },
                },
            }}
        >
            {/* Заголовок с именем задачи (не кликается) */}
            <MenuItem disabled sx={{ opacity: 1 }}>
                <ListItemText
                    primary={task.operation_name}
                    secondary={hasBatch
                        ? `Партия ${task.batch_id.substring(0, 8)}`
                        : task.equipment_id}
                    slotProps={{
                        primary: { sx: { fontWeight: 600, fontSize: '0.85rem' } },
                        secondary: { sx: { fontSize: '0.7rem' } },
                    }}
                />
            </MenuItem>

            <Divider />

            {/* ==========================================
                Просмотровые действия (всегда)
            ========================================== */}
            <MenuItem
                onClick={handle(onOpenTaskCard)}
                disabled={!isRealTask}
            >
                <ListItemIcon>
                    <InfoIcon fontSize="small" />
                </ListItemIcon>
                <ListItemText>Открыть карточку задачи</ListItemText>
            </MenuItem>

            {hasBatch && (
                <>
                    <MenuItem onClick={handle(onFilterByBatch)}>
                        <ListItemIcon>
                            <FilterAltIcon fontSize="small" />
                        </ListItemIcon>
                        <ListItemText>Показать только эту партию</ListItemText>
                    </MenuItem>
                    <MenuItem onClick={handle(onShowBatchOperations)}>
                        <ListItemIcon>
                            <ListAltIcon fontSize="small" />
                        </ListItemIcon>
                        <ListItemText>Все операции партии</ListItemText>
                    </MenuItem>
                </>
            )}

            {/* ==========================================
                Изменяющие действия (только при !isReadOnly)
                Не показываем для групп (виртуальные задачи).
            ========================================== */}
            {!isReadOnly && isRealTask && !isGroup && (
                <>
                    <Divider />

                    {task.is_pinned ? (
                        <MenuItem onClick={handle(onUnpinTask)}>
                            <ListItemIcon>
                                <PushPinOutlinedIcon fontSize="small" />
                            </ListItemIcon>
                            <ListItemText>Открепить</ListItemText>
                        </MenuItem>
                    ) : (
                        <MenuItem onClick={handle(onPinTask)}>
                            <ListItemIcon>
                                <PushPinIcon fontSize="small" />
                            </ListItemIcon>
                            <ListItemText>Закрепить</ListItemText>
                        </MenuItem>
                    )}

                    <MenuItem onClick={handle(() => onShiftTask(task, -60))}>
                        <ListItemIcon>
                            <ArrowBackIcon fontSize="small" />
                        </ListItemIcon>
                        <ListItemText>Сдвинуть на 1 час влево</ListItemText>
                    </MenuItem>
                    <MenuItem onClick={handle(() => onShiftTask(task, +60))}>
                        <ListItemIcon>
                            <ArrowForwardIcon fontSize="small" />
                        </ListItemIcon>
                        <ListItemText>Сдвинуть на 1 час вправо</ListItemText>
                    </MenuItem>
                </>
            )}

            {/* ==========================================
                Копирование (всегда)
            ========================================== */}
            <Divider />

            <MenuItem onClick={handle(onCopyTaskId)}>
                <ListItemIcon>
                    <ContentCopyIcon fontSize="small" />
                </ListItemIcon>
                <ListItemText>Копировать ID задачи</ListItemText>
            </MenuItem>

            {hasBatch && (
                <MenuItem onClick={handle(onCopyBatchId)}>
                    <ListItemIcon>
                        <ContentCopyIcon fontSize="small" />
                    </ListItemIcon>
                    <ListItemText>Копировать ID партии</ListItemText>
                </MenuItem>
            )}
        </Menu>
    );
};

export default TaskContextMenu;