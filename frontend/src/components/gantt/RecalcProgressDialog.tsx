// frontend/src/components/gantt/RecalcProgressDialog.tsx
/**
 * Модальное окно прогресса пересчёта плана (Итерация 13.20).
 *
 * Открывается, пока solver работает (30–120 секунд).
 * Показывает:
 *  - Крутящийся спиннер.
 *  - Текст: что происходит.
 *  - Таймер: сколько секунд прошло (пользователь видит, что система жива).
 *  - Пояснение про timeout.
 *
 * НЕ имеет кнопки «Отмена» — прервать solver с фронта нельзя,
 * запрос уже отправлен на сервер. Ждём завершения.
 *
 * Автоматически закрывается, когда recalculating становится false.
 */
import React, {useEffect, useRef, useState} from 'react';
import {Alert, Box, CircularProgress, Dialog, DialogContent, LinearProgress, Typography,} from '@mui/material';
import {HourglassEmpty as HourglassIcon} from '@mui/icons-material';

interface RecalcProgressDialogProps {
    /** Открыт ли диалог. */
    open: boolean;
    /** Текст операции: «Построение плана», «Пересчёт плана» и т.д. */
    operationLabel: string;
    /** Опциональный комментарий — что именно делаем. */
    operationHint?: string;
    /** Общий таймаут (сек) — для отображения границы. */
    timeoutSeconds?: number;
}

const RecalcProgressDialog: React.FC<RecalcProgressDialogProps> = ({
                                                                       open,
                                                                       operationLabel,
                                                                       operationHint,
                                                                       timeoutSeconds,
                                                                   }) => {
    const [elapsedSeconds, setElapsedSeconds] = useState(0);
    const startTimeRef = useRef<number | null>(null);

    // Сбрасываем счётчик при каждом открытии
    useEffect(() => {
        if (open) {
            startTimeRef.current = Date.now();
            setElapsedSeconds(0);
        } else {
            startTimeRef.current = null;
        }
    }, [open]);

    // Тикаем каждую секунду, пока открыто
    useEffect(() => {
        if (!open) return;

        const timer = setInterval(() => {
            if (startTimeRef.current !== null) {
                setElapsedSeconds(
                    Math.floor((Date.now() - startTimeRef.current) / 1000),
                );
            }
        }, 1000);

        return () => clearInterval(timer);
    }, [open]);

    // Форматируем «MM:SS»
    const formatElapsed = (sec: number): string => {
        const m = Math.floor(sec / 60);
        const s = sec % 60;
        return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    };

    const progressValue = timeoutSeconds
        ? Math.min(100, (elapsedSeconds / timeoutSeconds) * 100)
        : undefined;

    return (
        <Dialog
            open={open}
            maxWidth="sm"
            fullWidth
            slotProps={{
                paper: {
                    sx: {
                        borderRadius: 2,
                        boxShadow: '0 8px 32px rgba(0,0,0,0.35)',
                    },
                },
            }}
        >
            <DialogContent sx={{py: 4, px: 4}}>
                <Box
                    sx={{
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        gap: 3,
                    }}
                >
                    {/* Иконка/спиннер */}
                    <Box sx={{position: 'relative', display: 'inline-flex'}}>
                        <CircularProgress
                            size={80}
                            thickness={3}
                            color="primary"
                        />
                        <Box
                            sx={{
                                position: 'absolute',
                                top: 0,
                                left: 0,
                                right: 0,
                                bottom: 0,
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                            }}
                        >
                            <HourglassIcon sx={{fontSize: 32, color: '#2c3e50'}} />
                        </Box>
                    </Box>

                    {/* Заголовок */}
                    <Box sx={{textAlign: 'center'}}>
                        <Typography
                            variant="h6"
                            sx={{fontWeight: 600, mb: 0.5, color: '#2c3e50'}}
                        >
                            {operationLabel}
                        </Typography>
                        {operationHint && (
                            <Typography variant="body2" color="text.secondary">
                                {operationHint}
                            </Typography>
                        )}
                    </Box>

                    {/* Таймер */}
                    <Box
                        sx={{
                            bgcolor: '#f8f9fa',
                            border: '1px solid #e0e0e0',
                            borderRadius: 2,
                            px: 3,
                            py: 1.5,
                            textAlign: 'center',
                            minWidth: 220,
                        }}
                    >
                        <Typography
                            variant="caption"
                            color="text.secondary"
                            sx={{
                                display: 'block',
                                letterSpacing: 1,
                                textTransform: 'uppercase',
                                fontSize: '0.7rem',
                            }}
                        >
                            Прошло времени
                        </Typography>
                        <Typography
                            variant="h4"
                            sx={{
                                fontFamily: 'monospace',
                                fontWeight: 700,
                                color: '#2c3e50',
                                mt: 0.5,
                            }}
                        >
                            {formatElapsed(elapsedSeconds)}
                        </Typography>
                    </Box>

                    {/* Прогресс-бар, если известен timeout */}
                    {progressValue !== undefined && timeoutSeconds && (
                        <Box sx={{width: '100%'}}>
                            <LinearProgress
                                variant="determinate"
                                value={progressValue}
                                sx={{
                                    height: 6,
                                    borderRadius: 3,
                                    bgcolor: '#ecf0f1',
                                }}
                            />
                            <Typography
                                variant="caption"
                                color="text.secondary"
                                sx={{
                                    display: 'block',
                                    mt: 0.5,
                                    textAlign: 'center',
                                }}
                            >
                                Расчёт обычно занимает 30–120 секунд.
                                Максимум — {timeoutSeconds} сек.
                            </Typography>
                        </Box>
                    )}

                    {/* Предупреждение */}
                    <Alert
                        severity="info"
                        icon={false}
                        sx={{
                            width: '100%',
                            bgcolor: '#e3f2fd',
                            '& .MuiAlert-message': {width: '100%'},
                        }}
                    >
                        <Typography variant="body2" sx={{textAlign: 'center'}}>
                            <b>Не закрывайте страницу</b> и не перезагружайте её.
                            Solver OR-Tools ищет оптимальное решение —
                            это может занять до {timeoutSeconds ?? 120} секунд.
                        </Typography>
                    </Alert>
                </Box>
            </DialogContent>
        </Dialog>
    );
};

export default RecalcProgressDialog;