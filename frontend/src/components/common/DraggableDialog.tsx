// frontend/src/components/common/DraggableDialog.tsx
import React, {useCallback, useEffect, useRef, useState} from 'react';
import {Box, Dialog, DialogActions, DialogContent, DialogTitle, IconButton, Tooltip, Typography,} from '@mui/material';
import {Close as CloseIcon} from '@mui/icons-material';

/**
 * Базовый перетаскиваемый диалог с изменяемым размером.
 *
 * Свойства (все опциональны):
 *   - draggable (по умолчанию true) — перетаскивание за заголовок.
 *   - resizable (по умолчанию true) — изменение размера за угол.
 *   - closeOnBackdropClick (по умолчанию false) — закрытие по клику вне.
 *   - showCloseButton (по умолчанию true) — иконка "✕" в правом верхнем углу.
 *   - initialWidth / initialHeight — стартовый размер.
 *   - minWidth / minHeight — минимальные размеры.
 *
 * Escape (Esc) всегда закрывает диалог — это стандартное поведение.
 *
 * Использование:
 *   <DraggableDialog
 *       open={open}
 *       onClose={handleClose}
 *       title="Заголовок"
 *       actions={<Button onClick={handleClose}>Отмена</Button>}
 *   >
 *       ...содержимое...
 *   </DraggableDialog>
 */

interface DraggableDialogProps {
    open: boolean;
    onClose: () => void;
    title: React.ReactNode;
    children: React.ReactNode;
    actions?: React.ReactNode;

    // Поведение
    draggable?: boolean;
    resizable?: boolean;
    closeOnBackdropClick?: boolean;
    showCloseButton?: boolean;
    disableBackdropClick?: boolean;

    // Размеры
    initialWidth?: number | string;
    initialHeight?: number | string;
    minWidth?: number;
    minHeight?: number;
    maxWidth?: number | string;
    maxHeight?: number | string;

    // Дополнительные стили
    dialogSx?: object;
    contentSx?: object;
    titleSx?: object;

    // Дополнительный элемент в шапке (слева от кнопки закрытия)
    titleExtra?: React.ReactNode;
}

const DraggableDialog: React.FC<DraggableDialogProps> = ({
                                                             open,
                                                             onClose,
                                                             title,
                                                             children,
                                                             actions,
                                                             draggable = true,
                                                             resizable = true,
                                                             closeOnBackdropClick = false,
                                                             showCloseButton = true,
                                                             disableBackdropClick,
                                                             initialWidth = 700,
                                                             initialHeight = 'auto',
                                                             minWidth = 480,
                                                             minHeight = 320,
                                                             maxWidth,
                                                             maxHeight,
                                                             dialogSx,
                                                             contentSx,
                                                             titleSx,
                                                             titleExtra,
                                                         }) => {
    const paperRef = useRef<HTMLDivElement | null>(null);
    const [dialogWidth, setDialogWidth] = useState<number | string>(initialWidth);
    const [dialogHeight, setDialogHeight] = useState<number | string>(initialHeight);
    const [position, setPosition] = useState<{ left: number; top: number } | null>(null);

    // Сбрасываем позицию и размеры при каждом открытии
    useEffect(() => {
        if (open) {
            setDialogWidth(initialWidth);
            setDialogHeight(initialHeight);
            setPosition(null);
        }
    }, [open, initialWidth, initialHeight]);

    // Применяем позицию и размеры к .MuiDialog-paper
    useEffect(() => {
        if (!paperRef.current) return;
        const el = paperRef.current;

        if (position) {
            el.style.margin = '0';
            el.style.position = 'fixed';
            el.style.left = `${position.left}px`;
            el.style.top = `${position.top}px`;
            el.style.right = 'auto';
            el.style.bottom = 'auto';
        } else {
            el.style.margin = '';
            el.style.position = '';
            el.style.left = '';
            el.style.top = '';
            el.style.right = '';
            el.style.bottom = '';
        }

        el.style.width = typeof dialogWidth === 'number'
            ? `${dialogWidth}px`
            : dialogWidth;
        el.style.height = typeof dialogHeight === 'number'
            ? `${dialogHeight}px`
            : dialogHeight;
        el.style.maxWidth = maxWidth
            ? (typeof maxWidth === 'number' ? `${maxWidth}px` : maxWidth)
            : '';
        el.style.maxHeight = maxHeight
            ? (typeof maxHeight === 'number' ? `${maxHeight}px` : maxHeight)
            : '';
    }, [position, dialogWidth, dialogHeight, maxWidth, maxHeight]);

    // ==========================================
    // Drag за заголовок
    // ==========================================
    const handleTitleMouseDown = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
        if (!draggable) return;

        const target = e.target as HTMLElement;
        // Игнорируем клики по кнопкам/чипам/иконкам в шапке
        if (
            target.closest('button') ||
            target.closest('.MuiChip-root') ||
            target.closest('.MuiIconButton-root') ||
            target.closest('a')
        ) {
            return;
        }

        const paperEl = paperRef.current;
        if (!paperEl) return;

        const rect = paperEl.getBoundingClientRect();
        const startX = e.clientX;
        const startY = e.clientY;
        const startLeft = rect.left;
        const startTop = rect.top;

        const onMouseMove = (ev: MouseEvent) => {
            const dx = ev.clientX - startX;
            const dy = ev.clientY - startY;
            setPosition({
                left: startLeft + dx,
                top: startTop + dy,
            });
        };

        const onMouseUp = () => {
            document.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('mouseup', onMouseUp);
        };

        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
    }, [draggable]);

    // ==========================================
    // Resize за правый нижний угол
    // ==========================================
    const handleResizeMouseDown = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
        if (!resizable) return;
        e.stopPropagation();
        e.preventDefault();

        const paperEl = paperRef.current;
        if (!paperEl) return;

        const rect = paperEl.getBoundingClientRect();
        const startX = e.clientX;
        const startY = e.clientY;
        const startWidth = rect.width;
        const startHeight = rect.height;

        const onMouseMove = (ev: MouseEvent) => {
            const dx = ev.clientX - startX;
            const dy = ev.clientY - startY;

            let newWidth = Math.max(minWidth, startWidth + dx);
            let newHeight = Math.max(minHeight, startHeight + dy);

            // Ограничения по экрану
            const screenMaxW = window.innerWidth * 0.95;
            const screenMaxH = window.innerHeight * 0.9;
            newWidth = Math.min(newWidth, screenMaxW);
            newHeight = Math.min(newHeight, screenMaxH);

            setDialogWidth(newWidth);
            setDialogHeight(newHeight);
        };

        const onMouseUp = () => {
            document.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('mouseup', onMouseUp);
        };

        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
    }, [resizable, minWidth, minHeight]);

    // ==========================================
    // Закрытие
    // ==========================================
    const handleClose = (_event: any, reason: string) => {
        // Не закрываем по клику вне (backdropClick)
        if (
            reason === 'backdropClick' &&
            !closeOnBackdropClick &&
            disableBackdropClick !== false
        ) {
            return;
        }
        onClose();
    };

    return (
        <Dialog
            open={open}
            onClose={handleClose}
            maxWidth={false}
            fullWidth={false}
            slotProps={{
                root: {
                    sx: {
                        '& .MuiDialog-container': {
                            alignItems: 'flex-start',
                            justifyContent: 'flex-start',
                            padding: 0,
                        },
                    },
                },
                paper: {
                    ref: paperRef,
                    sx: {
                        display: 'flex',
                        flexDirection: 'column',
                        position: 'relative',
                        overflow: 'hidden',
                        minWidth,
                        minHeight,
                        ...dialogSx,
                    },
                },
            }}
        >
            {/* ==========================================
                Ручка-ресайзер в правом нижнем углу
                ========================================== */}
            {resizable && (
                <Box
                    onMouseDown={handleResizeMouseDown}
                    sx={{
                        position: 'absolute',
                        right: 0,
                        bottom: 0,
                        width: 20,
                        height: 20,
                        cursor: 'nwse-resize',
                        zIndex: 10,
                        '&::before': {
                            content: '""',
                            position: 'absolute',
                            right: 3,
                            bottom: 3,
                            width: 12,
                            height: 12,
                            borderRight: '2px solid #bdc3c7',
                            borderBottom: '2px solid #bdc3c7',
                            transition: 'border-color 0.15s',
                        },
                        '&:hover::before': {
                            borderRightColor: '#3498db',
                            borderBottomColor: '#3498db',
                        },
                        '&::after': {
                            content: '""',
                            position: 'absolute',
                            right: 0,
                            bottom: 0,
                            width: 20,
                            height: 20,
                        },
                    }}
                />
            )}

            {/* ==========================================
                Заголовок (drag-зона) + кнопка "Закрыть"
                ========================================== */}
            <DialogTitle
                onMouseDown={handleTitleMouseDown}
                sx={{
                    fontWeight: 600,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1,
                    cursor: draggable ? 'move' : 'default',
                    userSelect: 'none',
                    flexShrink: 0,
                    borderBottom: '1px solid #e0e0e0',
                    pr: showCloseButton ? 6 : 3,
                    '&:active': {
                        cursor: draggable ? 'grabbing' : 'default',
                    },
                    ...titleSx,
                }}
            >
                <Box sx={{flexGrow: 1, minWidth: 0}}>
                    {typeof title === 'string' ? (
                        <Typography variant="h6" component="div" sx={{fontWeight: 600}}>
                            {title}
                        </Typography>
                    ) : (
                        title
                    )}
                </Box>

                {titleExtra}

                {showCloseButton && (
                    <Tooltip title="Закрыть">
                        <IconButton
                            onClick={onClose}
                            size="small"
                            sx={{
                                position: 'absolute',
                                right: 8,
                                top: 8,
                            }}
                        >
                            <CloseIcon fontSize="small" />
                        </IconButton>
                    </Tooltip>
                )}
            </DialogTitle>

            {/* ==========================================
                Содержимое (скроллируемое)
                ========================================== */}
            <DialogContent
                dividers
                sx={{
                    flexGrow: 1,
                    minHeight: 0,
                    overflowY: 'auto',
                    pt: 2,
                    ...contentSx,
                }}
            >
                {children}
            </DialogContent>

            {/* ==========================================
                Действия (если переданы)
                ========================================== */}
            {actions && (
                <DialogActions
                    sx={{
                        px: 3,
                        py: 1.5,
                        flexShrink: 0,
                        borderTop: '1px solid #e0e0e0',
                    }}
                >
                    {actions}
                </DialogActions>
            )}
        </Dialog>
    );
};

export default DraggableDialog;