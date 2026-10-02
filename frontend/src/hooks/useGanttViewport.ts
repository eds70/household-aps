// frontend/src/hooks/useGanttViewport.ts
import type {MutableRefObject, RefObject} from 'react';
/**
 * Хук для управления viewport диаграммы Ганта
 * (Итерация 13.17 + 14.1).
 *
 * Отвечает за:
 *  - Pan (влево/вправо).
 *  - Zoom (in/out).
 *  - Fit (показать всё, ограничение 7 дней).
 *  - Go to today.
 *  - Сохранение viewport в localStorage (per version).
 *  - Восстановление viewport при смене версии.
 *
 * Итерация 13.17 (9i): readViewportFromStorage (экспорт).
 * Итерация 13.17 (9l): убраны отладочные логи.
 *
 * Итерация 14.1:
 *  - Добавлены функции loadGroupByMode / saveGroupByMode.
 *  - groupByMode хранится ГЛОБАЛЬНО (не per-version),
 *    так как пользователь обычно не переключает режим
 *    при каждой смене плана.
 *  - Аналогично для showBatchBrackets.
 */
import {useCallback, useEffect, useRef} from 'react';
import type {Timeline} from 'vis-timeline/standalone';
import type {ViewportState} from '../components/gantt/types';
import type {GroupByMode} from '../types';
import {
    DEFAULT_GROUP_BY_MODE,
    DEFAULT_SHOW_BATCH_BRACKETS,
    getViewportStorageKey,
    PAN_FACTOR,
    STORAGE_KEYS,
    ZOOM_IN_FACTOR,
    ZOOM_OUT_FACTOR,
} from '../components/gantt/constants';

export interface UseGanttViewportParams {
    timelineRef: RefObject<Timeline | null>;
    versionId: string | null;
}

export interface UseGanttViewportResult {
    viewportRef: MutableRefObject<ViewportState | null>;
    suppressViewportSyncRef: MutableRefObject<boolean>;

    handlePanLeft: () => void;
    handlePanRight: () => void;
    handleZoomIn: () => void;
    handleZoomOut: () => void;
    handleFitAll: () => void;
    handleGoToToday: () => void;

    saveViewportToStorage: (view: ViewportState) => void;
    persistCurrentViewport: () => void;
}

// ==========================================
// УТИЛИТЫ: viewport в localStorage (per version)
// ==========================================

/**
 * Читает сохранённый viewport из localStorage синхронно.
 *
 * Используется в useGanttTimeline при первом рендере — до того,
 * как useEffect в useGanttViewport обновит viewportRef.current.
 */
export const readViewportFromStorage = (
    versionId: string | null,
): ViewportState | null => {
    if (!versionId) return null;
    const key = getViewportStorageKey(versionId);
    try {
        const raw = localStorage.getItem(key);
        if (raw) {
            const parsed = JSON.parse(raw) as ViewportState;
            if (parsed.start && parsed.end) {
                return parsed;
            }
        }
    } catch {
        // ignore
    }
    return null;
};

// ==========================================
// ИТЕРАЦИЯ 14.1: groupByMode в localStorage (глобально)
// ==========================================

/**
 * Читает сохранённый режим группировки из localStorage.
 *
 * Если значение отсутствует или невалидно — возвращает
 * DEFAULT_GROUP_BY_MODE ('equipment').
 */
export const readGroupByModeFromStorage = (): GroupByMode => {
    try {
        const raw = localStorage.getItem(STORAGE_KEYS.groupByMode);
        if (raw === 'equipment' || raw === 'batch') {
            return raw;
        }
    } catch {
        // ignore
    }
    return DEFAULT_GROUP_BY_MODE;
};

/**
 * Сохраняет режим группировки в localStorage.
 */
export const saveGroupByModeToStorage = (mode: GroupByMode): void => {
    try {
        localStorage.setItem(STORAGE_KEYS.groupByMode, mode);
    } catch {
        // ignore
    }
};

// ==========================================
// ИТЕРАЦИЯ 14.1: showBatchBrackets в localStorage (глобально)
// ==========================================

/**
 * Читает настройку «Показывать скобки партий».
 *
 * Если значение отсутствует — возвращает
 * DEFAULT_SHOW_BATCH_BRACKETS (true).
 */
export const readShowBatchBracketsFromStorage = (): boolean => {
    try {
        const raw = localStorage.getItem(STORAGE_KEYS.showBatchBrackets);
        if (raw === '1') return true;
        if (raw === '0') return false;
    } catch {
        // ignore
    }
    return DEFAULT_SHOW_BATCH_BRACKETS;
};

/**
 * Сохраняет настройку «Показывать скобки партий» в localStorage.
 */
export const saveShowBatchBracketsToStorage = (value: boolean): void => {
    try {
        localStorage.setItem(
            STORAGE_KEYS.showBatchBrackets,
            value ? '1' : '0',
        );
    } catch {
        // ignore
    }
};

// ==========================================
// ОСНОВНОЙ ХУК
// ==========================================

export const useGanttViewport = (
    params: UseGanttViewportParams,
): UseGanttViewportResult => {
    const {timelineRef, versionId} = params;

    const viewportRef = useRef<ViewportState | null>(null);
    const suppressViewportSyncRef = useRef<boolean>(false);

    const saveViewportToStorage = useCallback(
        (view: ViewportState) => {
            const key = getViewportStorageKey(versionId);
            try {
                localStorage.setItem(key, JSON.stringify(view));
            } catch {
                // ignore
            }
        },
        [versionId],
    );

    useEffect(() => {
        viewportRef.current = readViewportFromStorage(versionId);
    }, [versionId]);

    const persistCurrentViewport = useCallback(() => {
        if (!timelineRef.current) return;
        if (suppressViewportSyncRef.current) return;
        const range = timelineRef.current.getWindow();
        if (!range || !range.start || !range.end) return;
        const view: ViewportState = {
            start: new Date(range.start).toISOString(),
            end: new Date(range.end).toISOString(),
        };
        viewportRef.current = view;
        saveViewportToStorage(view);
    }, [saveViewportToStorage, timelineRef]);

    const panByFactor = useCallback(
        (factor: number) => {
            if (!timelineRef.current) return;
            const range = timelineRef.current.getWindow();
            const interval = range.end.getTime() - range.start.getTime();
            const shift = interval * factor;
            timelineRef.current.setWindow(
                new Date(range.start.getTime() + shift),
                new Date(range.end.getTime() + shift),
                {animation: {duration: 300, easingFunction: 'easeInOutQuad'}},
            );
        },
        [timelineRef],
    );

    const handlePanLeft = useCallback(
        () => panByFactor(-PAN_FACTOR),
        [panByFactor],
    );
    const handlePanRight = useCallback(
        () => panByFactor(PAN_FACTOR),
        [panByFactor],
    );

    const zoomByFactor = useCallback(
        (factor: number) => {
            if (!timelineRef.current) return;
            const range = timelineRef.current.getWindow();
            const center =
                (range.start.getTime() + range.end.getTime()) / 2;
            const half =
                ((range.end.getTime() - range.start.getTime()) / 2) * factor;
            timelineRef.current.setWindow(
                new Date(center - half),
                new Date(center + half),
                {animation: {duration: 300, easingFunction: 'easeInOutQuad'}},
            );
        },
        [timelineRef],
    );

    const handleZoomIn = useCallback(
        () => zoomByFactor(ZOOM_IN_FACTOR),
        [zoomByFactor],
    );
    const handleZoomOut = useCallback(
        () => zoomByFactor(ZOOM_OUT_FACTOR),
        [zoomByFactor],
    );

    const handleFitAll = useCallback(() => {
        if (!timelineRef.current) return;
        suppressViewportSyncRef.current = true;

        const MAX_FIT_WINDOW_MS = 1000 * 60 * 60 * 24 * 7;

        try {
            const timelineAny = timelineRef.current as any;
            const itemsData = timelineAny.itemsData;
            const ids = itemsData ? itemsData.getIds() : [];

            if (ids.length === 0) {
                timelineRef.current.fit({animation: false});
            } else {
                const allItems = itemsData.get(ids) as any[];
                let minStart = Infinity;
                let maxEnd = -Infinity;

                for (const item of allItems) {
                    if (!item || !item.start || !item.end) continue;
                    const s = new Date(item.start).getTime();
                    const e = new Date(item.end).getTime();
                    if (s < minStart) minStart = s;
                    if (e > maxEnd) maxEnd = e;
                }

                if (!isFinite(minStart) || !isFinite(maxEnd)) {
                    timelineRef.current.fit({animation: false});
                } else {
                    let windowStart = minStart;
                    let windowEnd = maxEnd;

                    if (windowEnd - windowStart > MAX_FIT_WINDOW_MS) {
                        windowEnd = windowStart + MAX_FIT_WINDOW_MS;
                    }

                    timelineRef.current.setWindow(
                        new Date(windowStart),
                        new Date(windowEnd),
                        {animation: {duration: 300, easingFunction: 'easeInOutQuad'}},
                    );
                }
            }
        } catch {
            timelineRef.current.fit({animation: false});
        }

        setTimeout(() => {
            suppressViewportSyncRef.current = false;
            if (timelineRef.current) {
                const range = timelineRef.current.getWindow();
                const view: ViewportState = {
                    start: new Date(range.start).toISOString(),
                    end: new Date(range.end).toISOString(),
                };
                viewportRef.current = view;
                saveViewportToStorage(view);
            }
        }, 400);
    }, [saveViewportToStorage, timelineRef]);

    const handleGoToToday = useCallback(() => {
        if (!timelineRef.current) return;
        const now = new Date();
        const half = 1000 * 60 * 60 * 24 * 3;
        timelineRef.current.setWindow(
            new Date(now.getTime() - half),
            new Date(now.getTime() + half),
            {animation: {duration: 300, easingFunction: 'easeInOutQuad'}},
        );
    }, [timelineRef]);

    return {
        viewportRef,
        suppressViewportSyncRef,
        handlePanLeft,
        handlePanRight,
        handleZoomIn,
        handleZoomOut,
        handleFitAll,
        handleGoToToday,
        saveViewportToStorage,
        persistCurrentViewport,
    };
};