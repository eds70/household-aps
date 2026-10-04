// frontend/src/context/HelpHintsContext.tsx
/**
 * Глобальный контекст контекстных подсказок (Итерация 15.2).
 *
 * Один запрос GET /api/v1/help/hints при монтировании приложения.
 * Результат кэшируется до перезагрузки страницы.
 *
 * Использование в компонентах:
 *   const { getHint, loading } = useHelpHints();
 *   const hint = getHint('planning.recalc');
 *   if (hint) { ... }
 *
 * Или через удобный хук useHint(hintKey):
 *   const hint = useHint('planning.recalc');
 *
 * Если подсказки нет (не опубликована, удалена) — возвращается null.
 * Это нормальное поведение — компонент <Hint/> в этом случае
 * ничего не рендерит.
 */
import React, {createContext, useCallback, useContext, useEffect, useMemo, useState,} from 'react';
import {helpApi} from '../services/api';
import {useAuth} from './AuthContext';
import type {HelpHint} from '../types';

interface HelpHintsContextType {
    /** Словарь {hint_key: HelpHint}. Пустой до загрузки. */
    hints: Record<string, HelpHint>;

    /** Идёт ли загрузка. */
    loading: boolean;

    /** Ошибка загрузки (если была). */
    error: string | null;

    /** Получить подсказку по ключу (или null). */
    getHint: (hintKey: string) => HelpHint | null;

    /** Принудительно перезагрузить. */
    reload: () => Promise<void>;
}

export const HelpHintsContext = createContext<HelpHintsContextType | undefined>(
    undefined,
);

export const HelpHintsProvider: React.FC<{ children: React.ReactNode }> = ({
                                                                               children,
                                                                           }) => {
    const [hints, setHints] = useState<Record<string, HelpHint>>({});
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const {isAuthenticated, isLoading: authLoading} = useAuth();

    const loadHints = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const resp = await helpApi.getHints();
            setHints(resp.hints || {});
        } catch (err: any) {
            // Не критично — подсказки это «nice to have».
            // Молча логируем в консоль, не показываем пользователю.
            console.warn('[HelpHints] Не удалось загрузить подсказки:', err);
            const detail = err.response?.data?.detail;
            setError(typeof detail === 'string' ? detail : 'Ошибка загрузки');
            setHints({});
        } finally {
            setLoading(false);
        }
    }, []);

    // Загружаем только после аутентификации
    useEffect(() => {
        if (!authLoading && isAuthenticated) {
            void loadHints();
        }
    }, [authLoading, isAuthenticated, loadHints]);

    const getHint = useCallback(
        (hintKey: string): HelpHint | null => {
            return hints[hintKey] || null;
        },
        [hints],
    );

    const value = useMemo<HelpHintsContextType>(
        () => ({
            hints,
            loading,
            error,
            getHint,
            reload: loadHints,
        }),
        [hints, loading, error, getHint, loadHints],
    );

    return (
        <HelpHintsContext.Provider value={value}>
            {children}
        </HelpHintsContext.Provider>
    );
};

/**
 * Основной хук контекста. Бросает, если вне провайдера.
 */
export const useHelpHints = (): HelpHintsContextType => {
    const ctx = useContext(HelpHintsContext);
    if (!ctx) {
        throw new Error(
            'useHelpHints must be used within HelpHintsProvider',
        );
    }
    return ctx;
};

/**
 * Удобный хук для получения одной подсказки по ключу.
 *
 * Возвращает:
 *   - HelpHint, если загружена и существует;
 *   - null, если подсказки нет или загрузка не завершена.
 *
 * Не подписывает компонент на изменение других подсказок —
 * только на ту, что указана в hintKey (мемоизируется).
 */
export const useHint = (hintKey: string): HelpHint | null => {
    const {hints} = useHelpHints();
    return hints[hintKey] || null;
};