// frontend/src/pages/CzPage.tsx
import React, {useCallback, useEffect, useState} from 'react';
import {
    Alert,
    Box,
    Button,
    Card,
    CardContent,
    Chip,
    CircularProgress,
    FormControl,
    FormControlLabel,
    IconButton,
    InputLabel,
    LinearProgress,
    MenuItem,
    Select,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    TextField,
    Tooltip,
    Typography,
} from '@mui/material';
import {
    CheckCircleOutlined as CheckCircleIcon,
    Delete as DeleteIcon,
    HelpOutlined as HelpOutlineIcon,
    LinkOff as LinkOffIcon,
    Lock as LockIcon,
    QrCodeScanner as QrCodeScannerIcon,
    Refresh as RefreshIcon,
    WarningAmber as WarningIcon,
} from '@mui/icons-material';
import {czApi} from '../services/api';
import {usePlan} from '../context/PlainContext';
import type {CzPendingBatch, CzScanLogEntry, CzStats, CzStatus} from '../types';
import DraggableDialog from '../components/common/DraggableDialog';

// ==========================================
// КОНСТАНТЫ
// ==========================================

const STATUS_LABELS: Record<CzStatus, string> = {
    NOT_APPLICABLE: 'Не требуется',
    PENDING: 'Ожидает',
    IN_PROGRESS: 'В работе',
    COMPLETED: 'Завершено',
};

const STATUS_COLORS: Record<CzStatus, 'default' | 'warning' | 'info' | 'success'> = {
    NOT_APPLICABLE: 'default',
    PENDING: 'warning',
    IN_PROGRESS: 'info',
    COMPLETED: 'success',
};

// ==========================================
// КОМПОНЕНТ
// ==========================================

const CzPage: React.FC = () => {
    const {currentVersionId, currentPlanName} = usePlan();
    const isReadOnly = currentVersionId !== null;

    const [stats, setStats] = useState<CzStats | null>(null);
    const [pending, setPending] = useState<CzPendingBatch[]>([]);
    const [log, setLog] = useState<CzScanLogEntry[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Фильтры
    const [filterStatus, setFilterStatus] = useState<string>('ALL');
    const [filterLine, setFilterLine] = useState<string>('');
    const [showUnresolvedOnly, setShowUnresolvedOnly] = useState<boolean>(false);

    // Диалог сопоставления сироты
    const [attachDialogOpen, setAttachDialogOpen] = useState(false);
    const [attachScan, setAttachScan] = useState<CzScanLogEntry | null>(null);
    const [attachBatchId, setAttachBatchId] = useState('');
    const [attachComment, setAttachComment] = useState('');
    const [attaching, setAttaching] = useState(false);

    const loadData = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const [statsData, pendingData, logData] = await Promise.all([
                czApi.getStats(),
                czApi.getPending({include_completed: filterStatus === 'COMPLETED'}),
                czApi.getLog({
                    line_code: filterLine || undefined,
                    only_unresolved: showUnresolvedOnly,
                    limit: 200,
                }),
            ]);
            setStats(statsData);
            setPending(pendingData);
            setLog(logData);
        } catch (err: any) {
            const detail = err.response?.data?.detail;
            setError(typeof detail === 'string' ? detail : 'Ошибка загрузки данных ЧЗ');
        } finally {
            setLoading(false);
        }
    }, [filterStatus, filterLine, showUnresolvedOnly]);

    useEffect(() => {
        loadData();
    }, [loadData]);

    const handleOpenAttach = (scan: CzScanLogEntry) => {
        setAttachScan(scan);
        setAttachBatchId('');
        setAttachComment('');
        setAttachDialogOpen(true);
    };

    const handleDoAttach = async () => {
        if (!attachScan || !attachBatchId) {
            setError('Укажите batch_id');
            return;
        }
        setAttaching(true);
        try {
            await czApi.attachScan(attachScan.id, {
                batch_id: attachBatchId,
                comment: attachComment || null,
            });
            setAttachDialogOpen(false);
            await loadData();
        } catch (err: any) {
            const detail = err.response?.data?.detail;
            setError(typeof detail === 'string' ? detail : 'Ошибка сопоставления');
        } finally {
            setAttaching(false);
        }
    };

    const handleDeleteScan = async (scanId: string) => {
        if (!window.confirm('Удалить скан? Это уменьшит счётчик маркировки партии.')) return;
        try {
            await czApi.deleteScan(scanId);
            await loadData();
        } catch (err: any) {
            const detail = err.response?.data?.detail;
            setError(typeof detail === 'string' ? detail : 'Ошибка удаления');
        }
    };

    if (loading && !stats) {
        return (
            <Box sx={{display: 'flex', justifyContent: 'center', mt: 8}}>
                <CircularProgress/>
            </Box>
        );
    }

    return (
        <Box
            sx={{
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                minHeight: 0,
                gap: 2,
            }}
        >
            {/* ==========================================
                Заголовок страницы (в стиле остальных страниц)
                ========================================== */}
            <Box
                sx={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    flexShrink: 0,
                    flexWrap: 'wrap',
                    gap: 2,
                }}
            >
                <Box sx={{display: 'flex', alignItems: 'center', gap: 2}}>
                    <QrCodeScannerIcon color="primary" sx={{fontSize: 28}}/>
                    <Typography variant="h5" component="h1" sx={{fontWeight: 600, color: '#2c3e50'}}>
                        Честный Знак
                    </Typography>
                    {isReadOnly && (
                        <Chip
                            icon={<LockIcon/>}
                            label={`Просмотр: ${currentPlanName}`}
                            color="info"
                            variant="filled"
                            size="small"
                        />
                    )}
                </Box>
                <Button
                    variant="outlined"
                    startIcon={<RefreshIcon/>}
                    onClick={loadData}
                    disabled={loading}
                    sx={{textTransform: 'none'}}
                >
                    Обновить
                </Button>
            </Box>

            {error && (
                <Alert severity="warning" onClose={() => setError(null)} sx={{flexShrink: 0}}>
                    {error}
                </Alert>
            )}

            {/* ==========================================
                Сводка (Card в стиле остальных страниц)
                ========================================== */}
            {stats && (
                <Card sx={{flexShrink: 0, boxShadow: '0 2px 8px rgba(0,0,0,0.08)'}}>
                    <CardContent sx={{py: 1.5, '&:last-child': {pb: 1.5}}}>
                        <Box sx={{display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap'}}>
                            <Chip
                                icon={<QrCodeScannerIcon/>}
                                label={`Всего партий: ${stats.total_batches}`}
                                color="primary"
                                variant="outlined"
                                size="small"
                            />
                            <Chip
                                icon={<WarningIcon/>}
                                label={`Ожидает: ${stats.pending}`}
                                color="warning"
                                variant={stats.pending > 0 ? 'filled' : 'outlined'}
                                size="small"
                            />
                            <Chip
                                label={`В работе: ${stats.in_progress}`}
                                color="info"
                                variant={stats.in_progress > 0 ? 'filled' : 'outlined'}
                                size="small"
                            />
                            <Chip
                                icon={<CheckCircleIcon/>}
                                label={`Завершено: ${stats.completed}`}
                                color="success"
                                variant="outlined"
                                size="small"
                            />
                            <Chip
                                label={`Сканов: ${stats.total_scans}`}
                                variant="outlined"
                                size="small"
                            />
                            {stats.unresolved_scans > 0 && (
                                <Chip
                                    icon={<LinkOffIcon/>}
                                    label={`Не сопоставлено: ${stats.unresolved_scans}`}
                                    color="error"
                                    variant="filled"
                                    size="small"
                                />
                            )}
                            <Chip
                                label={`Порог: ${(stats.threshold * 100).toFixed(0)}%`}
                                variant="outlined"
                                size="small"
                            />
                        </Box>
                    </CardContent>
                </Card>
            )}

            {/* ==========================================
                Две колонки: партии + журнал
                ========================================== */}
            <Box
                sx={{
                    display: 'flex',
                    gap: 2,
                    flexGrow: 1,
                    minHeight: 0,
                    flexDirection: {xs: 'column', lg: 'row'},
                }}
            >
                {/* ЛЕВАЯ: партии */}
                <Card
                    sx={{
                        flex: 1,
                        minWidth: 0,
                        minHeight: 0,
                        display: 'flex',
                        flexDirection: 'column',
                        boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
                    }}
                >
                    <CardContent
                        sx={{
                            p: 2,
                            flexGrow: 1,
                            display: 'flex',
                            flexDirection: 'column',
                            minHeight: 0,
                        }}
                    >
                        <Box
                            sx={{
                                display: 'flex',
                                justifyContent: 'space-between',
                                alignItems: 'center',
                                mb: 1.5,
                                flexWrap: 'wrap',
                                gap: 1,
                                flexShrink: 0,
                            }}
                        >
                            <Typography variant="h6" sx={{fontWeight: 600, fontSize: '1rem'}}>
                                Партии по маркировке
                            </Typography>
                            <FormControl size="small" variant="outlined" sx={{minWidth: 200}}>
                                <InputLabel>Показать</InputLabel>
                                <Select
                                    value={filterStatus}
                                    label="Показать"
                                    variant="outlined"
                                    onChange={(e) => setFilterStatus(e.target.value)}
                                >
                                    <MenuItem value="ALL">Ожидают + В работе</MenuItem>
                                    <MenuItem value="COMPLETED">Только завершённые</MenuItem>
                                </Select>
                            </FormControl>
                        </Box>

                        <TableContainer sx={{flexGrow: 1, minHeight: 0}}>
                            <Table size="small" stickyHeader>
                                <TableHead>
                                    <TableRow>
                                        <TableCell sx={{fontWeight: 600}}>Партия</TableCell>
                                        <TableCell sx={{fontWeight: 600}}>Продукт</TableCell>
                                        <TableCell sx={{fontWeight: 600}} align="right">Прогресс</TableCell>
                                        <TableCell sx={{fontWeight: 600}} align="center">Статус</TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {pending.length === 0 && (
                                        <TableRow>
                                            <TableCell colSpan={4} align="center">
                                                <Typography variant="body2" color="text.secondary" sx={{py: 3}}>
                                                    Нет партий по выбранному фильтру
                                                </Typography>
                                            </TableCell>
                                        </TableRow>
                                    )}
                                    {pending.map((batch) => (
                                        <TableRow key={batch.batch_id} hover>
                                            <TableCell>
                                                <Typography variant="caption" sx={{fontFamily: 'monospace'}}>
                                                    {batch.batch_id.substring(0, 8)}
                                                </Typography>
                                            </TableCell>
                                            <TableCell>
                                                <Typography variant="body2" sx={{fontWeight: 600}}>
                                                    {batch.product_code || '—'}
                                                </Typography>
                                                <Typography variant="caption" color="text.secondary">
                                                    {batch.product_name || ''}
                                                </Typography>
                                            </TableCell>
                                            <TableCell align="right" sx={{minWidth: 200}}>
                                                <Box sx={{display: 'flex', alignItems: 'center', gap: 1}}>
                                                    <Box sx={{flexGrow: 1}}>
                                                        <LinearProgress
                                                            variant="determinate"
                                                            value={Math.min(batch.progress_percent, 100)}
                                                            color={
                                                                batch.progress_percent >= 95 ? 'success' :
                                                                    batch.progress_percent > 0 ? 'info' : 'warning'
                                                            }
                                                            sx={{height: 8, borderRadius: 1}}
                                                        />
                                                    </Box>
                                                    <Typography variant="caption" sx={{minWidth: 70, textAlign: 'right'}}>
                                                        {batch.marked_qty.toFixed(0)}
                                                        {batch.planned_qty ? ` / ${batch.planned_qty.toFixed(0)}` : ''}
                                                    </Typography>
                                                </Box>
                                            </TableCell>
                                            <TableCell align="center">
                                                <Chip
                                                    label={STATUS_LABELS[batch.cz_status]}
                                                    color={STATUS_COLORS[batch.cz_status]}
                                                    size="small"
                                                />
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </TableContainer>
                    </CardContent>
                </Card>

                {/* ПРАВАЯ: журнал */}
                <Card
                    sx={{
                        flex: 1,
                        minWidth: 0,
                        minHeight: 0,
                        display: 'flex',
                        flexDirection: 'column',
                        boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
                    }}
                >
                    <CardContent
                        sx={{
                            p: 2,
                            flexGrow: 1,
                            display: 'flex',
                            flexDirection: 'column',
                            minHeight: 0,
                        }}
                    >
                        <Box
                            sx={{
                                display: 'flex',
                                justifyContent: 'space-between',
                                alignItems: 'center',
                                mb: 1.5,
                                flexWrap: 'wrap',
                                gap: 1,
                                flexShrink: 0,
                            }}
                        >
                            <Typography variant="h6" sx={{fontWeight: 600, fontSize: '1rem'}}>
                                Журнал сканирований ({log.length})
                            </Typography>
                            <Box sx={{display: 'flex', gap: 1, alignItems: 'center'}}>
                                <TextField
                                    size="small"
                                    label="Линия"
                                    value={filterLine}
                                    onChange={(e) => setFilterLine(e.target.value)}
                                    sx={{width: 120}}
                                />
                                <FormControlLabel
                                    control={
                                        <input
                                            type="checkbox"
                                            checked={showUnresolvedOnly}
                                            onChange={(e) => setShowUnresolvedOnly(e.target.checked)}
                                        />
                                    }
                                    label={<Typography variant="caption">Только сироты</Typography>}
                                />
                            </Box>
                        </Box>

                        <TableContainer sx={{flexGrow: 1, minHeight: 0}}>
                            <Table size="small" stickyHeader>
                                <TableHead>
                                    <TableRow>
                                        <TableCell sx={{fontWeight: 600}}>Время</TableCell>
                                        <TableCell sx={{fontWeight: 600}}>Код ЧЗ</TableCell>
                                        <TableCell sx={{fontWeight: 600}}>Партия</TableCell>
                                        <TableCell sx={{fontWeight: 600}}>Линия</TableCell>
                                        <TableCell sx={{fontWeight: 600}} align="center">Действия</TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {log.length === 0 && (
                                        <TableRow>
                                            <TableCell colSpan={5} align="center">
                                                <Typography variant="body2" color="text.secondary" sx={{py: 3}}>
                                                    Сканов пока нет
                                                </Typography>
                                            </TableCell>
                                        </TableRow>
                                    )}
                                    {log.map((scan) => (
                                        <TableRow key={scan.id} hover>
                                            <TableCell>
                                                <Typography variant="caption">
                                                    {new Date(scan.scanned_at).toLocaleString('ru-RU', {
                                                        day: '2-digit',
                                                        month: '2-digit',
                                                        hour: '2-digit',
                                                        minute: '2-digit',
                                                    })}
                                                </Typography>
                                            </TableCell>
                                            <TableCell>
                                                <Tooltip title={scan.cz_code}>
                                                    <Typography variant="caption" sx={{fontFamily: 'monospace'}}>
                                                        {scan.cz_code.substring(0, 24)}...
                                                    </Typography>
                                                </Tooltip>
                                            </TableCell>
                                            <TableCell>
                                                {scan.batch_id ? (
                                                    <Typography variant="caption" sx={{fontFamily: 'monospace'}}>
                                                        {scan.batch_id.substring(0, 8)}
                                                    </Typography>
                                                ) : (
                                                    <Chip
                                                        icon={<LinkOffIcon/>}
                                                        label="Сирота"
                                                        size="small"
                                                        color="error"
                                                        variant="outlined"
                                                    />
                                                )}
                                            </TableCell>
                                            <TableCell>
                                                <Typography variant="caption">
                                                    {scan.line_code || '—'}
                                                </Typography>
                                            </TableCell>
                                            <TableCell align="center">
                                                {!scan.batch_id && !isReadOnly && (
                                                    <Tooltip title="Сопоставить с партией">
                                                        <IconButton
                                                            size="small"
                                                            color="primary"
                                                            onClick={() => handleOpenAttach(scan)}
                                                        >
                                                            <HelpOutlineIcon fontSize="small"/>
                                                        </IconButton>
                                                    </Tooltip>
                                                )}
                                                {!isReadOnly && (
                                                    <Tooltip title="Удалить скан (ADMIN)">
                                                        <IconButton
                                                            size="small"
                                                            color="error"
                                                            onClick={() => handleDeleteScan(scan.id)}
                                                        >
                                                            <DeleteIcon fontSize="small"/>
                                                        </IconButton>
                                                    </Tooltip>
                                                )}
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </TableContainer>
                    </CardContent>
                </Card>
            </Box>

            {/* ==========================================
                Подсказка внизу (в стиле Card)
                ========================================== */}
            <Card
                sx={{
                    flexShrink: 0,
                    boxShadow: 'none',
                    bgcolor: '#f8f9fa',
                    border: '1px solid #e0e0e0',
                }}
            >
                <CardContent sx={{py: 1, '&:last-child': {pb: 1}}}>
                    <Typography variant="caption" color="text.secondary" sx={{display: 'block', textAlign: 'center'}}>
                        💡 Сканы приходят автоматически от камер ЧЗ. «Сироты» — сканы без сопоставления; их можно привязать вручную.
                    </Typography>
                </CardContent>
            </Card>

            {/* ==========================================
                Диалог сопоставления сироты
                ========================================== */}
            <DraggableDialog
                open={attachDialogOpen}
                onClose={() => setAttachDialogOpen(false)}
                title="Сопоставить скан с партией"
                initialWidth={600}
                initialHeight="auto"
                minWidth={480}
                minHeight={320}
                actions={
                    <>
                        <Button onClick={() => setAttachDialogOpen(false)}>Отмена</Button>
                        <Button
                            onClick={handleDoAttach}
                            variant="contained"
                            disabled={attaching || !attachBatchId.trim()}
                        >
                            {attaching ? 'Сопоставление...' : 'Сопоставить'}
                        </Button>
                    </>
                }
            >
                {attachScan && (
                    <Box sx={{display: 'flex', flexDirection: 'column', gap: 2}}>
                        <Alert severity="info">
                            <Typography variant="body2">
                                <b>Код ЧЗ:</b> {attachScan.cz_code.substring(0, 40)}...<br/>
                                <b>Время:</b> {new Date(attachScan.scanned_at).toLocaleString('ru-RU')}<br/>
                                <b>Линия:</b> {attachScan.line_code || '—'}
                            </Typography>
                        </Alert>

                        <TextField
                            label="Batch ID (UUID партии)"
                            fullWidth
                            required
                            value={attachBatchId}
                            onChange={(e) => setAttachBatchId(e.target.value)}
                            placeholder="00000000-0000-0000-0000-000000000000"
                            helperText="Скопируйте UUID партии из карточки партии или журнала"
                        />

                        <TextField
                            label="Комментарий (опционально)"
                            fullWidth
                            multiline
                            rows={2}
                            value={attachComment}
                            onChange={(e) => setAttachComment(e.target.value)}
                        />
                    </Box>
                )}
            </DraggableDialog>
        </Box>
    );
};

export default CzPage;