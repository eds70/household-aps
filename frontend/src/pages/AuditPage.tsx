// frontend/src/pages/AuditPage.tsx
import React, {useCallback, useEffect, useMemo, useState} from 'react';
import {useSearchParams} from 'react-router-dom';
import {
    Alert,
    Box,
    Button,
    Card,
    CardContent,
    Chip,
    CircularProgress,
    FormControl,
    InputLabel,
    MenuItem,
    OutlinedInput,
    Select,
    TextField,
    Tooltip,
    Typography,
} from '@mui/material';
import {
    History as HistoryIcon,
    Info as InfoIcon,
    Refresh as RefreshIcon,
    Search as SearchIcon,
    Warning as WarningIcon,
} from '@mui/icons-material';
import {auditApi} from '../services/api';
import type {
    AuditEvent,
    AuditListResponse,
    AuditSeverity,
    AuditSource,
    AuditSourceInfo,
    AuditStatsResponse,
} from '../types';

// ==========================================
// КОНСТАНТЫ
// ==========================================

const SEVERITY_LABELS: Record<AuditSeverity, string> = {
    INFO: 'Инфо',
    WARNING: 'Внимание',
    CRITICAL: 'Критично',
};

const SEVERITY_COLORS: Record<
    AuditSeverity,
    'info' | 'warning' | 'error'
> = {
    INFO: 'info',
    WARNING: 'warning',
    CRITICAL: 'error',
};

const SEVERITY_ICONS: Record<AuditSeverity, React.ReactNode> = {
    INFO: <InfoIcon fontSize="small" />,
    WARNING: <WarningIcon fontSize="small" />,
    CRITICAL: <WarningIcon fontSize="small" />,
};

const SOURCE_COLORS: Record<AuditSource, 'primary' | 'secondary' | 'warning' | 'success'> = {
    STOCK: 'primary',
    RESCHEDULE: 'secondary',
    LAB: 'warning',
    CZ: 'success',
};

// ==========================================
// КОМПОНЕНТ
// ==========================================

const AuditPage: React.FC = () => {
    // Итерация 13.3 (fix): читаем фильтры из URL-параметров.
    // Пример: /audit?sources=RESCHEDULE,LAB,CZ&days=30&search=крем
    const [searchParams, setSearchParams] = useSearchParams();

    // Начальные значения фильтров берём из URL (если есть)
    const _initialSources = (() => {
        const s = searchParams.get('sources');
        if (!s) return [] as string[];
        return s.split(',').map((x) => x.trim().toUpperCase()).filter(Boolean);
    })();
    const _initialSeverity = (searchParams.get('severity') || '').toUpperCase();
    const _initialSearch = searchParams.get('search') || '';
    const _initialDays = (() => {
        const d = searchParams.get('days');
        if (!d) return 7;
        const n = parseInt(d, 10);
        return isNaN(n) ? 7 : Math.max(1, Math.min(365, n));
    })();
    const _initialDateFrom = searchParams.get('date_from') || '';
    const _initialDateTo = searchParams.get('date_to') || '';
    const _initialLimit = (() => {
        const l = searchParams.get('limit');
        if (!l) return 200;
        const n = parseInt(l, 10);
        return isNaN(n) ? 200 : Math.max(10, Math.min(2000, n));
    })();

    const [data, setData] = useState<AuditListResponse | null>(null);
    const [stats, setStats] = useState<AuditStatsResponse | null>(null);
    const [sources, setSources] = useState<AuditSourceInfo[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Фильтры
    const [selectedSources, setSelectedSources] = useState<string[]>(_initialSources);
    const [filterSeverity, setFilterSeverity] = useState<string>(_initialSeverity);
    const [filterDateFrom, setFilterDateFrom] = useState<string>(_initialDateFrom);
    const [filterDateTo, setFilterDateTo] = useState<string>(_initialDateTo);
    const [search, setSearch] = useState<string>(_initialSearch);
    const [limit, setLimit] = useState<number>(_initialLimit);
    const [statsDays, setStatsDays] = useState<number>(_initialDays);

    // ==========================================
    // ЗАГРУЗКА СПРАВОЧНИКА ИСТОЧНИКОВ
    // ==========================================
    useEffect(() => {
        (async () => {
            try {
                const res = await auditApi.getSources();
                setSources(res.sources);
            } catch {
                // если не получилось — используем дефолт
                setSources([
                    { key: 'STOCK', label: 'Остатки', description: '' },
                    { key: 'RESCHEDULE', label: 'Перепланирования', description: '' },
                    { key: 'LAB', label: 'Лаборатория', description: '' },
                    { key: 'CZ', label: 'Честный Знак', description: '' },
                ]);
            }
        })();
    }, []);

    // ==========================================
    // Итерация 13.3 (fix): синхронизация фильтров с URL
    // ==========================================
    // При любом изменении фильтра — обновляем query-параметры в адресной строке.
    // Это позволяет:
    //   - делиться ссылкой с коллегами (сохраняются все фильтры);
    //   - переходить из Ганта по ссылке /audit?sources=...;
    //   - использовать history (назад/вперёд в браузере).
    useEffect(() => {
        const params: Record<string, string> = {};
        if (selectedSources.length > 0) {
            params.sources = selectedSources.join(',');
        }
        if (filterSeverity) {
            params.severity = filterSeverity;
        }
        if (filterDateFrom) {
            params.date_from = filterDateFrom;
        }
        if (filterDateTo) {
            params.date_to = filterDateTo;
        }
        if (search.trim()) {
            params.search = search.trim();
        }
        if (limit !== 200) {
            params.limit = String(limit);
        }
        if (statsDays !== 7) {
            params.days = String(statsDays);
        }

        // Сравниваем с текущими — чтобы не зацикливаться
        const currentStr = searchParams.toString();
        const newStr = new URLSearchParams(params).toString();
        if (currentStr !== newStr) {
            setSearchParams(params, { replace: true });
        }
    }, [
        selectedSources,
        filterSeverity,
        filterDateFrom,
        filterDateTo,
        search,
        limit,
        statsDays,
        searchParams,
        setSearchParams,
    ]);
    
    // ==========================================
    // ЗАГРУЗКА ЖУРНАЛА
    // ==========================================
    const loadLog = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await auditApi.getLog({
                sources: selectedSources.length > 0 ? selectedSources.join(',') : undefined,
                severity: filterSeverity || undefined,
                date_from: filterDateFrom ? new Date(filterDateFrom).toISOString() : undefined,
                date_to: filterDateTo
                    ? new Date(filterDateTo + 'T23:59:59').toISOString()
                    : undefined,
                search: search.trim() || undefined,
                limit,
            });
            setData(res);
        } catch (err: any) {
            const detail = err.response?.data?.detail;
            setError(typeof detail === 'string' ? detail : 'Ошибка загрузки аудита');
        } finally {
            setLoading(false);
        }
    }, [selectedSources, filterSeverity, filterDateFrom, filterDateTo, search, limit]);

    // ==========================================
    // ЗАГРУЗКА СТАТИСТИКИ
    // ==========================================
    const loadStats = useCallback(async () => {
        try {
            const res = await auditApi.getStats(statsDays);
            setStats(res);
        } catch {
            setStats(null);
        }
    }, [statsDays]);

    // Автозагрузка
    useEffect(() => {
        loadLog();
    }, [loadLog]);

    useEffect(() => {
        loadStats();
    }, [loadStats]);

    // ==========================================
    // ПРЕСЕТЫ ДАТ
    // ==========================================
    const applyPreset = (days: number) => {
        const now = new Date();
        const from = new Date(now.getTime() - days * 24 * 3600 * 1000);
        setFilterDateFrom(from.toISOString().slice(0, 10));
        setFilterDateTo(now.toISOString().slice(0, 10));
    };

    const resetFilters = () => {
        setSelectedSources([]);
        setFilterSeverity('');
        setFilterDateFrom('');
        setFilterDateTo('');
        setSearch('');
        setLimit(200);
    };

    // ==========================================
    // ЦВЕТА СТРОК ПО SEVERITY
    // ==========================================
    const getRowBg = (severity: AuditSeverity): string => {
        switch (severity) {
            case 'CRITICAL':
                return '#ffebee';
            case 'WARNING':
                return '#fff8e1';
            default:
                return 'white';
        }
    };

    // Группировка событий по дате (для визуальных разделителей)
    const groupedEvents = useMemo(() => {
        if (!data) return [];
        const groups: Record<string, AuditEvent[]> = {};
        data.events.forEach((e) => {
            const day = new Date(e.occurred_at).toISOString().slice(0, 10);
            if (!groups[day]) groups[day] = [];
            groups[day].push(e);
        });
        // Сортируем даты по убыванию
        const sortedDays = Object.keys(groups).sort().reverse();
        return sortedDays.map((day) => ({
            day,
            events: groups[day],
        }));
    }, [data]);

    // ==========================================
    // РЕНДЕР
    // ==========================================
    return (
        <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            {/* Заголовок */}
            <Box
                sx={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    mb: 2,
                    flexWrap: 'wrap',
                    gap: 2,
                }}
            >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                    <HistoryIcon color="primary" sx={{ fontSize: 32 }} />
                    <Typography variant="h4" component="h1" sx={{ fontWeight: 600, color: '#2c3e50' }}>
                        Аудит
                    </Typography>
                    {data && <Chip label={`Всего: ${data.total}`} variant="outlined" />}
                </Box>
                <Box sx={{ display: 'flex', gap: 1 }}>
                    <Button
                        variant="outlined"
                        startIcon={<RefreshIcon />}
                        onClick={() => {
                            loadLog();
                            loadStats();
                        }}
                        disabled={loading}
                    >
                        Обновить
                    </Button>
                </Box>
            </Box>

            {error && (
                <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
                    {error}
                </Alert>
            )}

            {/* Статистика */}
            {stats && (
                <Card sx={{ mb: 2, bgcolor: '#f8f9fa' }}>
                    <CardContent sx={{ py: 1.5 }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
                            <Chip
                                label={`За ${stats.period_days} дн.: ${stats.total}`}
                                color="primary"
                                variant="outlined"
                                icon={<HistoryIcon />}
                            />
                            {Object.entries(stats.by_source).map(([src, cnt]) => (
                                <Chip
                                    key={src}
                                    label={`${src}: ${cnt}`}
                                    color={SOURCE_COLORS[src as AuditSource] || 'default'}
                                    variant={cnt > 0 ? 'filled' : 'outlined'}
                                    size="small"
                                    onClick={() => setSelectedSources([src])}
                                />
                            ))}
                            <Box sx={{ mx: 1, borderLeft: '1px solid #ccc', height: 24 }} />
                            {Object.entries(stats.by_severity).map(([sev, cnt]) => (
                                <Chip
                                    key={sev}
                                    icon={SEVERITY_ICONS[sev as AuditSeverity] as any}
                                    label={`${SEVERITY_LABELS[sev as AuditSeverity]}: ${cnt}`}
                                    color={SEVERITY_COLORS[sev as AuditSeverity] || 'default'}
                                    variant={cnt > 0 ? 'filled' : 'outlined'}
                                    size="small"
                                />
                            ))}
                            <FormControl size="small" variant="outlined" sx={{ minWidth: 100, ml: 'auto' }}>
                                <InputLabel>Период</InputLabel>
                                <Select
                                    value={statsDays}
                                    label="Период"
                                    variant="outlined"
                                    onChange={(e) => setStatsDays(Number(e.target.value))}
                                >
                                    <MenuItem value={1}>1 день</MenuItem>
                                    <MenuItem value={7}>7 дней</MenuItem>
                                    <MenuItem value={30}>30 дней</MenuItem>
                                    <MenuItem value={90}>90 дней</MenuItem>
                                </Select>
                            </FormControl>
                        </Box>
                    </CardContent>
                </Card>
            )}

            {/* Фильтры */}
            <Card sx={{ mb: 2 }}>
                <CardContent sx={{ py: 1.5 }}>
                    <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}>
                        <FormControl size="small" variant="outlined" sx={{ minWidth: 260 }}>
                            <InputLabel>Источники</InputLabel>
                            <Select
                                multiple
                                value={selectedSources}
                                onChange={(e) =>
                                    setSelectedSources(
                                        typeof e.target.value === 'string'
                                            ? e.target.value.split(',')
                                            : e.target.value,
                                    )
                                }
                                input={<OutlinedInput label="Источники" />}
                                renderValue={(selected) =>
                                    selected.length === 0
                                        ? 'Все источники'
                                        : selected.join(', ')
                                }
                                variant="outlined"
                            >
                                {sources.map((s) => (
                                    <MenuItem key={s.key} value={s.key}>
                                        {s.label}
                                    </MenuItem>
                                ))}
                            </Select>
                        </FormControl>

                        <FormControl size="small" variant="outlined" sx={{ minWidth: 150 }}>
                            <InputLabel>Важность</InputLabel>
                            <Select
                                value={filterSeverity}
                                label="Важность"
                                variant="outlined"
                                onChange={(e) => setFilterSeverity(e.target.value)}
                            >
                                <MenuItem value="">— Все —</MenuItem>
                                <MenuItem value="INFO">Инфо</MenuItem>
                                <MenuItem value="WARNING">Внимание</MenuItem>
                                <MenuItem value="CRITICAL">Критично</MenuItem>
                            </Select>
                        </FormControl>

                        <TextField
                            size="small"
                            type="date"
                            label="С даты"
                            value={filterDateFrom}
                            onChange={(e) => setFilterDateFrom(e.target.value)}
                            slotProps={{ inputLabel: { shrink: true } }}
                            sx={{ width: 160 }}
                        />
                        <TextField
                            size="small"
                            type="date"
                            label="По дату"
                            value={filterDateTo}
                            onChange={(e) => setFilterDateTo(e.target.value)}
                            slotProps={{ inputLabel: { shrink: true } }}
                            sx={{ width: 160 }}
                        />

                        <TextField
                            size="small"
                            placeholder="Поиск..."
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                            sx={{ minWidth: 220 }}
                            slotProps={{
                                input: {
                                    startAdornment: (
                                        <Box sx={{ mr: 1, display: 'flex' }}>
                                            <SearchIcon fontSize="small" />
                                        </Box>
                                    ),
                                },
                            }}
                        />

                        <TextField
                            size="small"
                            type="number"
                            label="Лимит"
                            value={limit}
                            onChange={(e) => setLimit(Number(e.target.value) || 200)}
                            sx={{ width: 100 }}
                            slotProps={{ htmlInput: { min: 10, max: 2000, step: 50 } }}
                        />

                        {/* Пресеты дат */}
                        <Button size="small" variant="text" onClick={() => applyPreset(1)}>
                            День
                        </Button>
                        <Button size="small" variant="text" onClick={() => applyPreset(7)}>
                            Неделя
                        </Button>
                        <Button size="small" variant="text" onClick={() => applyPreset(30)}>
                            Месяц
                        </Button>
                        <Button size="small" variant="text" color="inherit" onClick={resetFilters}>
                            Сбросить
                        </Button>
                    </Box>
                </CardContent>
            </Card>

            {/* Список событий */}
            <Card
                sx={{
                    flexGrow: 1,
                    display: 'flex',
                    flexDirection: 'column',
                    minHeight: 0,
                    boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
                }}
            >
                <CardContent
                    sx={{
                        p: 0,
                        flexGrow: 1,
                        display: 'flex',
                        flexDirection: 'column',
                        minHeight: 0,
                    }}
                >
                    {loading && !data ? (
                        <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
                            <CircularProgress />
                        </Box>
                    ) : !data || data.events.length === 0 ? (
                        <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
                            <Typography color="text.secondary">
                                За выбранный период событий нет
                            </Typography>
                        </Box>
                    ) : (
                        <Box sx={{ flexGrow: 1, minHeight: 0, overflow: 'auto' }}>
                            {groupedEvents.map(({ day, events }) => (
                                <Box key={day}>
                                    {/* Заголовок дня */}
                                    <Box
                                        sx={{
                                            px: 2,
                                            py: 1,
                                            bgcolor: '#ecf0f1',
                                            position: 'sticky',
                                            top: 0,
                                            zIndex: 1,
                                            borderBottom: '1px solid #bdc3c7',
                                        }}
                                    >
                                        <Typography
                                            variant="subtitle2"
                                            sx={{ fontWeight: 700, color: '#2c3e50' }}
                                        >
                                            {new Date(day).toLocaleDateString('ru-RU', {
                                                weekday: 'long',
                                                day: '2-digit',
                                                month: 'long',
                                                year: 'numeric',
                                            })}
                                            <Chip
                                                label={`${events.length}`}
                                                size="small"
                                                sx={{ ml: 1 }}
                                                variant="outlined"
                                            />
                                        </Typography>
                                    </Box>

                                    {/* События дня */}
                                    {events.map((e) => (
                                        <Box
                                            key={e.id}
                                            sx={{
                                                px: 2,
                                                py: 1.25,
                                                borderBottom: '1px solid #f0f0f0',
                                                bgcolor: getRowBg(e.severity),
                                                display: 'flex',
                                                gap: 2,
                                                alignItems: 'flex-start',
                                                '&:hover': { bgcolor: '#f5f7fa' },
                                            }}
                                        >
                                            {/* Время */}
                                            <Typography
                                                variant="caption"
                                                sx={{
                                                    minWidth: 60,
                                                    fontFamily: 'monospace',
                                                    color: '#7f8c8d',
                                                    pt: 0.5,
                                                }}
                                            >
                                                {new Date(e.occurred_at).toLocaleTimeString('ru-RU', {
                                                    hour: '2-digit',
                                                    minute: '2-digit',
                                                })}
                                            </Typography>

                                            {/* Источник */}
                                            <Chip
                                                label={e.source}
                                                color={SOURCE_COLORS[e.source] || 'default'}
                                                size="small"
                                                sx={{ minWidth: 100 }}
                                            />

                                            {/* Важность */}
                                            <Chip
                                                icon={SEVERITY_ICONS[e.severity] as any}
                                                label={SEVERITY_LABELS[e.severity]}
                                                color={SEVERITY_COLORS[e.severity]}
                                                size="small"
                                                variant={
                                                    e.severity === 'CRITICAL' ? 'filled' : 'outlined'
                                                }
                                            />

                                            {/* Заголовок + описание */}
                                            <Box sx={{ flexGrow: 1, minWidth: 0 }}>
                                                <Typography
                                                    variant="body2"
                                                    sx={{ fontWeight: 600, mb: 0.25 }}
                                                >
                                                    {e.title}
                                                </Typography>
                                                {e.description && (
                                                    <Typography
                                                        variant="caption"
                                                        color="text.secondary"
                                                        sx={{
                                                            display: 'block',
                                                            overflow: 'hidden',
                                                            textOverflow: 'ellipsis',
                                                            whiteSpace: 'nowrap',
                                                            maxWidth: 700,
                                                        }}
                                                    >
                                                        {e.description}
                                                    </Typography>
                                                )}
                                                {e.entity_name && (
                                                    <Typography
                                                        variant="caption"
                                                        sx={{
                                                            display: 'block',
                                                            color: '#3498db',
                                                            mt: 0.25,
                                                        }}
                                                    >
                                                        {e.entity_type}: {e.entity_name}
                                                    </Typography>
                                                )}
                                            </Box>

                                            {/* Автор */}
                                            {e.actor_name && (
                                                <Tooltip
                                                    title={
                                                        e.actor_id
                                                            ? `ID: ${e.actor_id}`
                                                            : 'Не пользователь'
                                                    }
                                                >
                                                    <Typography
                                                        variant="caption"
                                                        sx={{
                                                            color: '#7f8c8d',
                                                            minWidth: 120,
                                                            textAlign: 'right',
                                                            pt: 0.5,
                                                        }}
                                                    >
                                                        {e.actor_name}
                                                    </Typography>
                                                </Tooltip>
                                            )}
                                        </Box>
                                    ))}
                                </Box>
                            ))}

                            {/* Итог */}
                            <Box sx={{ p: 2, textAlign: 'center', bgcolor: '#fafbfc' }}>
                                <Typography variant="caption" color="text.secondary">
                                    Показано {data.events.length} из {data.total} событий
                                </Typography>
                            </Box>
                        </Box>
                    )}
                </CardContent>
            </Card>
        </Box>
    );
};

export default AuditPage;