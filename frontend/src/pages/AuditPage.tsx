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
    Collapse,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    FormControl,
    IconButton,
    InputLabel,
    MenuItem,
    OutlinedInput,
    Select,
    TextField,
    Tooltip,
    Typography,
} from '@mui/material';
import {
    BookmarkAdd as BookmarkAddIcon,
    Delete as DeleteIcon,
    Download as DownloadIcon,
    ExpandLess as ExpandLessIcon,
    ExpandMore as ExpandMoreIcon,
    History as HistoryIcon,
    Info as InfoIcon,
    Refresh as RefreshIcon,
    Search as SearchIcon,
    Star as StarIcon,
    StarBorder as StarBorderIcon,
    Warning as WarningIcon,
} from '@mui/icons-material';
import {
    Bar,
    BarChart,
    CartesianGrid,
    Line,
    LineChart,
    ResponsiveContainer,
    Tooltip as RechartsTooltip,
    XAxis,
    YAxis,
} from 'recharts';
import {auditApi} from '../services/api';
import type {
    AuditEvent,
    AuditFilterSpec,
    AuditGroupBy,
    AuditListResponse,
    AuditSavedView,
    AuditSeverity,
    AuditSource,
    AuditSourceInfo,
    AuditStatsResponse,
    AuditStatsSeriesResponse,
} from '../types';

// ==========================================
// КОНСТАНТЫ
// ==========================================

const DASHBOARD_STORAGE_KEY = 'aps_audit_dashboard_open';

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

const SOURCE_CHART_COLORS: Record<AuditSource, string> = {
    STOCK: '#3498db',
    RESCHEDULE: '#9b59b6',
    LAB: '#e67e22',
    CZ: '#27ae60',
};

const SEVERITY_CHART_COLORS: Record<AuditSeverity, string> = {
    INFO: '#3498db',
    WARNING: '#f39c12',
    CRITICAL: '#e74c3c',
};

const ENTITY_TYPES = [
    { value: '', label: '— Все —' },
    { value: 'material', label: 'Материал' },
    { value: 'batch', label: 'Партия' },
    { value: 'schedule_version', label: 'Версия плана' },
];

// ==========================================
// ХЕЛПЕРЫ
// ==========================================

const _parseCsv = (s: string | null): string[] =>
    s ? s.split(',').map((x) => x.trim().toUpperCase()).filter(Boolean) : [];

const _parseInt = (
    s: string | null,
    def: number,
    min: number,
    max: number,
): number => {
    if (!s) return def;
    const n = parseInt(s, 10);
    if (isNaN(n)) return def;
    return Math.max(min, Math.min(max, n));
};

const _parseFloat = (s: string | null): number | null => {
    if (!s) return null;
    const n = parseFloat(s);
    return isNaN(n) ? null : n;
};

// ==========================================
// КОМПОНЕНТ
// ==========================================

const AuditPage: React.FC = () => {
    const [searchParams, setSearchParams] = useSearchParams();

    // ---- Начальные значения из URL ----
    const _initialSources = _parseCsv(searchParams.get('sources'));
    const _initialSeverity = (searchParams.get('severity') || '').toUpperCase();
    const _initialSearch = searchParams.get('search') || '';
    const _initialDays = _parseInt(searchParams.get('days'), 7, 1, 365);
    const _initialDateFrom = searchParams.get('date_from') || '';
    const _initialDateTo = searchParams.get('date_to') || '';
    const _initialLimit = _parseInt(searchParams.get('limit'), 200, 10, 2000);
    const _initialActorId = searchParams.get('actor_id') || '';
    const _initialEntityType = searchParams.get('entity_type') || '';
    const _initialDeltaFrom = _parseFloat(searchParams.get('delta_qty_from'));
    const _initialDeltaTo = _parseFloat(searchParams.get('delta_qty_to'));
    const _initialGroupBy = (searchParams.get('group_by') || 'day') as AuditGroupBy;

    // ---- Состояние данных ----
    const [data, setData] = useState<AuditListResponse | null>(null);
    const [stats, setStats] = useState<AuditStatsResponse | null>(null);
    const [seriesByDay, setSeriesByDay] = useState<AuditStatsSeriesResponse | null>(null);
    const [seriesBySource, setSeriesBySource] = useState<AuditStatsSeriesResponse | null>(null);
    const [seriesBySeverity, setSeriesBySeverity] = useState<AuditStatsSeriesResponse | null>(null);
    const [sources, setSources] = useState<AuditSourceInfo[]>([]);
    const [savedViews, setSavedViews] = useState<AuditSavedView[]>([]);

    const [loading, setLoading] = useState(false);
    const [exporting, setExporting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [successMsg, setSuccessMsg] = useState<string | null>(null);

    // ---- Состояние фильтров ----
    const [selectedSources, setSelectedSources] = useState<string[]>(_initialSources);
    const [filterSeverity, setFilterSeverity] = useState<string>(_initialSeverity);
    const [filterDateFrom, setFilterDateFrom] = useState<string>(_initialDateFrom);
    const [filterDateTo, setFilterDateTo] = useState<string>(_initialDateTo);
    const [search, setSearch] = useState<string>(_initialSearch);
    const [limit, setLimit] = useState<number>(_initialLimit);
    const [statsDays, setStatsDays] = useState<number>(_initialDays);
    const [filterActorId, setFilterActorId] = useState<string>(_initialActorId);
    const [filterEntityType, setFilterEntityType] = useState<string>(_initialEntityType);
    const [filterDeltaFrom, setFilterDeltaFrom] = useState<number | null>(_initialDeltaFrom);
    const [filterDeltaTo, setFilterDeltaTo] = useState<number | null>(_initialDeltaTo);
    const [groupBy, setGroupBy] = useState<AuditGroupBy>(_initialGroupBy);

    // ---- Дашборд сворачиваемый ----
    const [dashboardOpen, setDashboardOpen] = useState<boolean>(() => {
        const saved = localStorage.getItem(DASHBOARD_STORAGE_KEY);
        return saved !== 'false';
    });

    useEffect(() => {
        localStorage.setItem(DASHBOARD_STORAGE_KEY, String(dashboardOpen));
    }, [dashboardOpen]);

    // ---- Диалог сохранения ----
    const [saveDialogOpen, setSaveDialogOpen] = useState(false);
    const [saveViewName, setSaveViewName] = useState('');
    const [saveViewIsDefault, setSaveViewIsDefault] = useState(false);

    // ==========================================
    // СБОРКА ФИЛЬТРОВ В AuditFilterSpec
    // ==========================================
    const currentFilters: AuditFilterSpec = useMemo(() => ({
        sources: selectedSources.length > 0 ? (selectedSources as AuditSource[]) : undefined,
        severity: filterSeverity ? (filterSeverity as AuditSeverity) : undefined,
        date_from: filterDateFrom ? new Date(filterDateFrom).toISOString() : undefined,
        date_to: filterDateTo
            ? new Date(filterDateTo + 'T23:59:59').toISOString()
            : undefined,
        search: search.trim() || undefined,
        limit,
        actor_id: filterActorId.trim() || undefined,
        entity_type: filterEntityType || undefined,
        delta_qty_from: filterDeltaFrom,
        delta_qty_to: filterDeltaTo,
    }), [
        selectedSources, filterSeverity, filterDateFrom, filterDateTo,
        search, limit, filterActorId, filterEntityType,
        filterDeltaFrom, filterDeltaTo,
    ]);

    // ==========================================
    // ЗАГРУЗКА СПРАВОЧНИКА ИСТОЧНИКОВ
    // ==========================================
    useEffect(() => {
        (async () => {
            try {
                const res = await auditApi.getSources();
                setSources(res.sources);
            } catch {
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
    // ЗАГРУЗКА СОХРАНЁННЫХ ПРЕДСТАВЛЕНИЙ
    // ==========================================
    const loadSavedViews = useCallback(async () => {
        try {
            const res = await auditApi.listSavedViews();
            setSavedViews(res.views);
        } catch {
            setSavedViews([]);
        }
    }, []);

    useEffect(() => {
        loadSavedViews();
    }, [loadSavedViews]);

    // ==========================================
    // СИНХРОНИЗАЦИЯ ФИЛЬТРОВ С URL
    // ==========================================
    useEffect(() => {
        const params: Record<string, string> = {};
        if (selectedSources.length > 0) params.sources = selectedSources.join(',');
        if (filterSeverity) params.severity = filterSeverity;
        if (filterDateFrom) params.date_from = filterDateFrom;
        if (filterDateTo) params.date_to = filterDateTo;
        if (search.trim()) params.search = search.trim();
        if (limit !== 200) params.limit = String(limit);
        if (statsDays !== 7) params.days = String(statsDays);
        if (filterActorId.trim()) params.actor_id = filterActorId.trim();
        if (filterEntityType) params.entity_type = filterEntityType;
        if (filterDeltaFrom != null) params.delta_qty_from = String(filterDeltaFrom);
        if (filterDeltaTo != null) params.delta_qty_to = String(filterDeltaTo);
        if (groupBy !== 'day') params.group_by = groupBy;

        const currentStr = searchParams.toString();
        const newStr = new URLSearchParams(params).toString();
        if (currentStr !== newStr) {
            setSearchParams(params, { replace: true });
        }
    }, [
        selectedSources, filterSeverity, filterDateFrom, filterDateTo,
        search, limit, statsDays, filterActorId, filterEntityType,
        filterDeltaFrom, filterDeltaTo, groupBy,
        searchParams, setSearchParams,
    ]);

    // ==========================================
    // ЗАГРУЗКА ЖУРНАЛА
    // ==========================================
    const loadLog = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await auditApi.getLog({filters: currentFilters});
            setData(res);
        } catch (err: any) {
            const detail = err.response?.data?.detail;
            setError(typeof detail === 'string' ? detail : 'Ошибка загрузки аудита');
        } finally {
            setLoading(false);
        }
    }, [currentFilters]);

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

    // ==========================================
    // ЗАГРУЗКА СЕРИЙ ДЛЯ ДАШБОРДА
    // ==========================================
    const loadSeries = useCallback(async () => {
        try {
            const [byDay, bySource, bySeverity] = await Promise.all([
                auditApi.getStatsSeries('day', statsDays),
                auditApi.getStatsSeries('source', statsDays),
                auditApi.getStatsSeries('severity', statsDays),
            ]);
            setSeriesByDay(byDay);
            setSeriesBySource(bySource);
            setSeriesBySeverity(bySeverity);
        } catch {
            setSeriesByDay(null);
            setSeriesBySource(null);
            setSeriesBySeverity(null);
        }
    }, [statsDays]);

    // Автозагрузка
    useEffect(() => { loadLog(); }, [loadLog]);
    useEffect(() => { loadStats(); loadSeries(); }, [loadStats, loadSeries]);

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
        setFilterActorId('');
        setFilterEntityType('');
        setFilterDeltaFrom(null);
        setFilterDeltaTo(null);
    };

    // ==========================================
    // ЭКСПОРТ В EXCEL (16.4)
    // ==========================================
    const handleExport = async () => {
        setExporting(true);
        setError(null);
        try {
            const blob = await auditApi.exportAudit({
                filters: currentFilters,
                title: 'Журнал аудита APS Scheduler',
                max_rows: 10000,
            });

            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `audit_${new Date().toISOString().slice(0, 10)}.xlsx`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);

            setSuccessMsg('Файл выгружен');
            setTimeout(() => setSuccessMsg(null), 3000);
        } catch (err: any) {
            const detail = err.response?.data?.detail;
            setError(typeof detail === 'string' ? detail : 'Ошибка экспорта');
        } finally {
            setExporting(false);
        }
    };

    // ==========================================
    // СОХРАНЁННЫЕ ПРЕДСТАВЛЕНИЯ (16.2)
    // ==========================================
    const handleSaveView = async () => {
        if (!saveViewName.trim()) {
            setError('Введите имя представления');
            return;
        }
        setError(null);
        try {
            await auditApi.createSavedView({
                name: saveViewName.trim(),
                filters: currentFilters,
                is_default: saveViewIsDefault,
            });
            setSaveDialogOpen(false);
            setSaveViewName('');
            setSaveViewIsDefault(false);
            await loadSavedViews();
            setSuccessMsg('Представление сохранено');
            setTimeout(() => setSuccessMsg(null), 3000);
        } catch (err: any) {
            const detail = err.response?.data?.detail;
            setError(typeof detail === 'string' ? detail : 'Ошибка сохранения');
        }
    };

    const handleLoadView = (view: AuditSavedView) => {
        const f = view.filters;
        setSelectedSources(f.sources || []);
        setFilterSeverity(f.severity || '');
        setFilterDateFrom(
            f.date_from ? new Date(f.date_from).toISOString().slice(0, 10) : ''
        );
        setFilterDateTo(
            f.date_to ? new Date(f.date_to).toISOString().slice(0, 10) : ''
        );
        setSearch(f.search || '');
        setLimit(f.limit ?? 200);
        setFilterActorId(f.actor_id || '');
        setFilterEntityType(f.entity_type || '');
        setFilterDeltaFrom(f.delta_qty_from ?? null);
        setFilterDeltaTo(f.delta_qty_to ?? null);
    };

    const handleDeleteView = async (view: AuditSavedView) => {
        if (!window.confirm(`Удалить представление «${view.name}»?`)) return;
        try {
            await auditApi.deleteSavedView(view.id);
            await loadSavedViews();
        } catch {
            setError('Ошибка удаления представления');
        }
    };

    const handleToggleDefault = async (view: AuditSavedView) => {
        try {
            await auditApi.updateSavedView(view.id, {
                is_default: !view.is_default,
            });
            await loadSavedViews();
        } catch {
            setError('Ошибка обновления представления');
        }
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

    // ==========================================
    // ГРУППИРОВКА СОБЫТИЙ ПО ДАТЕ
    // ==========================================
    const groupedEvents = useMemo(() => {
        if (!data) return [];
        const groups: Record<string, AuditEvent[]> = {};
        data.events.forEach((e) => {
            const day = new Date(e.occurred_at).toISOString().slice(0, 10);
            if (!groups[day]) groups[day] = [];
            groups[day].push(e);
        });
        const sortedDays = Object.keys(groups).sort().reverse();
        return sortedDays.map((day) => ({
            day,
            events: groups[day],
        }));
    }, [data]);

    // ==========================================
    // ДАННЫЕ ДЛЯ ГРАФИКОВ (нулевые категории скрыты)
    // ==========================================
    const chartLineData = useMemo(() => {
        if (!seriesByDay) return [];
        return seriesByDay.points.map((p) => ({
            label: p.label.slice(5),
            fullLabel: p.label,
            count: p.count,
        }));
    }, [seriesByDay]);

    const chartSourceData = useMemo(() => {
        if (!seriesBySource) return [];
        return seriesBySource.points
            .filter((p) => p.count > 0)   // скрываем нулевые
            .map((p) => ({
                source: p.label,
                count: p.count,
                fill: SOURCE_CHART_COLORS[p.label as AuditSource] || '#7f8c8d',
            }));
    }, [seriesBySource]);

    const chartSeverityData = useMemo(() => {
        if (!seriesBySeverity) return [];
        return seriesBySeverity.points
            .filter((p) => p.count > 0)   // скрываем нулевые
            .map((p) => ({
                severity: SEVERITY_LABELS[p.label as AuditSeverity] || p.label,
                count: p.count,
                fill: SEVERITY_CHART_COLORS[p.label as AuditSeverity] || '#7f8c8d',
            }));
    }, [seriesBySeverity]);

    // ==========================================
    // КРАТКАЯ СВОДКА ДЛЯ СВЁРНУТОГО ДАШБОРДА
    // ==========================================
    const collapsedSummary = useMemo(() => {
        if (!stats) return '';
        const parts: string[] = [];
        for (const [src, cnt] of Object.entries(stats.by_source)) {
            if (cnt > 0) parts.push(`${src}: ${cnt}`);
        }
        for (const [sev, cnt] of Object.entries(stats.by_severity)) {
            if (cnt > 0) parts.push(`${SEVERITY_LABELS[sev as AuditSeverity]}: ${cnt}`);
        }
        return parts.join(' · ');
    }, [stats]);

    // ==========================================
    // РЕНДЕР
    // ==========================================
    return (
        <Box
            sx={{
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                minHeight: 0,
                gap: 1.5,
            }}
        >
            {/* ==========================================
                ЗАГОЛОВОК + КНОПКИ
            ========================================== */}
            <Box
                sx={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    flexWrap: 'wrap',
                    gap: 1,
                    flexShrink: 0,
                }}
            >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                    <HistoryIcon color="primary" sx={{ fontSize: 28 }} />
                    <Typography
                        variant="h5"
                        component="h1"
                        sx={{ fontWeight: 600, color: '#2c3e50' }}
                    >
                        Аудит
                    </Typography>
                    {data && (
                        <Chip
                            label={`Всего: ${data.total}`}
                            variant="outlined"
                            size="small"
                        />
                    )}
                </Box>
                <Box sx={{ display: 'flex', gap: 1 }}>
                    <Button
                        size="small"
                        variant="outlined"
                        startIcon={<DownloadIcon />}
                        onClick={handleExport}
                        disabled={exporting || loading}
                    >
                        {exporting ? 'Экспорт...' : 'Экспорт в Excel'}
                    </Button>
                    <Button
                        size="small"
                        variant="outlined"
                        startIcon={<RefreshIcon />}
                        onClick={() => { loadLog(); loadStats(); loadSeries(); }}
                        disabled={loading}
                    >
                        Обновить
                    </Button>
                </Box>
            </Box>

            {error && (
                <Alert
                    severity="error"
                    onClose={() => setError(null)}
                    sx={{ flexShrink: 0 }}
                >
                    {error}
                </Alert>
            )}
            {successMsg && (
                <Alert
                    severity="success"
                    onClose={() => setSuccessMsg(null)}
                    sx={{ flexShrink: 0 }}
                >
                    {successMsg}
                </Alert>
            )}

            {/* ==========================================
                ДАШБОРД (сворачиваемый)
            ========================================== */}
            <Card sx={{ flexShrink: 0 }}>
                <CardContent sx={{ py: 1, '&:last-child': { pb: 1 } }}>
                    <Box
                        sx={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            cursor: 'pointer',
                            minHeight: 32,
                        }}
                        onClick={() => setDashboardOpen((v) => !v)}
                    >
                        <Box
                            sx={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 1,
                                minWidth: 0,
                                overflow: 'hidden',
                            }}
                        >
                            <Typography
                                variant="subtitle2"
                                sx={{ fontWeight: 600, flexShrink: 0 }}
                            >
                                Дашборд
                            </Typography>
                            {stats && (
                                <Typography
                                    variant="caption"
                                    color="text.secondary"
                                    sx={{
                                        overflow: 'hidden',
                                        textOverflow: 'ellipsis',
                                        whiteSpace: 'nowrap',
                                    }}
                                >
                                    за {stats.period_days} дн., всего {stats.total} событий
                                    {!dashboardOpen && collapsedSummary && ` · ${collapsedSummary}`}
                                </Typography>
                            )}
                        </Box>
                        <Box
                            sx={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 0.5,
                                flexShrink: 0,
                            }}
                        >
                            <FormControl
                                size="small"
                                variant="outlined"
                                sx={{ minWidth: 100 }}
                                onClick={(e) => e.stopPropagation()}
                            >
                                <Select
                                    value={statsDays}
                                    onChange={(e) => setStatsDays(Number(e.target.value))}
                                    variant="outlined"
                                    sx={{ height: 30, fontSize: '0.85rem' }}
                                >
                                    <MenuItem value={1}>1 день</MenuItem>
                                    <MenuItem value={7}>7 дней</MenuItem>
                                    <MenuItem value={30}>30 дней</MenuItem>
                                    <MenuItem value={90}>90 дней</MenuItem>
                                </Select>
                            </FormControl>
                            <IconButton size="small">
                                {dashboardOpen ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                            </IconButton>
                        </Box>
                    </Box>

                    <Collapse in={dashboardOpen} timeout="auto" unmountOnExit>
                        <Box sx={{ mt: 1.5 }}>
                            {/* Графики (нулевые категории скрыты) */}
                            {(seriesByDay || seriesBySource || seriesBySeverity) && (
                                <Box
                                    sx={{
                                        display: 'grid',
                                        gridTemplateColumns: { xs: '1fr', md: '2fr 1fr 1fr' },
                                        gap: 1.5,
                                    }}
                                >
                                    {/* График по дням */}
                                    <Box>
                                        <Box
                                            sx={{
                                                display: 'flex',
                                                justifyContent: 'space-between',
                                                alignItems: 'center',
                                                mb: 0.5,
                                            }}
                                        >
                                            <Typography variant="caption" sx={{ fontWeight: 600 }}>
                                                События по дням
                                            </Typography>
                                            <FormControl size="small" variant="outlined" sx={{ minWidth: 130 }}>
                                                <Select
                                                    value={groupBy}
                                                    onChange={(e) => setGroupBy(e.target.value as AuditGroupBy)}
                                                    variant="outlined"
                                                    sx={{ height: 28, fontSize: '0.75rem' }}
                                                >
                                                    <MenuItem value="day">По дням</MenuItem>
                                                    <MenuItem value="source">По источникам</MenuItem>
                                                    <MenuItem value="severity">По важности</MenuItem>
                                                </Select>
                                            </FormControl>
                                        </Box>
                                        {chartLineData.length > 0 ? (
                                            <ResponsiveContainer width="100%" height={140}>
                                                <LineChart
                                                    data={chartLineData}
                                                    margin={{ top: 4, right: 4, left: -20, bottom: 0 }}
                                                >
                                                    <CartesianGrid strokeDasharray="3 3" stroke="#ecf0f1" />
                                                    <XAxis dataKey="label" fontSize={10} />
                                                    <YAxis fontSize={10} allowDecimals={false} />
                                                    <RechartsTooltip
                                                        formatter={(value: number) => [value, 'Событий']}
                                                        labelFormatter={(label: string) => `Дата: ${label}`}
                                                    />
                                                    <Line
                                                        type="monotone"
                                                        dataKey="count"
                                                        stroke="#3498db"
                                                        strokeWidth={2}
                                                        dot={{r: 2}}
                                                        activeDot={{r: 4}}
                                                    />
                                                </LineChart>
                                            </ResponsiveContainer>
                                        ) : (
                                            <Typography variant="caption" color="text.secondary">
                                                Нет данных за период
                                            </Typography>
                                        )}
                                    </Box>

                                    {/* График по источникам */}
                                    <Box>
                                        <Typography variant="caption" sx={{ fontWeight: 600 }}>
                                            По источникам
                                        </Typography>
                                        {chartSourceData.length > 0 ? (
                                            <ResponsiveContainer width="100%" height={140}>
                                                <BarChart
                                                    data={chartSourceData}
                                                    layout="vertical"
                                                    margin={{ top: 4, right: 4, left: 0, bottom: 0 }}
                                                >
                                                    <CartesianGrid strokeDasharray="3 3" stroke="#ecf0f1" />
                                                    <XAxis type="number" fontSize={10} allowDecimals={false} />
                                                    <YAxis type="category" dataKey="source" fontSize={10} width={80} />
                                                    <RechartsTooltip
                                                        formatter={(value: number) => [value, 'Событий']}
                                                    />
                                                    <Bar dataKey="count" fill="#3498db">
                                                        {chartSourceData.map((entry, idx) => (
                                                            <Bar key={idx} dataKey="count" fill={entry.fill} />
                                                        ))}
                                                    </Bar>
                                                </BarChart>
                                            </ResponsiveContainer>
                                        ) : (
                                            <Typography variant="caption" color="text.secondary">
                                                Нет данных
                                            </Typography>
                                        )}
                                    </Box>

                                    {/* График по важности */}
                                    <Box>
                                        <Typography variant="caption" sx={{ fontWeight: 600 }}>
                                            По важности
                                        </Typography>
                                        {chartSeverityData.length > 0 ? (
                                            <ResponsiveContainer width="100%" height={140}>
                                                <BarChart
                                                    data={chartSeverityData}
                                                    layout="vertical"
                                                    margin={{ top: 4, right: 4, left: 0, bottom: 0 }}
                                                >
                                                    <CartesianGrid strokeDasharray="3 3" stroke="#ecf0f1" />
                                                    <XAxis type="number" fontSize={10} allowDecimals={false} />
                                                    <YAxis type="category" dataKey="severity" fontSize={10} width={80} />
                                                    <RechartsTooltip
                                                        formatter={(value: number) => [value, 'Событий']}
                                                    />
                                                    <Bar dataKey="count" fill="#e67e22">
                                                        {chartSeverityData.map((entry, idx) => (
                                                            <Bar key={idx} dataKey="count" fill={entry.fill} />
                                                        ))}
                                                    </Bar>
                                                </BarChart>
                                            </ResponsiveContainer>
                                        ) : (
                                            <Typography variant="caption" color="text.secondary">
                                                Нет данных
                                            </Typography>
                                        )}
                                    </Box>
                                </Box>
                            )}
                        </Box>
                    </Collapse>
                </CardContent>
            </Card>

            {/* ==========================================
                СОХРАНЁННЫЕ ПРЕДСТАВЛЕНИЯ (компактные чипы)
            ========================================== */}
            {savedViews.length > 0 && (
                <Box
                    sx={{
                        display: 'flex',
                        gap: 1,
                        flexWrap: 'wrap',
                        alignItems: 'center',
                        flexShrink: 0,
                    }}
                >
                    <Typography variant="caption" sx={{ fontWeight: 600, mr: 0.5 }}>
                        Мои представления:
                    </Typography>
                    {savedViews.map((view) => (
                        <Chip
                            key={view.id}
                            label={view.name}
                            onClick={() => handleLoadView(view)}
                            onDelete={() => handleDeleteView(view)}
                            deleteIcon={<DeleteIcon fontSize="small" />}
                            icon={view.is_default ? <StarIcon /> : <StarBorderIcon />}
                            variant={view.is_default ? 'filled' : 'outlined'}
                            color={view.is_default ? 'warning' : 'default'}
                            size="small"
                            onDoubleClick={() => handleToggleDefault(view)}
                        />
                    ))}
                </Box>
            )}

            {/* ==========================================
                ФИЛЬТРЫ (компактные, оба ряда)
            ========================================== */}
            <Card sx={{ flexShrink: 0 }}>
                <CardContent
                    sx={{
                        py: 1,
                        '&:last-child': { pb: 1 },
                        overflowX: 'auto',
                    }}
                >
                    {/* Верхний ряд */}
                    <Box
                        sx={{
                            display: 'flex',
                            gap: 1,
                            flexWrap: 'wrap',
                            alignItems: 'center',
                        }}
                    >
                        <FormControl size="small" variant="outlined" sx={{ minWidth: 200 }}>
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
                                    selected.length === 0 ? 'Все источники' : selected.join(', ')
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

                        <FormControl size="small" variant="outlined" sx={{ minWidth: 130 }}>
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
                            sx={{ width: 150 }}
                        />
                        <TextField
                            size="small"
                            type="date"
                            label="По дату"
                            value={filterDateTo}
                            onChange={(e) => setFilterDateTo(e.target.value)}
                            slotProps={{ inputLabel: { shrink: true } }}
                            sx={{ width: 150 }}
                        />

                        <TextField
                            size="small"
                            placeholder="Поиск..."
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                            sx={{ minWidth: 180, flexGrow: 1, maxWidth: 320 }}
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
                            sx={{ width: 90 }}
                            slotProps={{ htmlInput: { min: 10, max: 2000, step: 50 } }}
                        />

                        {/* Группа кнопок: пресеты дат + сброс */}
                        <Box
                            sx={{
                                display: 'flex',
                                gap: 0.5,
                                alignItems: 'center',
                                ml: 'auto',
                            }}
                        >
                            <Button size="small" variant="text" onClick={() => applyPreset(1)}>
                                День
                            </Button>
                            <Button size="small" variant="text" onClick={() => applyPreset(7)}>
                                Неделя
                            </Button>
                            <Button size="small" variant="text" onClick={() => applyPreset(30)}>
                                Месяц
                            </Button>
                            <Button
                                size="small"
                                variant="text"
                                color="inherit"
                                onClick={resetFilters}
                                sx={{ textTransform: 'none' }}
                            >
                                Сбросить
                            </Button>
                        </Box>
                    </Box>

                    {/* Нижний ряд: расширенные фильтры + save */}
                    <Box
                        sx={{
                            display: 'flex',
                            gap: 1,
                            flexWrap: 'wrap',
                            alignItems: 'center',
                            mt: 1,
                        }}
                    >
                        <TextField
                            size="small"
                            label="Entity type"
                            select
                            value={filterEntityType}
                            onChange={(e) => setFilterEntityType(e.target.value)}
                            sx={{ minWidth: 150 }}
                        >
                            {ENTITY_TYPES.map((opt) => (
                                <MenuItem key={opt.value} value={opt.value}>
                                    {opt.label}
                                </MenuItem>
                            ))}
                        </TextField>

                        <TextField
                            size="small"
                            label="Actor ID (UUID)"
                            value={filterActorId}
                            onChange={(e) => setFilterActorId(e.target.value)}
                            sx={{ minWidth: 220, flexGrow: 1, maxWidth: 400 }}
                            placeholder="00000000-0000-0000-0000-000000000001"
                        />

                        <TextField
                            size="small"
                            type="number"
                            label="Δ qty от"
                            value={filterDeltaFrom ?? ''}
                            onChange={(e) =>
                                setFilterDeltaFrom(e.target.value === '' ? null : Number(e.target.value))
                            }
                            sx={{ width: 110 }}
                            slotProps={{ htmlInput: { step: 0.1 } }}
                        />

                        <TextField
                            size="small"
                            type="number"
                            label="Δ qty до"
                            value={filterDeltaTo ?? ''}
                            onChange={(e) =>
                                setFilterDeltaTo(e.target.value === '' ? null : Number(e.target.value))
                            }
                            sx={{ width: 110 }}
                            slotProps={{ htmlInput: { step: 0.1 } }}
                        />

                        <Button
                            size="small"
                            variant="outlined"
                            startIcon={<BookmarkAddIcon />}
                            onClick={() => setSaveDialogOpen(true)}
                            sx={{ ml: 'auto' }}
                        >
                            Сохранить представление
                        </Button>
                    </Box>
                </CardContent>
            </Card>

            {/* ==========================================
                СПИСОК СОБЫТИЙ (растягивается, скроллится)
            ========================================== */}
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
                        '&:last-child': { pb: 0 },
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
                                            py: 0.75,
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
                                                py: 1,
                                                borderBottom: '1px solid #f0f0f0',
                                                bgcolor: getRowBg(e.severity),
                                                display: 'flex',
                                                gap: 1.5,
                                                alignItems: 'flex-start',
                                                '&:hover': { bgcolor: '#f5f7fa' },
                                            }}
                                        >
                                            <Typography
                                                variant="caption"
                                                sx={{
                                                    minWidth: 55,
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

                                            <Chip
                                                label={e.source}
                                                color={SOURCE_COLORS[e.source] || 'default'}
                                                size="small"
                                                sx={{ minWidth: 100 }}
                                            />

                                            <Chip
                                                icon={SEVERITY_ICONS[e.severity] as any}
                                                label={SEVERITY_LABELS[e.severity]}
                                                color={SEVERITY_COLORS[e.severity]}
                                                size="small"
                                                variant={
                                                    e.severity === 'CRITICAL' ? 'filled' : 'outlined'
                                                }
                                            />

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

                            <Box sx={{ p: 1.5, textAlign: 'center', bgcolor: '#fafbfc' }}>
                                <Typography variant="caption" color="text.secondary">
                                    Показано {data.events.length} из {data.total} событий
                                </Typography>
                            </Box>
                        </Box>
                    )}
                </CardContent>
            </Card>

            {/* ==========================================
                ДИАЛОГ СОХРАНЕНИЯ ПРЕДСТАВЛЕНИЯ
            ========================================== */}
            <Dialog
                open={saveDialogOpen}
                onClose={() => setSaveDialogOpen(false)}
                maxWidth="sm"
                fullWidth
            >
                <DialogTitle>Сохранить представление</DialogTitle>
                <DialogContent>
                    <TextField
                        autoFocus
                        margin="dense"
                        label="Имя представления"
                        fullWidth
                        value={saveViewName}
                        onChange={(e) => setSaveViewName(e.target.value)}
                        placeholder="напр. Критичные за неделю"
                    />
                    <Box sx={{ display: 'flex', alignItems: 'center', mt: 2 }}>
                        <input
                            type="checkbox"
                            id="save-default"
                            checked={saveViewIsDefault}
                            onChange={(e) => setSaveViewIsDefault(e.target.checked)}
                            style={{ marginRight: 8 }}
                        />
                        <label htmlFor="save-default">
                            Открывать автоматически при входе на страницу
                        </label>
                    </Box>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setSaveDialogOpen(false)}>Отмена</Button>
                    <Button onClick={handleSaveView} variant="contained">
                        Сохранить
                    </Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
};

export default AuditPage;