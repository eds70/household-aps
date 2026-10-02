// frontend/src/components/help/HelpSidebar.tsx
/**
 * Левая панель страницы «Помощь» (Итерация 15.1).
 *
 * Содержит:
 *  - Поле поиска (с debounce).
 *  - Список категорий (аккордеоны).
 *  - Список статей внутри категории.
 *  - При активном поиске — список найденных статей вместо категорий.
 */
import React, {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {
    Accordion,
    AccordionDetails,
    AccordionSummary,
    Box,
    Chip,
    CircularProgress,
    Divider,
    List,
    ListItemButton,
    ListItemText,
    TextField,
    Typography,
} from '@mui/material';
import {ExpandMore as ExpandMoreIcon, Search as SearchIcon,} from '@mui/icons-material';
import {helpApi} from '../../services/api';
import type {HelpArticleListItem, HelpCategory, HelpSearchHit} from '../../types';

interface HelpSidebarProps {
    /** Активный slug (для подсветки выбранной статьи). */
    activeSlug: string | null;
    /** Клик по статье. */
    onSelectArticle: (slug: string) => void;
}

const SEARCH_DEBOUNCE_MS = 300;

const HelpSidebar: React.FC<HelpSidebarProps> = ({
                                                     activeSlug,
                                                     onSelectArticle,
                                                 }) => {
    const [categories, setCategories] = useState<HelpCategory[]>([]);
    const [articles, setArticles] = useState<HelpArticleListItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const [searchQuery, setSearchQuery] = useState('');
    const [searchHits, setSearchHits] = useState<HelpSearchHit[] | null>(null);
    const [searching, setSearching] = useState(false);
    const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    // Загрузка категорий и статей
    const loadData = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const [cats, arts] = await Promise.all([
                helpApi.listCategories(),
                helpApi.listArticles(),
            ]);
            setCategories(cats.categories);
            setArticles(arts.articles);
        } catch (err: any) {
            const detail = err.response?.data?.detail;
            setError(typeof detail === 'string' ? detail : 'Ошибка загрузки справки');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        loadData();
    }, [loadData]);

    // Debounced поиск
    useEffect(() => {
        if (searchTimerRef.current) {
            clearTimeout(searchTimerRef.current);
        }

        const trimmed = searchQuery.trim();
        if (trimmed.length < 2) {
            setSearchHits(null);
            setSearching(false);
            return;
        }

        setSearching(true);
        searchTimerRef.current = setTimeout(async () => {
            try {
                const res = await helpApi.search(trimmed);
                setSearchHits(res.hits);
            } catch {
                setSearchHits([]);
            } finally {
                setSearching(false);
            }
        }, SEARCH_DEBOUNCE_MS);

        return () => {
            if (searchTimerRef.current) {
                clearTimeout(searchTimerRef.current);
            }
        };
    }, [searchQuery]);

    // Группировка статей по категориям
    const articlesByCategory = useMemo(() => {
        const map: Record<string, HelpArticleListItem[]> = {};
        for (const a of articles) {
            if (!map[a.category]) map[a.category] = [];
            map[a.category].push(a);
        }
        for (const cat of Object.keys(map)) {
            map[cat].sort((a, b) => a.display_order - b.display_order);
        }
        return map;
    }, [articles]);

    // Какие категории раскрыты — по умолчанию первая с активной статьёй
    const defaultExpanded = useMemo(() => {
        if (!activeSlug) return categories[0]?.key ?? false;
        const active = articles.find((a) => a.slug === activeSlug);
        return active?.category ?? categories[0]?.key ?? false;
    }, [activeSlug, articles, categories]);

    const isSearchActive = searchHits !== null;

    return (
        <Box
            sx={{
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                minHeight: 0,
                bgcolor: '#fafbfc',
            }}
        >
            {/* Поиск */}
            <Box sx={{p: 1.5, flexShrink: 0}}>
                <TextField
                    size="small"
                    placeholder="Поиск по справке..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    fullWidth
                    slotProps={{
                        input: {
                            startAdornment: (
                                <Box sx={{mr: 1, display: 'flex'}}>
                                    <SearchIcon fontSize="small"/>
                                </Box>
                            ),
                            endAdornment: searching ? (
                                <CircularProgress size={16}/>
                            ) : undefined,
                        },
                    }}
                />
            </Box>

            <Divider/>

            {/* Список */}
            <Box sx={{flexGrow: 1, overflow: 'auto', minHeight: 0}}>
                {loading && (
                    <Box sx={{display: 'flex', justifyContent: 'center', py: 4}}>
                        <CircularProgress size={28}/>
                    </Box>
                )}

                {!loading && error && (
                    <Box sx={{p: 2}}>
                        <Typography color="error" variant="body2">
                            {error}
                        </Typography>
                    </Box>
                )}

                {!loading && !error && isSearchActive && (
                    <SearchResults
                        hits={searchHits ?? []}
                        activeSlug={activeSlug}
                        onSelectArticle={onSelectArticle}
                    />
                )}

                {!loading && !error && !isSearchActive && (
                    <CategoryList
                        categories={categories}
                        articlesByCategory={articlesByCategory}
                        activeSlug={activeSlug}
                        defaultExpanded={defaultExpanded}
                        onSelectArticle={onSelectArticle}
                    />
                )}
            </Box>
        </Box>
    );
};

// ==========================================
// Категории
// ==========================================

interface CategoryListProps {
    categories: HelpCategory[];
    articlesByCategory: Record<string, HelpArticleListItem[]>;
    activeSlug: string | null;
    defaultExpanded: string | false;
    onSelectArticle: (slug: string) => void;
}

const CategoryList: React.FC<CategoryListProps> = ({
                                                       categories,
                                                       articlesByCategory,
                                                       activeSlug,
                                                       defaultExpanded,
                                                       onSelectArticle,
                                                   }) => {
    return (
        <Box sx={{py: 0.5}}>
            {categories.map((cat) => (
                <Accordion
                    key={cat.key}
                    defaultExpanded={cat.key === defaultExpanded}
                    disableGutters
                    elevation={0}
                    sx={{
                        bgcolor: 'transparent',
                        '&:before': {display: 'none'},
                    }}
                >
                    <AccordionSummary
                        expandIcon={<ExpandMoreIcon fontSize="small"/>}
                        sx={{
                            minHeight: 36,
                            '& .MuiAccordionSummary-content': {my: 0.5},
                        }}
                    >
                        <Box sx={{display: 'flex', alignItems: 'center', gap: 0.5, width: '100%'}}>
                            <Typography variant="body2" sx={{fontWeight: 600}}>
                                {cat.label}
                            </Typography>
                            <Chip
                                label={cat.article_count}
                                size="small"
                                variant="outlined"
                                sx={{height: 18, fontSize: '0.65rem'}}
                            />
                        </Box>
                    </AccordionSummary>
                    <AccordionDetails sx={{p: 0}}>
                        <List dense disablePadding>
                            {(articlesByCategory[cat.key] || []).map((a) => (
                                <ListItemButton
                                    key={a.slug}
                                    selected={activeSlug === a.slug}
                                    onClick={() => onSelectArticle(a.slug)}
                                    sx={{
                                        pl: 3,
                                        minHeight: 32,
                                        '&.Mui-selected': {
                                            bgcolor: '#e3f2fd',
                                            color: '#1976d2',
                                            '&:hover': {bgcolor: '#bbdefb'},
                                        },
                                    }}
                                >
                                    <ListItemText
                                        primary={a.title}
                                        slotProps={{
                                            primary: {sx: {fontSize: '0.85rem'}},
                                        }}
                                    />
                                </ListItemButton>
                            ))}
                        </List>
                    </AccordionDetails>
                </Accordion>
            ))}
        </Box>
    );
};

// ==========================================
// Результаты поиска
// ==========================================

interface SearchResultsProps {
    hits: HelpSearchHit[];
    activeSlug: string | null;
    onSelectArticle: (slug: string) => void;
}

const SearchResults: React.FC<SearchResultsProps> = ({
                                                         hits,
                                                         activeSlug,
                                                         onSelectArticle,
                                                     }) => {
    if (hits.length === 0) {
        return (
            <Box sx={{p: 2}}>
                <Typography color="text.secondary" variant="body2">
                    Ничего не найдено
                </Typography>
            </Box>
        );
    }

    return (
        <List dense disablePadding sx={{py: 0.5}}>
            {hits.map((h) => (
                <ListItemButton
                    key={h.slug}
                    selected={activeSlug === h.slug}
                    onClick={() => onSelectArticle(h.slug)}
                    sx={{
                        py: 1,
                        alignItems: 'flex-start',
                        '&.Mui-selected': {
                            bgcolor: '#e3f2fd',
                            '&:hover': {bgcolor: '#bbdefb'},
                        },
                    }}
                >
                    <ListItemText
                        primary={h.title}
                        secondary={h.snippet}
                        slotProps={{
                            primary: {
                                sx: {fontSize: '0.85rem', fontWeight: 600},
                            },
                            secondary: {
                                sx: {
                                    fontSize: '0.72rem',
                                    color: 'text.secondary',
                                    display: '-webkit-box',
                                    WebkitLineClamp: 2,
                                    WebkitBoxOrient: 'vertical',
                                    overflow: 'hidden',
                                },
                            },
                        }}
                    />
                </ListItemButton>
            ))}
        </List>
    );
};

export default HelpSidebar;