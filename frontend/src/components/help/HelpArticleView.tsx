// frontend/src/components/help/HelpArticleView.tsx
/**
 * Просмотр markdown-статьи справки (Итерация 15.1).
 *
 * Использует react-markdown + remark-gfm. Ссылки вида
 * [текст](/help/slug) перехватываются и открывают соответствующую
 * статью внутри приложения.
 */
import React from 'react';
import type {Components} from 'react-markdown';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {Box, Link} from '@mui/material';

interface HelpArticleViewProps {
    /** Markdown-контент. */
    content: string;
    /** Колбэк при клике на внутреннюю ссылку /help/xxx. */
    onInternalLink?: (slug: string) => void;
}

const HelpArticleView: React.FC<HelpArticleViewProps> = ({
                                                             content,
                                                             onInternalLink,
                                                         }) => {
    const components: Components = {
        // Внутренние ссылки /help/slug перехватываем
        a: ({href, children, ...props}) => {
            const isInternal = href?.startsWith('/help/');
            const slug = isInternal ? href!.replace('/help/', '') : null;

            if (isInternal && slug && onInternalLink) {
                return (
                    <Link
                        component="button"
                        type="button"
                        onClick={(e) => {
                            e.preventDefault();
                            onInternalLink(slug);
                        }}
                        sx={{
                            textAlign: 'left',
                            cursor: 'pointer',
                            textDecoration: 'underline',
                        }}
                    >
                        {children}
                    </Link>
                );
            }

            return (
                <Link
                    href={href}
                    target="_blank"
                    rel="noopener noreferrer"
                    {...props}
                >
                    {children}
                </Link>
            );
        },

        // Таблицы — со скроллом
        table: ({children}) => (
            <Box sx={{overflowX: 'auto', my: 2}}>
                <table
                    style={{
                        borderCollapse: 'collapse',
                        width: '100%',
                        fontSize: '0.9rem',
                    }}
                >
                    {children}
                </table>
            </Box>
        ),
        th: ({children}) => (
            <th
                style={{
                    border: '1px solid #e0e0e0',
                    padding: '8px 12px',
                    backgroundColor: '#f5f7fa',
                    textAlign: 'left',
                    fontWeight: 600,
                }}
            >
                {children}
            </th>
        ),
        td: ({children}) => (
            <td
                style={{
                    border: '1px solid #e0e0e0',
                    padding: '8px 12px',
                }}
            >
                {children}
            </td>
        ),

        // Код
        code: ({children, className}) => {
            const isInline = !className;
            if (isInline) {
                return (
                    <code
                        style={{
                            backgroundColor: '#f0f2f5',
                            padding: '2px 6px',
                            borderRadius: 4,
                            fontFamily: 'monospace',
                            fontSize: '0.85em',
                            color: '#c0392b',
                        }}
                    >
                        {children}
                    </code>
                );
            }
            return (
                <code
                    className={className}
                    style={{
                        display: 'block',
                        backgroundColor: '#2c3e50',
                        color: '#ecf0f1',
                        padding: 12,
                        borderRadius: 6,
                        fontFamily: 'monospace',
                        fontSize: '0.85em',
                        overflowX: 'auto',
                        whiteSpace: 'pre',
                    }}
                >
                    {children}
                </code>
            );
        },

        // Блоки цитат (для 💡 Совет / ⚠️ Внимание)
        blockquote: ({children}) => (
            <Box
                sx={{
                    borderLeft: '4px solid #3498db',
                    bgcolor: '#e3f2fd',
                    pl: 2,
                    py: 1,
                    my: 1.5,
                    borderRadius: '0 4px 4px 0',
                }}
            >
                {children}
            </Box>
        ),
    };

    return (
        <Box
            sx={{
                '& h1': {
                    fontSize: '1.75rem',
                    fontWeight: 700,
                    color: '#2c3e50',
                    mt: 0,
                    mb: 2,
                    borderBottom: '2px solid #ecf0f1',
                    pb: 1,
                },
                '& h2': {
                    fontSize: '1.3rem',
                    fontWeight: 600,
                    color: '#2c3e50',
                    mt: 3,
                    mb: 1.5,
                },
                '& h3': {
                    fontSize: '1.1rem',
                    fontWeight: 600,
                    color: '#34495e',
                    mt: 2,
                    mb: 1,
                },
                '& p': {
                    lineHeight: 1.7,
                    my: 1,
                },
                '& ul, & ol': {
                    pl: 3,
                    my: 1,
                },
                '& li': {
                    my: 0.5,
                    lineHeight: 1.6,
                },
                '& a': {
                    color: '#1976d2',
                    textDecoration: 'none',
                    '&:hover': {textDecoration: 'underline'},
                },
                '& hr': {
                    border: 'none',
                    borderTop: '1px solid #ecf0f1',
                    my: 3,
                },
                '& strong': {
                    color: '#2c3e50',
                    fontWeight: 600,
                },
            }}
        >
            <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={components}
            >
                {content}
            </ReactMarkdown>
        </Box>
    );
};

export default HelpArticleView;