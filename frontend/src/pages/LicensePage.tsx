// frontend/src/pages/LicensePage.tsx
import React, {useCallback, useEffect, useState} from 'react';
import {
    Alert,
    Box,
    Button,
    Card,
    CardContent,
    Chip,
    CircularProgress,
    Divider,
    Grid,
    IconButton,
    Snackbar,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Tooltip,
    Typography,
} from '@mui/material';
import {
    CheckCircle as CheckCircleIcon,
    ContentCopy as ContentCopyIcon,
    ErrorOutlined as ErrorOutlineIcon,
    Info as InfoIcon,
    Refresh as RefreshIcon,
    WarningAmber as WarningAmberIcon,
    WorkspacePremium as WorkspacePremiumIcon,
} from '@mui/icons-material';
import {licenseApi} from '../services/api';
import type {LicenseInfo, LicenseInstanceResponse, LicenseTier,} from '../types';

// ==========================================
// КОНСТАНТЫ
// ==========================================

const TIER_LABELS: Record<LicenseTier, string> = {
    trial: 'Trial (пробная)',
    community: 'Community',
    enterprise: 'Enterprise',
};

const ALL_FEATURES: { key: string; label: string }[] = [
    { key: 'audit_export', label: 'Экспорт аудита в Excel' },
    { key: 'whatif', label: 'What-if сценарии' },
    { key: 'cz', label: 'Честный Знак (маркировка)' },
    { key: 'multi_objective', label: 'Multi-objective оптимизация' },
    { key: 'help_crud', label: 'Редактирование статей справки через UI' },
];

// ==========================================
// КОМПОНЕНТ
// ==========================================

const LicensePage: React.FC = () => {
    const [info, setInfo] = useState<LicenseInfo | null>(null);
    const [instance, setInstance] = useState<LicenseInstanceResponse | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [copied, setCopied] = useState(false);

    // ==========================================
    // ЗАГРУЗКА
    // ==========================================
    const load = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const [i, inst] = await Promise.all([
                licenseApi.getInfo(),
                licenseApi.getInstance(),
            ]);
            setInfo(i);
            setInstance(inst);
        } catch (err: any) {
            const detail = err.response?.data?.detail;
            setError(
                typeof detail === 'string'
                    ? detail
                    : 'Ошибка загрузки данных лицензии',
            );
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        load();
    }, [load]);

    // ==========================================
    // КОПИРОВАНИЕ instance_id
    // ==========================================
    const handleCopyInstanceId = async () => {
        if (!instance?.instance_id) return;
        try {
            await navigator.clipboard.writeText(instance.instance_id);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        } catch {
            // Fallback: выделяем текст
            setError('Не удалось скопировать в буфер. Скопируйте вручную.');
        }
    };

    // ==========================================
    // ОТОБРАЖЕНИЕ СТАТУСА
    // ==========================================
    const statusColor = (): 'success' | 'warning' | 'error' | 'info' => {
        if (!info) return 'info';
        if (!info.valid || info.is_expired) return 'error';
        if (info.days_left !== null && info.days_left <= 14) return 'warning';
        return 'success';
    };

    const statusIcon = () => {
        const color = statusColor();
        if (color === 'success')
            return <CheckCircleIcon sx={{ fontSize: 32 }} />;
        if (color === 'warning')
            return <WarningAmberIcon sx={{ fontSize: 32 }} />;
        if (color === 'error')
            return <ErrorOutlineIcon sx={{ fontSize: 32 }} />;
        return <InfoIcon sx={{ fontSize: 32 }} />;
    };

    const statusLabel = (): string => {
        if (!info) return 'Загрузка...';
        if (!info.valid) return 'Лицензия недействительна';
        if (info.is_expired) return 'Лицензия истекла';
        if (info.days_left !== null && info.days_left <= 14)
            return `Лицензия истекает через ${info.days_left} дн.`;
        return 'Лицензия действительна';
    };

    const statusDescription = (): string => {
        if (!info) return '';
        if (!info.valid) return info.error || 'Лицензия не проверена';
        if (info.is_expired) return `Истекла ${formatDate(info.expires_at)}`;
        if (info.days_left !== null && info.days_left <= 14)
            return `Действует до ${formatDate(info.expires_at)}. Продлите лицензию.`;
        return `Действует до ${formatDate(info.expires_at)}`;
    };

    const formatDate = (iso: string | null): string => {
        if (!iso) return '—';
        return new Date(iso).toLocaleDateString('ru-RU', {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric',
        });
    };

    const formatDateTime = (iso: string | null): string => {
        if (!iso) return '—';
        return new Date(iso).toLocaleString('ru-RU', {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
        });
    };

    // ==========================================
    // РЕНДЕР
    // ==========================================
    return (
        <Box sx={{ height: '100%', overflow: 'auto', p: { xs: 1, md: 2 } }}>
            {/* Заголовок */}
            <Box
                sx={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    flexWrap: 'wrap',
                    gap: 2,
                    mb: 2,
                }}
            >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                    <WorkspacePremiumIcon
                        color="primary"
                        sx={{ fontSize: 32 }}
                    />
                    <Typography
                        variant="h5"
                        sx={{ fontWeight: 600, color: '#2c3e50' }}
                    >
                        Лицензия
                    </Typography>
                </Box>

                <Button
                    size="small"
                    variant="outlined"
                    startIcon={<RefreshIcon />}
                    onClick={load}
                    disabled={loading}
                >
                    Обновить
                </Button>
            </Box>

            {error && (
                <Alert
                    severity="error"
                    sx={{ mb: 2 }}
                    onClose={() => setError(null)}
                >
                    {error}
                </Alert>
            )}

            {loading && !info && (
                <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
                    <CircularProgress />
                </Box>
            )}

            {info && (
                <>
                    {/* ==========================================
                        СТАТУС-КАРТОЧКА
                    ========================================== */}
                    <Card
                        sx={{
                            mb: 2,
                            bgcolor:
                                statusColor() === 'success'
                                    ? '#e8f5e9'
                                    : statusColor() === 'warning'
                                        ? '#fff3e0'
                                        : statusColor() === 'error'
                                            ? '#ffebee'
                                            : '#f5f5f5',
                        }}
                    >
                        <CardContent>
                            <Box
                                sx={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: 2,
                                    flexWrap: 'wrap',
                                }}
                            >
                                <Box
                                    sx={{
                                        color:
                                            statusColor() === 'success'
                                                ? '#27ae60'
                                                : statusColor() === 'warning'
                                                    ? '#e67e22'
                                                    : statusColor() === 'error'
                                                        ? '#e74c3c'
                                                        : '#7f8c8d',
                                    }}
                                >
                                    {statusIcon()}
                                </Box>

                                <Box sx={{ flexGrow: 1, minWidth: 0 }}>
                                    <Typography
                                        variant="h6"
                                        sx={{ fontWeight: 600, color: '#2c3e50' }}
                                    >
                                        {statusLabel()}
                                    </Typography>
                                    <Typography
                                        variant="body2"
                                        color="text.secondary"
                                        sx={{ mt: 0.5 }}
                                    >
                                        {statusDescription()}
                                    </Typography>
                                </Box>

                                {info.tier && (
                                    <Chip
                                        label={TIER_LABELS[info.tier] || info.tier}
                                        color="primary"
                                        size="medium"
                                        sx={{ fontWeight: 600 }}
                                    />
                                )}
                            </Box>
                        </CardContent>
                    </Card>

                    {/* ==========================================
                        ИНФОРМАЦИЯ
                    ========================================== */}
                    <Grid container spacing={2} sx={{ mb: 2 }}>
                        <Grid size={{xs: 12, md: 6}}>
                            <Card sx={{ height: '100%' }}>
                                <CardContent>
                                    <Typography
                                        variant="subtitle2"
                                        sx={{ fontWeight: 600, mb: 1.5 }}
                                    >
                                        Информация о лицензии
                                    </Typography>

                                    <Table size="small">
                                        <TableBody>
                                            <TableRow>
                                                <TableCell
                                                    sx={{
                                                        fontWeight: 600,
                                                        color: '#7f8c8d',
                                                        width: '40%',
                                                    }}
                                                >
                                                    Организация
                                                </TableCell>
                                                <TableCell>
                                                    {info.holder || '—'}
                                                </TableCell>
                                            </TableRow>
                                            <TableRow>
                                                <TableCell
                                                    sx={{ fontWeight: 600, color: '#7f8c8d' }}
                                                >
                                                    Уровень (tier)
                                                </TableCell>
                                                <TableCell>
                                                    {info.tier
                                                        ? TIER_LABELS[info.tier] ||
                                                        info.tier
                                                        : '—'}
                                                </TableCell>
                                            </TableRow>
                                            <TableRow>
                                                <TableCell
                                                    sx={{ fontWeight: 600, color: '#7f8c8d' }}
                                                >
                                                    Выпущена
                                                </TableCell>
                                                <TableCell>
                                                    {formatDateTime(info.issued_at)}
                                                </TableCell>
                                            </TableRow>
                                            <TableRow>
                                                <TableCell
                                                    sx={{ fontWeight: 600, color: '#7f8c8d' }}
                                                >
                                                    Истекает
                                                </TableCell>
                                                <TableCell>
                                                    {formatDateTime(info.expires_at)}
                                                    {info.days_left !== null && (
                                                        <Typography
                                                            variant="caption"
                                                            sx={{
                                                                display: 'block',
                                                                color:
                                                                    info.days_left <= 14
                                                                        ? '#e67e22'
                                                                        : '#7f8c8d',
                                                            }}
                                                        >
                                                            Осталось: {info.days_left} дн.
                                                        </Typography>
                                                    )}
                                                </TableCell>
                                            </TableRow>
                                            {info.max_users !== null && (
                                                <TableRow>
                                                    <TableCell
                                                        sx={{
                                                            fontWeight: 600,
                                                            color: '#7f8c8d',
                                                        }}
                                                    >
                                                        Лимит пользователей
                                                    </TableCell>
                                                    <TableCell>
                                                        {info.max_users}
                                                    </TableCell>
                                                </TableRow>
                                            )}
                                            <TableRow>
                                                <TableCell
                                                    sx={{ fontWeight: 600, color: '#7f8c8d' }}
                                                >
                                                    Алгоритм
                                                </TableCell>
                                                <TableCell>
                                                    {info.algorithm}
                                                </TableCell>
                                            </TableRow>
                                        </TableBody>
                                    </Table>
                                </CardContent>
                            </Card>
                        </Grid>

                        <Grid size={{xs: 12, md: 6}}>
                            <Card sx={{ height: '100%' }}>
                                <CardContent>
                                    <Typography
                                        variant="subtitle2"
                                        sx={{ fontWeight: 600, mb: 1.5 }}
                                    >
                                        Сервер (instance ID)
                                    </Typography>

                                    <Typography
                                        variant="caption"
                                        color="text.secondary"
                                        sx={{ display: 'block', mb: 1 }}
                                    >
                                        Идентификатор используется для выпуска
                                        лицензии, привязанной к этому серверу.
                                        Скопируйте и передайте вендору.
                                    </Typography>

                                    <Box
                                        sx={{
                                            display: 'flex',
                                            gap: 1,
                                            alignItems: 'center',
                                            mb: 1.5,
                                        }}
                                    >
                                        <Box
                                            sx={{
                                                flexGrow: 1,
                                                p: 1,
                                                bgcolor: '#f5f6fa',
                                                borderRadius: 1,
                                                fontFamily: 'monospace',
                                                fontSize: '0.75rem',
                                                wordBreak: 'break-all',
                                                minHeight: 40,
                                                display: 'flex',
                                                alignItems: 'center',
                                            }}
                                        >
                                            {instance?.instance_id || '—'}
                                        </Box>
                                        <Tooltip title="Скопировать">
                                            <span>
                                                <IconButton
                                                    size="small"
                                                    onClick={handleCopyInstanceId}
                                                    disabled={!instance?.instance_id}
                                                >
                                                    <ContentCopyIcon fontSize="small" />
                                                </IconButton>
                                            </span>
                                        </Tooltip>
                                    </Box>

                                    {instance && (
                                        <Typography
                                            variant="caption"
                                            color="text.secondary"
                                        >
                                            Алгоритм: {instance.algorithm}.{' '}
                                            Компоненты:{' '}
                                            {instance.components.join(', ')}.
                                        </Typography>
                                    )}

                                    {info.instance_bound && (
                                        <Alert
                                            severity="info"
                                            icon={<CheckCircleIcon />}
                                            sx={{ mt: 1.5 }}
                                        >
                                            Лицензия привязана к этому серверу
                                        </Alert>
                                    )}
                                </CardContent>
                            </Card>
                        </Grid>
                    </Grid>

                    {/* ==========================================
                        ДОСТУПНЫЕ ФИЧИ
                    ========================================== */}
                    <Card sx={{ mb: 2 }}>
                        <CardContent>
                            <Typography
                                variant="subtitle2"
                                sx={{ fontWeight: 600, mb: 1 }}
                            >
                                Доступные функции
                            </Typography>

                            <Typography
                                variant="caption"
                                color="text.secondary"
                                sx={{ display: 'block', mb: 1.5 }}
                            >
                                Список функций, входящих в вашу лицензию
                                (tier <b>{info.tier || '—'}</b>).
                            </Typography>

                            <TableContainer>
                                <Table size="small">
                                    <TableHead>
                                        <TableRow>
                                            <TableCell sx={{ fontWeight: 600 }}>
                                                Функция
                                            </TableCell>
                                            <TableCell
                                                align="center"
                                                sx={{ fontWeight: 600 }}
                                            >
                                                Включена
                                            </TableCell>
                                        </TableRow>
                                    </TableHead>
                                    <TableBody>
                                        {ALL_FEATURES.map((f) => {
                                            const enabled = info.hasOwnProperty(
                                                'features',
                                            )
                                                ? info.features.includes(f.key)
                                                : false;
                                            return (
                                                <TableRow key={f.key}>
                                                    <TableCell>
                                                        {f.label}
                                                    </TableCell>
                                                    <TableCell align="center">
                                                        {enabled ? (
                                                            <Chip
                                                                icon={
                                                                    <CheckCircleIcon fontSize="small" />
                                                                }
                                                                label="Да"
                                                                color="success"
                                                                size="small"
                                                                variant="outlined"
                                                            />
                                                        ) : (
                                                            <Chip
                                                                label="Нет"
                                                                size="small"
                                                                variant="outlined"
                                                            />
                                                        )}
                                                    </TableCell>
                                                </TableRow>
                                            );
                                        })}
                                    </TableBody>
                                </Table>
                            </TableContainer>
                        </CardContent>
                    </Card>

                    {/* ==========================================
                        ИНСТРУКЦИЯ ПО ОБНОВЛЕНИЮ
                    ========================================== */}
                    <Card>
                        <CardContent>
                            <Typography
                                variant="subtitle2"
                                sx={{ fontWeight: 600, mb: 1 }}
                            >
                                Как обновить лицензию
                            </Typography>

                            <Typography
                                variant="body2"
                                sx={{ mb: 1.5, color: 'text.secondary' }}
                            >
                                Лицензионный ключ хранится в файле <code>.env</code>{' '}
                                в корне проекта. Он читается backend'ом при
                                старте. Чтобы обновить лицензию:
                            </Typography>

                            <Box
                                component="ol"
                                sx={{
                                    pl: 2,
                                    '& li': { mb: 0.75, fontSize: '0.875rem' },
                                }}
                            >
                                <li>
                                    Получите новый ключ <code>LICENSE_KEY</code>{' '}
                                    у вендора.
                                </li>
                                <li>
                                    Откройте файл <code>.env</code> в корне
                                    проекта.
                                </li>
                                <li>
                                    Замените значение переменной{' '}
                                    <code>LICENSE_KEY</code> на новое.
                                </li>
                                <li>
                                    Перезапустите backend:{' '}
                                    <code>
                                        docker compose -f
                                        docker-compose.prod.yml restart backend
                                    </code>
                                </li>
                                <li>
                                    Обновите эту страницу (кнопка{' '}
                                    <b>Обновить</b> вверху).
                                </li>
                            </Box>

                            <Divider sx={{ my: 1.5 }} />

                            <Typography
                                variant="caption"
                                color="text.secondary"
                                sx={{ display: 'block' }}
                            >
                                Режим проверки:{' '}
                                <b>
                                    {info.verify_enabled
                                        ? 'включён'
                                        : 'отключён'}
                                </b>{' '}
                                (LICENSE_VERIFY). Ключ:{' '}
                                <b>
                                    {info.key_provided
                                        ? 'задан'
                                        : 'не задан'}
                                </b>{' '}
                                (LICENSE_KEY).
                            </Typography>
                        </CardContent>
                    </Card>
                </>
            )}

            {/* Снекбар «скопировано» */}
            <Snackbar
                open={copied}
                autoHideDuration={2000}
                onClose={() => setCopied(false)}
                message="Instance ID скопирован в буфер обмена"
                anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
            />
        </Box>
    );
};

export default LicensePage;