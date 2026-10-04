// frontend/src/components/help/Hint.tsx
/**
 * Компонент контекстной подсказки (Итерация 15.2).
 *
 * Рендерит компактную иконку «?» рядом с элементом UI.
 * По клику открывает Popover с заголовком, markdown-телом
 * и кнопкой «Читать подробнее» (ведёт на /help/{slug}).
 *
 * Если подсказка не найдена (нет в контексте) — компонент
 * рендерит null. Это позволяет безопасно добавлять <Hint/>
 * в код до того, как подсказка создана в БД.
 *
 * Использование:
 *   <Box>
 *       <Typography>Пересчёт плана <Hint id="planning.recalc"/></Typography>
 *   </Box>
 *
 * Или с явным размером:
 *   <Hint id="gantt.edit_mode" size="small"/>
 */
import React, {useState} from 'react';
import {Box, Button, Divider, IconButton, Popover, Tooltip, Typography,} from '@mui/material';
import {HelpOutlined as HelpOutlineIcon, MenuBook as MenuBookIcon,} from '@mui/icons-material';
import {useNavigate} from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import {useHint} from '../../context/HelpHintsContext';

interface HintProps {
    /** Ключ подсказки (например, 'planning.recalc'). */
    id: string;

    /** Размер иконки: 'small' (14px) или 'medium' (18px). */
    size?: 'small' | 'medium';

    /** Цвет иконки. По умолчанию — серый (text.secondary). */
    color?: string;

    /** Дополнительные стили. */
    sx?: object;

    /** Tooltip при наведении (если не задан — title подсказки). */
    tooltipText?: string;
}

const Hint: React.FC<HintProps> = ({
                                       id,
                                       size = 'small',
                                       color,
                                       sx,
                                       tooltipText,
                                   }) => {
    const hint = useHint(id);
    const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);
    const navigate = useNavigate();

    // Нет подсказки — ничего не рендерим
    if (!hint) return null;

    const iconSize = size === 'small' ? 14 : 18;
    const open = Boolean(anchorEl);

    const handleOpen = (e: React.MouseEvent<HTMLElement>) => {
        e.stopPropagation();
        setAnchorEl(e.currentTarget);
    };

    const handleClose = () => {
        setAnchorEl(null);
    };

    const handleReadMore = () => {
        if (hint.article_slug) {
            navigate(`/help/${hint.article_slug}`);
        }
        handleClose();
    };

    return (
        <>
            <Tooltip
                title={tooltipText || hint.title}
                arrow
                placement="top"
            >
                <IconButton
                    size="small"
                    onClick={handleOpen}
                    sx={{
                        p: 0.25,
                        ml: 0.5,
                        verticalAlign: 'middle',
                        color: color || 'text.secondary',
                        '&:hover': {
                            color: 'primary.main',
                        },
                        ...sx,
                    }}
                    aria-label={`Подсказка: ${hint.title}`}
                >
                    <HelpOutlineIcon sx={{fontSize: iconSize}}/>
                </IconButton>
            </Tooltip>

            <Popover
                open={open}
                anchorEl={anchorEl}
                onClose={handleClose}
                anchorOrigin={{
                    vertical: 'bottom',
                    horizontal: 'center',
                }}
                transformOrigin={{
                    vertical: 'top',
                    horizontal: 'center',
                }}
                slotProps={{
                    paper: {
                        sx: {
                            maxWidth: 360,
                            p: 2,
                        },
                    },
                }}
            >
                <Box
                    sx={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 1,
                        mb: 1,
                    }}
                >
                    <HelpOutlineIcon
                        fontSize="small"
                        color="primary"
                    />
                    <Typography
                        variant="subtitle2"
                        sx={{fontWeight: 700}}
                    >
                        {hint.title}
                    </Typography>
                </Box>

                <Divider sx={{mb: 1.5}}/>

                {/* Markdown-тело подсказки */}
                <Box
                    sx={{
                        fontSize: '0.85rem',
                        lineHeight: 1.6,
                        '& p': {m: 0, mb: 1},
                        '& p:last-child': {mb: 0},
                        '& code': {
                            bgcolor: '#f0f2f5',
                            px: 0.5,
                            py: 0.25,
                            borderRadius: 0.5,
                            fontFamily: 'monospace',
                            fontSize: '0.8em',
                        },
                        '& strong': {
                            color: '#2c3e50',
                            fontWeight: 600,
                        },
                        '& ul, & ol': {
                            pl: 2.5,
                            m: 0,
                            mb: 1,
                        },
                    }}
                >
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {hint.body_md}
                    </ReactMarkdown>
                </Box>

                {/* Кнопка «Читать подробнее» — только если есть статья */}
                {hint.article_slug && (
                    <Box
                        sx={{
                            display: 'flex',
                            justifyContent: 'flex-end',
                            mt: 2,
                        }}
                    >
                        <Button
                            size="small"
                            variant="text"
                            startIcon={<MenuBookIcon fontSize="small"/>}
                            onClick={handleReadMore}
                            sx={{
                                textTransform: 'none',
                                fontSize: '0.8rem',
                            }}
                        >
                            Читать подробнее
                        </Button>
                    </Box>
                )}
            </Popover>
        </>
    );
};

export default Hint;