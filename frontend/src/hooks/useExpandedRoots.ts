// frontend/src/hooks/useExpandedRoots.ts
/**
 * Хук для управления раскрытыми корневыми версиями планов
 * в «Истории планов» (Итерация 13.21).
 *
 * Логика:
 *  - Set содержит ID РАСКРЫТЫХ корней.
 *  - По умолчанию (initialized === false) — все корни РАСКРЫТЫ.
 *  - После первого взаимодействия (initialized === true):
 *    - корень раскрыт, если его ID в Set;
 *    - корень свёрнут, если его нет в Set.
 *
 * Это означает:
 *  - При первой загрузке — все корни раскрыты, Set пустой,
 *    initialized = false.
 *  - Пользователь кликает на ▶ — корень добавляется в Set
 *    (или, если он уже там, удаляется), initialized = true.
 *  - После этого Set явно хранит раскрытые корни.
 *
 * Состояние сохраняется в localStorage per-organization.
 * Ключ v3 — чтобы не конфликтовать со старыми форматами.
 */
import {useCallback, useEffect, useRef, useState} from 'react';

const STORAGE_KEY = 'aps_expanded_plan_roots_v3';

export const useExpandedRoots = (organizationId?: string | null) => {
    const storageKey = organizationId
        ? `${STORAGE_KEY}_${organizationId}`
        : STORAGE_KEY;

    // Set раскрытых ID корней.
    const [expanded, setExpanded] = useState<Set<string>>(() => {
        try {
            const raw = localStorage.getItem(storageKey);
            if (raw) {
                const parsed = JSON.parse(raw);
                if (Array.isArray(parsed)) {
                    return new Set(parsed);
                }
            }
        } catch { /* ignore */ }
        return new Set();
    });

    // Пользователь уже взаимодействовал?
    const [initialized, setInitialized] = useState<boolean>(() => {
        try {
            const raw = localStorage.getItem(storageKey);
            return raw !== null;
        } catch {
            return false;
        }
    });

    // Ref для отслеживания предыдущего storageKey.
    const prevStorageKeyRef = useRef(storageKey);

    // Читаем из localStorage ТОЛЬКО при смене организации.
    useEffect(() => {
        if (prevStorageKeyRef.current === storageKey) return;
        prevStorageKeyRef.current = storageKey;

        try {
            const raw = localStorage.getItem(storageKey);
            if (raw) {
                const parsed = JSON.parse(raw);
                if (Array.isArray(parsed)) {
                    setExpanded(new Set(parsed));
                    setInitialized(true);
                    return;
                }
            }
        } catch { /* ignore */ }
        setExpanded(new Set());
        setInitialized(false);
    }, [storageKey]);

    // Сохраняем при каждом изменении (только после инициализации).
    useEffect(() => {
        if (!initialized) return;
        try {
            localStorage.setItem(
                storageKey,
                JSON.stringify(Array.from(expanded)),
            );
        } catch { /* ignore */ }
    }, [expanded, initialized, storageKey]);

    /**
     * Раскрыт ли корень.
     *
     *  - Если пользователь ещё не взаимодействовал (initialized === false) —
     *    все корни раскрыты.
     *  - Иначе — раскрыт только тот, чей ID в Set.
     */
    const isExpanded = useCallback((rootId: string): boolean => {
        if (!initialized) return true;
        return expanded.has(rootId);
    }, [expanded, initialized]);

    const toggle = useCallback((rootId: string) => {
        setInitialized(true);
        setExpanded((prev) => {
            const next = new Set(prev);
            if (next.has(rootId)) {
                next.delete(rootId);
            } else {
                next.add(rootId);
            }
            return next;
        });
    }, []);

    /**
     * Развернуть все корни.
     *  - Очищаем Set (тогда initialized = true, все раскрыты).
     */
    const expandAll = useCallback((allRootIds: string[]) => {
        setInitialized(true);
        // Пустой Set + initialized = true → isExpanded возвращает
        // expanded.has(rootId) = false для всех. Это НЕПРАВИЛЬНО.
        // Поэтому для "развернуть всё" нужно явно добавить все ID.
        setExpanded(new Set(allRootIds));
    }, []);

    /**
     * Свернуть все корни.
     *  - Пустой Set + initialized = true → все свёрнуты.
     */
    const collapseAll = useCallback((_allRootIds: string[]) => {
        setInitialized(true);
        setExpanded(new Set());  // пустой Set → все свёрнуты
    }, []);

    return {
        expanded,
        isExpanded,
        toggle,
        expandAll,
        collapseAll,
    };
};