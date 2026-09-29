// frontend/src/hooks/useExpandedGroups.ts
/**
 * Хук для управления раскрытыми группами LINE_FILL
 * на Ганте (Итерация 13.17).
 *
 * Хранит Set ключей раскрытых групп. При смене версии плана
 * сбрасывается.
 */
import {useCallback, useEffect, useState} from 'react';

const STORAGE_KEY_PREFIX = 'aps_gantt_expanded_groups_';

export const useExpandedGroups = (versionId: string | null) => {
    const storageKey = `${STORAGE_KEY_PREFIX}${versionId || 'draft'}`;

    const [expanded, setExpanded] = useState<Set<string>>(() => {
        try {
            const raw = localStorage.getItem(storageKey);
            if (raw) {
                const parsed = JSON.parse(raw);
                if (Array.isArray(parsed)) {
                    return new Set(parsed);
                }
            }
        } catch {
            // ignore
        }
        return new Set();
    });

    // При смене версии — перечитываем из localStorage
    useEffect(() => {
        try {
            const raw = localStorage.getItem(storageKey);
            if (raw) {
                const parsed = JSON.parse(raw);
                if (Array.isArray(parsed)) {
                    setExpanded(new Set(parsed));
                    return;
                }
            }
        } catch {
            // ignore
        }
        setExpanded(new Set());
    }, [storageKey]);

    // Сохраняем в localStorage
    useEffect(() => {
        try {
            localStorage.setItem(
                storageKey,
                JSON.stringify(Array.from(expanded)),
            );
        } catch {
            // ignore
        }
    }, [expanded, storageKey]);

    const toggleGroup = useCallback((groupKey: string) => {
        setExpanded((prev) => {
            const next = new Set(prev);
            if (next.has(groupKey)) {
                next.delete(groupKey);
            } else {
                next.add(groupKey);
            }
            return next;
        });
    }, []);

    const expandAll = useCallback((keys: string[]) => {
        setExpanded(new Set(keys));
    }, []);

    const collapseAll = useCallback(() => {
        setExpanded(new Set());
    }, []);

    return {
        expanded,
        toggleGroup,
        expandAll,
        collapseAll,
    };
};