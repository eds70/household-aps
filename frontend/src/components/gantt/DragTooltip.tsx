// frontend/src/components/gantt/DragTooltip.tsx
/**
 * Tooltip, показываемый при перетаскивании задачи и при изменении
 * её длительности (Итерация 13.17 + 13.18).
 *
 * Итерация 13.18 (fix #5):
 *  - Показывает тип операции: перемещение / изменение длительности.
 *  - Показывает исходное и новое время начала/окончания.
 *  - Показывает Δ в минутах.
 *  - Позиционирование через transform: translate — без reflow,
 *    без мерцания при быстром движении.
 *  - transition: none — tooltip не «догоняет» курсор.
 *  - will-change: transform — подсказка браузеру.
 */
import React from 'react';
import {Box, Paper, Typography} from '@mui/material';
import {
    AccessTime as TimeIcon,
    CompareArrows as MoveIcon,
    Warning as WarningIcon,
    WidthNormal as ResizeIcon,
} from '@mui/icons-material';
import type {DragTooltipState} from '../../types';

interface DragTooltipProps {
    state: DragTooltipState | null;
}

// ==========================================
// Хелпер: форматирование даты/времени
// ==========================================

const formatDateTime = (iso: string | undefined): string => {
    if (!iso) return '—';
    const d = new Date(iso);
    if (isNaN(d.getTime())) return '—';

    const now = new Date();
    const isToday = d.toDateString() === now.toDateString();

    const time = d.toLocaleTimeString('ru-RU', {
        hour: '2-digit',
        minute: '2-digit',
    });

    if (isToday) return time;

    const date = d.toLocaleDateString('ru-RU', {
        day: '2-digit',
        month: '2-digit',
    });
    return `${date} ${time}`;
};

const DragTooltip: React.FC<DragTooltipProps> = ({state}) => {
    if (!state) return null;

    const isResize = state.operationType === 'resize';
    const icon = isResize
        ? <ResizeIcon sx={{fontSize: 14}}/>
        : <MoveIcon sx={{fontSize: 14}}/>;
    const operationLabel = isResize
        ? 'Изменение длительности'
        : 'Перемещение';

    return (
        <Paper
            elevation={8}
            sx={{
                position: 'fixed',
                left: 0,
                top: 0,
                transform: `translate(${state.x}px, ${state.y}px)`,
                willChange: 'transform',
                transition: 'none',
                p: 1,
                zIndex: 9999,
                pointerEvents: 'none',
                bgcolor: '#2c3e50',
                color: 'white',
                borderRadius: 1,
                maxWidth: 360,
                boxShadow: '0 4px 16px rgba(0,0,0,0.4)',
            }}
        >
            {/* Заголовок: тип операции */}
            <Box
                sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 0.5,
                    mb: 0.25,
                }}
            >
                {icon}
                <Typography
                    variant="caption"
                    sx={{
                        fontWeight: 700,
                        fontSize: '0.75rem',
                        letterSpacing: 0.3,
                    }}
                >
                    {operationLabel}
                </Typography>
            </Box>

            {/* Основной текст */}
            <Box sx={{display: 'flex', alignItems: 'center', gap: 0.5}}>
                <TimeIcon sx={{fontSize: 14}}/>
                <Typography
                    variant="caption"
                    sx={{fontFamily: 'monospace', fontWeight: 700}}
                >
                    {state.text}
                </Typography>
            </Box>

            {/* Текущее время начала/окончания */}
            {(state.startTime || state.endTime) && (
                <Box
                    sx={{
                        mt: 0.5,
                        pt: 0.5,
                        borderTop: '1px solid rgba(255,255,255,0.15)',
                    }}
                >
                    <Typography
                        variant="caption"
                        sx={{
                            display: 'block',
                            fontFamily: 'monospace',
                            fontSize: '0.72rem',
                            lineHeight: 1.5,
                        }}
                    >
                        🕐 Начало: <b>{formatDateTime(state.startTime)}</b>
                    </Typography>
                    <Typography
                        variant="caption"
                        sx={{
                            display: 'block',
                            fontFamily: 'monospace',
                            fontSize: '0.72rem',
                            lineHeight: 1.5,
                        }}
                    >
                        🏁 Конец: <b>{formatDateTime(state.endTime)}</b>
                    </Typography>
                </Box>
            )}

            {/* Исходное время */}
            {(state.originalStart || state.originalEnd) && (
                <Box
                    sx={{
                        mt: 0.5,
                        pt: 0.5,
                        borderTop: '1px dashed rgba(255,255,255,0.15)',
                    }}
                >
                    <Typography
                        variant="caption"
                        sx={{
                            display: 'block',
                            fontFamily: 'monospace',
                            fontSize: '0.68rem',
                            color: 'rgba(255,255,255,0.6)',
                            lineHeight: 1.5,
                        }}
                    >
                        Было: {formatDateTime(state.originalStart)} —{' '}
                        {formatDateTime(state.originalEnd)}
                    </Typography>
                </Box>
            )}

            {/* Δ изменения */}
            {state.deltaMinutes !== undefined && state.deltaMinutes !== 0 && (
                <Typography
                    variant="caption"
                    sx={{
                        display: 'block',
                        fontFamily: 'monospace',
                        color: state.deltaMinutes > 0 ? '#2ecc71' : '#e74c3c',
                        mt: 0.25,
                        fontWeight: 600,
                    }}
                >
                    Δ {state.deltaMinutes > 0 ? '+' : ''}
                    {state.deltaMinutes} мин
                </Typography>
            )}

            {/* Количество сдвигаемых задач */}
            {state.affectedCount !== undefined && state.affectedCount > 0 && (
                <Typography
                    variant="caption"
                    sx={{display: 'block', mt: 0.25, color: '#f39c12'}}
                >
                    Сдвинется задач: {state.affectedCount}
                </Typography>
            )}

            {/* Предупреждение */}
            {state.warning && (
                <Box
                    sx={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 0.5,
                        mt: 0.5,
                        pt: 0.5,
                        borderTop: '1px solid rgba(255,255,255,0.2)',
                    }}
                >
                    <WarningIcon sx={{fontSize: 12, color: '#f39c12'}}/>
                    <Typography
                        variant="caption"
                        sx={{color: '#f39c12', fontSize: '0.7rem'}}
                    >
                        {state.warning}
                    </Typography>
                </Box>
            )}
        </Paper>
    );
};

export default DragTooltip;