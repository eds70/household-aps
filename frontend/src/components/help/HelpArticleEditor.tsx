// frontend/src/components/help/HelpArticleEditor.tsx
/**
 * Форма создания/редактирования статьи справки (Итерация 15.5).
 *
 * Две вкладки:
 *  - «Редактор» — поля формы + textarea для markdown.
 *  - «Предпросмотр» — рендер markdown через HelpArticleView.
 *
 * Используется в HelpPage.tsx.
 */
import React, {useEffect, useMemo, useState} from 'react';
import {
    Alert,
    Box,
    Button,
    Chip,
    Divider,
    FormControl,
    FormControlLabel,
    InputLabel,
    MenuItem,
    Select,
    Stack,
    Switch,
    Tab,
    Tabs,
    TextField,
    Typography,
} from '@mui/material';
import {
    Delete as DeleteIcon,
    Edit as EditIcon,
    Save as SaveIcon,
    Visibility as VisibilityIcon,
} from '@mui/icons-material';

import DraggableDialog from '../common/DraggableDialog';
import HelpArticleView from './HelpArticleView';
import type {HelpArticle, HelpArticleCreate, HelpArticleUpdate, HelpCategory,} from '../../types';

// ==========================================
// Props
// ==========================================

export type HelpEditorMode = 'create' | 'edit';

export interface HelpArticleEditorProps {
    /** Открыт ли диалог. */
    open: boolean;
    /** Режим: создание или редактирование. */
    mode: HelpEditorMode;
    /** Существующая статья (только для mode='edit'). */
    article?: HelpArticle | null;
    /** Список категорий (для селекта). */
    categories: HelpCategory[];
    /** Коллбэк сохранения. Должен вернуть Promise. */
    onSave: (payload: HelpArticleCreate | HelpArticleUpdate) => Promise<void>;
    /** Коллбэк удаления (только для mode='edit'). */
    onDelete?: () => Promise<void>;
    /** Коллбэк закрытия. */
    onClose: () => void;
    /** Внешняя ошибка (если сохранение упало). */
    error?: string | null;
}

// ==========================================
// Компонент
// ==========================================

const HelpArticleEditor: React.FC<HelpArticleEditorProps> = ({
                                                                 open,
                                                                 mode,
                                                                 article,
                                                                 categories,
                                                                 onSave,
                                                                 onDelete,
                                                                 onClose,
                                                                 error,
                                                             }) => {
    const isEdit = mode === 'edit';

    // ---- Поля формы ----
    const [title, setTitle] = useState('');
    const [slug, setSlug] = useState('');
    const [category, setCategory] = useState('');
    const [contentMd, setContentMd] = useState('');
    const [tagsInput, setTagsInput] = useState('');
    const [isPublished, setIsPublished] = useState(true);
    const [displayOrder, setDisplayOrder] = useState<number | ''>('');

    // ---- UI ----
    const [activeTab, setActiveTab] = useState<'editor' | 'preview'>('editor');
    const [saving, setSaving] = useState(false);
    const [localError, setLocalError] = useState<string | null>(null);

    // ==========================================
    // Инициализация формы при открытии
    // ==========================================
    useEffect(() => {
        if (!open) return;

        setActiveTab('editor');
        setLocalError(null);
        setSaving(false);

        if (isEdit && article) {
            setTitle(article.title || '');
            setSlug(article.slug || '');
            setCategory(article.category || '');
            setContentMd(article.content_md || '');
            setTagsInput((article.tags || []).join(', '));
            setIsPublished(article.display_order >= 0); // не используется, но оставим логику
            setDisplayOrder(article.display_order ?? '');
        } else {
            // create
            setTitle('');
            setSlug('');
            setCategory(categories[0]?.key || '');
            setContentMd('');
            setTagsInput('');
            setIsPublished(true);
            setDisplayOrder('');
        }
    }, [open, isEdit, article, categories]);

    // ==========================================
    // Парсинг тегов
    // ==========================================
    const parsedTags = useMemo<string[]>(() => {
        return tagsInput
            .split(',')
            .map((t) => t.trim())
            .filter((t) => t.length > 0);
    }, [tagsInput]);

    // ==========================================
    // Валидация
    // ==========================================
    const validationError = useMemo<string | null>(() => {
        if (!title.trim()) return 'Введите заголовок';
        if (title.trim().length < 3) return 'Заголовок — минимум 3 символа';
        if (!category) return 'Выберите категорию';
        if (!contentMd.trim()) return 'Введите содержимое статьи';
        return null;
    }, [title, category, contentMd]);

    const canSave = !validationError && !saving;

    // ==========================================
    // Сохранение
    // ==========================================
    const handleSave = async () => {
        if (validationError) {
            setLocalError(validationError);
            return;
        }
        setSaving(true);
        setLocalError(null);
        try {
            const payload: HelpArticleCreate | HelpArticleUpdate = isEdit
                ? {
                    title: title.trim(),
                    slug: slug.trim() || undefined,
                    category,
                    content_md: contentMd,
                    tags: parsedTags,
                    display_order:
                        typeof displayOrder === 'number' ? displayOrder : undefined,
                    is_published: isPublished,
                }
                : {
                    title: title.trim(),
                    slug: slug.trim() || undefined,
                    category,
                    content_md: contentMd,
                    tags: parsedTags,
                    display_order:
                        typeof displayOrder === 'number' ? displayOrder : undefined,
                    is_published: isPublished,
                };

            await onSave(payload);
        } catch (err: any) {
            const detail = err?.response?.data?.detail;
            setLocalError(
                typeof detail === 'string' ? detail : 'Ошибка сохранения',
            );
        } finally {
            setSaving(false);
        }
    };

    // ==========================================
    // Удаление
    // ==========================================
    const handleDelete = async () => {
        if (!onDelete) return;
        if (!window.confirm(
            'Удалить статью? Действие необратимо.\n\n' +
            'Если нужно просто скрыть — используйте переключатель «Опубликовано».',
        )) {
            return;
        }
        setSaving(true);
        setLocalError(null);
        try {
            await onDelete();
        } catch (err: any) {
            const detail = err?.response?.data?.detail;
            setLocalError(
                typeof detail === 'string' ? detail : 'Ошибка удаления',
            );
        } finally {
            setSaving(false);
        }
    };

    // ==========================================
    // Действия диалога
    // ==========================================
    const dialogActions = (
        <Box
            sx={{
                display: 'flex',
                justifyContent: 'space-between',
                width: '100%',
                alignItems: 'center',
                gap: 1,
            }}
        >
            <Box>
                {isEdit && onDelete && (
                    <Button
                        onClick={handleDelete}
                        color="error"
                        startIcon={<DeleteIcon />}
                        disabled={saving}
                        sx={{ textTransform: 'none' }}
                    >
                        Удалить
                    </Button>
                )}
            </Box>
            <Box sx={{ display: 'flex', gap: 1 }}>
                <Button
                    onClick={onClose}
                    disabled={saving}
                    sx={{ textTransform: 'none' }}
                >
                    Отмена
                </Button>
                <Button
                    onClick={handleSave}
                    variant="contained"
                    startIcon={<SaveIcon />}
                    disabled={!canSave}
                    sx={{ textTransform: 'none' }}
                >
                    {saving ? 'Сохранение...' : 'Сохранить'}
                </Button>
            </Box>
        </Box>
    );

    // ==========================================
    // Рендер
    // ==========================================
    return (
        <DraggableDialog
            open={open}
            onClose={onClose}
            draggable
            resizable
            closeOnBackdropClick={false}
            showCloseButton
            initialWidth={1000}
            initialHeight={720}
            minWidth={640}
            minHeight={480}
            title={
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                    {isEdit ? <EditIcon color="primary" /> : <SaveIcon color="primary" />}
                    <Box sx={{ flexGrow: 1, minWidth: 0 }}>
                        <Typography variant="h6" component="div" sx={{ fontWeight: 600 }}>
                            {isEdit ? 'Редактирование статьи' : 'Новая статья справки'}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                            {isEdit
                                ? `slug: ${article?.slug || '—'}`
                                : 'Slug генерируется автоматически, если не задан'}
                        </Typography>
                    </Box>
                </Box>
            }
            actions={dialogActions}
        >
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, minHeight: 0 }}>
                {(localError || error) && (
                    <Alert severity="error" onClose={() => setLocalError(null)}>
                        {localError || error}
                    </Alert>
                )}

                {/* ==========================================
                    Вкладки
                ========================================== */}
                <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
                    <Tabs
                        value={activeTab}
                        onChange={(_, v) => setActiveTab(v)}
                        sx={{ minHeight: 36 }}
                    >
                        <Tab
                            value="editor"
                            icon={<EditIcon fontSize="small" />}
                            iconPosition="start"
                            label="Редактор"
                            sx={{ minHeight: 36, textTransform: 'none' }}
                        />
                        <Tab
                            value="preview"
                            icon={<VisibilityIcon fontSize="small" />}
                            iconPosition="start"
                            label="Предпросмотр"
                            sx={{ minHeight: 36, textTransform: 'none' }}
                        />
                    </Tabs>
                </Box>

                {/* ==========================================
                    Мета-поля (общие для обеих вкладок)
                ========================================== */}
                <Stack spacing={2}>
                    <TextField
                        label="Заголовок"
                        fullWidth
                        required
                        size="small"
                        value={title}
                        onChange={(e) => setTitle(e.target.value)}
                        error={!title.trim() && !!localError}
                        helperText="От 3 до 200 символов"
                    />

                    <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                        <TextField
                            label="Slug (опционально)"
                            fullWidth
                            size="small"
                            value={slug}
                            onChange={(e) => setSlug(e.target.value)}
                            sx={{ flex: '1 1 260px' }}
                            helperText={
                                isEdit
                                    ? 'Изменение slug сломает ссылки — используйте осторожно'
                                    : 'Оставьте пустым — сгенерируется из заголовка'
                            }
                            disabled={isEdit}
                        />

                        <FormControl
                            size="small"
                            required
                            sx={{ flex: '0 0 220px' }}
                        >
                            <InputLabel>Категория</InputLabel>
                            <Select
                                value={category}
                                label="Категория"
                                onChange={(e) => setCategory(e.target.value)}
                            >
                                {categories.map((c) => (
                                    <MenuItem key={c.key} value={c.key}>
                                        {c.label}
                                    </MenuItem>
                                ))}
                            </Select>
                        </FormControl>

                        <TextField
                            label="Порядок"
                            type="number"
                            size="small"
                            value={displayOrder}
                            onChange={(e) => {
                                const raw = e.target.value;
                                setDisplayOrder(raw === '' ? '' : Number(raw));
                            }}
                            sx={{ flex: '0 0 120px' }}
                            helperText="Меньше — выше"
                        />
                    </Box>

                    <TextField
                        label="Теги (через запятую)"
                        fullWidth
                        size="small"
                        value={tagsInput}
                        onChange={(e) => setTagsInput(e.target.value)}
                        helperText="Например: гант, drag, задача"
                    />

                    {parsedTags.length > 0 && (
                        <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                            {parsedTags.map((t) => (
                                <Chip key={t} label={t} size="small" variant="outlined" />
                            ))}
                        </Box>
                    )}

                    <FormControlLabel
                        control={
                            <Switch
                                checked={isPublished}
                                onChange={(e) => setIsPublished(e.target.checked)}
                            />
                        }
                        label={
                            <Typography variant="body2">
                                Опубликовано (видна в списке и поиске)
                            </Typography>
                        }
                    />
                </Stack>

                <Divider />

                {/* ==========================================
                    Содержимое: редактор / предпросмотр
                ========================================== */}
                <Box sx={{ flexGrow: 1, minHeight: 0 }}>
                    {activeTab === 'editor' ? (
                        <TextField
                            label="Markdown-содержимое"
                            fullWidth
                            multiline
                            minRows={16}
                            maxRows={28}
                            value={contentMd}
                            onChange={(e) => setContentMd(e.target.value)}
                            required
                            error={!contentMd.trim() && !!localError}
                            helperText="Поддерживается GFM: таблицы, чек-боксы, код"
                            slotProps={{
                                input: {
                                    style: {
                                        fontFamily: 'monospace',
                                        fontSize: '0.85rem',
                                        lineHeight: 1.5,
                                    },
                                },
                            }}
                        />
                    ) : (
                        <Box
                            sx={{
                                border: '1px solid #e0e0e0',
                                borderRadius: 1,
                                p: 2,
                                maxHeight: 520,
                                overflow: 'auto',
                                bgcolor: '#fafbfc',
                            }}
                        >
                            {contentMd.trim() ? (
                                <HelpArticleView content={contentMd} />
                            ) : (
                                <Typography color="text.secondary" align="center" sx={{ py: 4 }}>
                                    Нет содержимого для предпросмотра
                                </Typography>
                            )}
                        </Box>
                    )}
                </Box>
            </Box>
        </DraggableDialog>
    );
};

export default HelpArticleEditor;