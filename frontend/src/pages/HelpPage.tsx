// frontend/src/pages/HelpPage.tsx
/**
 * Страница «Помощь» (Итерация 15.1 + 15.3).
 *
 * Двухпанельный layout:
 *  - Слева: дерево категорий + поиск (HelpSidebar).
 *  - Справа: markdown-статья (HelpArticleView).
 *
 * Итерация 15.3: на главной странице справки (intro-overview)
 * добавлен блок «Интерактивные туры» с карточками туров.
 *
 * Маршрут: /help/:slug
 * Если slug не указан — открывается первая статья.
 */
import React, {useCallback, useEffect, useState} from 'react';
import {useNavigate, useParams} from 'react-router-dom';
import {
    Alert,
    Box,
    Button,
    Card,
    CardActions,
    CardContent,
    Chip,
    CircularProgress,
    Divider,
    Typography,
} from '@mui/material';
import {
    Assignment as AssignmentIcon,
    CheckCircle as CheckCircleIcon,
    HelpOutlined as HelpIcon,
    PlayArrow as PlayIcon,
    Replay as ReplayIcon,
    RocketLaunch as RocketLaunchIcon,
    Timeline as TimelineIcon,
} from '@mui/icons-material';
import {Allotment} from 'allotment';
import 'allotment/dist/style.css';

import HelpSidebar from '../components/help/HelpSidebar';
import HelpArticleView from '../components/help/HelpArticleView';
import {helpApi} from '../services/api';
import {useTutorial} from '../context/TutorialContext';
import {ALL_TOURS} from '../tutorial/tours';
import type {HelpArticle} from '../types';

const DEFAULT_SLUG = 'intro-overview';

// ==========================================
// Итерация 15.3: маппинг иконок туров
// ==========================================
// Ключи соответствуют tour.icon из tours.ts.
const TOUR_ICONS: Record<string, React.ReactNode> = {
    RocketLaunch: <RocketLaunchIcon fontSize="large" />,
    Timeline: <TimelineIcon fontSize="large" />,
    Assignment: <AssignmentIcon fontSize="large" />,
};

const HelpPage: React.FC = () => {
    const {slug} = useParams<{ slug: string }>();
    const navigate = useNavigate();
    const {startTour, isTourCompleted, resetTourProgress} = useTutorial();

    const [article, setArticle] = useState<HelpArticle | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Если slug не задан — редирект на дефолтную статью
    useEffect(() => {
        if (!slug) {
            navigate(`/help/${DEFAULT_SLUG}`, {replace: true});
        }
    }, [slug, navigate]);

    // Загрузка статьи
    const loadArticle = useCallback(async (s: string) => {
        setLoading(true);
        setError(null);
        try {
            const art = await helpApi.getArticle(s);
            setArticle(art);
        } catch (err: any) {
            const detail = err.response?.data?.detail;
            setError(typeof detail === 'string' ? detail : 'Ошибка загрузки статьи');
            setArticle(null);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        if (slug) {
            loadArticle(slug);
        }
    }, [slug, loadArticle]);

    const handleSelectArticle = useCallback((newSlug: string) => {
        navigate(`/help/${newSlug}`);
    }, [navigate]);

    // ==========================================
    // Итерация 15.3: блок «Интерактивные туры»
    // ==========================================
    const renderToursBlock = () => {
        return (
            <Box sx={{ mb: 4 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                    <PlayIcon color="primary" />
                    <Typography variant="h5" sx={{ fontWeight: 600 }}>
                        Интерактивные туры
                    </Typography>
                </Box>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    Пошаговые туры по ключевым сценариям. Тур можно пропустить
                    на любом шаге — прогресс сохраняется в браузере.
                </Typography>
                <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                    {ALL_TOURS.map((tour) => {
                        const completed = isTourCompleted(tour.id);
                        return (
                            <Card
                                key={tour.id}
                                sx={{
                                    width: 320,
                                    display: 'flex',
                                    flexDirection: 'column',
                                    boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
                                    transition: 'box-shadow 0.2s',
                                    '&:hover': {
                                        boxShadow: '0 4px 16px rgba(0,0,0,0.15)',
                                    },
                                }}
                            >
                                <CardContent sx={{ flexGrow: 1 }}>
                                    <Box
                                        sx={{
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: 1.5,
                                            mb: 1.5,
                                        }}
                                    >
                                        <Box
                                            sx={{
                                                color: 'primary.main',
                                                display: 'flex',
                                                alignItems: 'center',
                                            }}
                                        >
                                            {TOUR_ICONS[tour.icon || ''] || (
                                                <PlayIcon fontSize="large" />
                                            )}
                                        </Box>
                                        <Typography
                                            variant="h6"
                                            sx={{
                                                fontWeight: 600,
                                                fontSize: '1rem',
                                            }}
                                        >
                                            {tour.name}
                                        </Typography>
                                    </Box>
                                    <Typography variant="body2" color="text.secondary">
                                        {tour.description}
                                    </Typography>
                                </CardContent>
                                <Divider />
                                <CardActions
                                    sx={{
                                        justifyContent: 'space-between',
                                        p: 1.5,
                                    }}
                                >
                                    {completed ? (
                                        <>
                                            <Chip
                                                icon={<CheckCircleIcon />}
                                                label="Пройден"
                                                color="success"
                                                size="small"
                                                variant="outlined"
                                            />
                                            <Button
                                                size="small"
                                                startIcon={<ReplayIcon />}
                                                onClick={() => {
                                                    resetTourProgress(tour.id);
                                                    startTour(tour.id);
                                                }}
                                                sx={{ textTransform: 'none' }}
                                            >
                                                Пройти заново
                                            </Button>
                                        </>
                                    ) : (
                                        <>
                                            <Box />
                                            <Button
                                                size="small"
                                                variant="contained"
                                                startIcon={<PlayIcon />}
                                                onClick={() => startTour(tour.id)}
                                                sx={{ textTransform: 'none' }}
                                            >
                                                Начать
                                            </Button>
                                        </>
                                    )}
                                </CardActions>
                            </Card>
                        );
                    })}
                </Box>
            </Box>
        );
    };

    return (
        <Box
            sx={{
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                minHeight: 0,
            }}
        >
            {/* Заголовок */}
            <Box
                sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 2,
                    mb: 2,
                    flexShrink: 0,
                }}
            >
                <HelpIcon color="primary" sx={{fontSize: 32}}/>
                <Typography
                    variant="h4"
                    component="h1"
                    sx={{fontWeight: 600, color: '#2c3e50'}}
                >
                    Помощь
                </Typography>
            </Box>

            {/* Двухпанельный layout */}
            <Box
                sx={{
                    flexGrow: 1,
                    minHeight: 0,
                    border: '1px solid #e0e0e0',
                    borderRadius: 1,
                    overflow: 'hidden',
                    bgcolor: 'white',
                }}
            >
                <Allotment
                    defaultSizes={[280, 720]}
                    minSize={240}
                >
                    <Allotment.Pane
                        minSize={240}
                        preferredSize={280}
                    >
                        <HelpSidebar
                            activeSlug={slug || null}
                            onSelectArticle={handleSelectArticle}
                        />
                    </Allotment.Pane>

                    <Allotment.Pane minSize={400}>
                        <Box
                            sx={{
                                height: '100%',
                                overflow: 'auto',
                                p: {xs: 2, md: 4},
                            }}
                        >
                            {loading && (
                                <Box
                                    sx={{
                                        display: 'flex',
                                        justifyContent: 'center',
                                        py: 6,
                                    }}
                                >
                                    <CircularProgress/>
                                </Box>
                            )}

                            {!loading && error && (
                                <Alert severity="error">
                                    {error}
                                </Alert>
                            )}

                            {!loading && !error && article && (
                                <Box sx={{maxWidth: 900, mx: 'auto'}}>
                                    {/* Итерация 15.3: блок туров
                                        на главной странице помощи */}
                                    {article.slug === DEFAULT_SLUG && (
                                        <>
                                            {renderToursBlock()}
                                            <Divider sx={{ my: 4 }} />
                                        </>
                                    )}

                                    {/* Мета статьи */}
                                    <Box
                                        sx={{
                                            display: 'flex',
                                            gap: 1,
                                            alignItems: 'center',
                                            mb: 2,
                                            color: 'text.secondary',
                                            fontSize: '0.8rem',
                                        }}
                                    >
                                        <Typography
                                            variant="caption"
                                            sx={{
                                                bgcolor: '#ecf0f1',
                                                px: 1,
                                                py: 0.25,
                                                borderRadius: 0.5,
                                                textTransform: 'uppercase',
                                                fontWeight: 600,
                                                letterSpacing: 0.5,
                                            }}
                                        >
                                            {article.category}
                                        </Typography>
                                        <Typography variant="caption">
                                            Обновлено:{' '}
                                            {new Date(
                                                article.updated_at,
                                            ).toLocaleDateString('ru-RU')}
                                        </Typography>
                                    </Box>

                                    <HelpArticleView
                                        content={article.content_md}
                                        onInternalLink={handleSelectArticle}
                                    />
                                </Box>
                            )}

                            {!loading && !error && !article && (
                                <Alert severity="info">
                                    Статья не найдена.
                                </Alert>
                            )}
                        </Box>
                    </Allotment.Pane>
                </Allotment>
            </Box>
        </Box>
    );
};

export default HelpPage;