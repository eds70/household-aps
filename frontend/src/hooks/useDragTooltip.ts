// frontend/src/hooks/useDragTooltip.ts
/**
 * Хук для управления tooltip'ом при перетаскивании и изменении
 * длительности задач (Итерация 13.17 + 13.18).
 *
 * Итерация 13.18 (fix #5):
 *  - Tooltip показывается из нативных mousemove/mouseup слушателей
 *    (vis-timeline 8.x не генерирует itemmoving/itemresizing).
 *  - Добавлен метод updatePosition для быстрого обновления только
 *    координат (без пересоздания текста).
 *  - Добавлен метод updateText для обновления текстовых полей
 *    без пересоздания объекта.
 *  - Добавлен метод patch для частичного обновления.
 */
import {useCallback, useRef, useState} from 'react';
import type {DragTooltipState} from '../types';

export type DragOperationType = 'move' | 'resize';

export interface ShowTooltipOptions {
    /** Тип операции: перемещение или изменение длительности. */
    operationType?: DragOperationType;
    /** Предупреждение (жёлтый блок снизу). */
    warning?: string;
    /** Изменение длительности в минутах. */
    deltaMinutes?: number;
    /** Сколько задач сдвинется каскадом. */
    affectedCount?: number;
    /** Текущее время начала задачи (ISO). */
    startTime?: string;
    /** Текущее время окончания задачи (ISO). */
    endTime?: string;
    /** Исходное время начала задачи (ISO). */
    originalStart?: string;
    /** Исходное время окончания задачи (ISO). */
    originalEnd?: string;
}

export interface UpdateTextOptions {
    text?: string;
    deltaMinutes?: number;
    startTime?: string;
    endTime?: string;
    warning?: string;
    affectedCount?: number;
}

export const useDragTooltip = () => {
    const [tooltip, setTooltip] = useState<DragTooltipState | null>(null);

    // Реф для доступа к актуальному состоянию в updatePosition / updateText
    const tooltipRef = useRef<DragTooltipState | null>(null);

    // Синхронизируем реф
    const setTooltipSafe = useCallback((next: DragTooltipState | null) => {
        tooltipRef.current = next;
        setTooltip(next);
    }, []);

    /**
     * Показать tooltip целиком. Если уже показан — перезапишет.
     */
    const show = useCallback((
        x: number,
        y: number,
        text: string,
        options?: ShowTooltipOptions,
    ) => {
        setTooltipSafe({
            x: x + 15,
            y: y + 15,
            text,
            warning: options?.warning,
            deltaMinutes: options?.deltaMinutes,
            affectedCount: options?.affectedCount,
            startTime: options?.startTime,
            endTime: options?.endTime,
            originalStart: options?.originalStart,
            originalEnd: options?.originalEnd,
            operationType: options?.operationType,
        });
    }, [setTooltipSafe]);

    /**
     * Обновить ТОЛЬКО позицию. Не трогает текст. Быстрое.
     * Используется при live-обновлении во время перетаскивания.
     */
    const updatePosition = useCallback((x: number, y: number) => {
        const prev = tooltipRef.current;
        if (!prev) return;
        // Не пересоздаём объект — мутируем поля и триггерим setState
        // через новый объект (React не увидит мутации того же объекта).
        const next: DragTooltipState = {
            ...prev,
            x: x + 15,
            y: y + 15,
        };
        tooltipRef.current = next;
        setTooltip(next);
    }, []);

    /**
     * Обновить текстовые поля, не трогая позицию.
     * Используется реже (раз в 150–200 мс).
     */
    const updateText = useCallback((options: UpdateTextOptions) => {
        const prev = tooltipRef.current;
        if (!prev) return;
        const next: DragTooltipState = {
            ...prev,
            text: options.text ?? prev.text,
            deltaMinutes: options.deltaMinutes ?? prev.deltaMinutes,
            startTime: options.startTime ?? prev.startTime,
            endTime: options.endTime ?? prev.endTime,
            warning: options.warning ?? prev.warning,
            affectedCount: options.affectedCount ?? prev.affectedCount,
        };
        tooltipRef.current = next;
        setTooltip(next);
    }, []);

    /**
     * Полная замена состояния. Удобно, когда нужно обновить
     * и позицию, и текст одним вызовом.
     */
    const set = useCallback((next: DragTooltipState | null) => {
        setTooltipSafe(next);
    }, [setTooltipSafe]);

    const hide = useCallback(() => {
        setTooltipSafe(null);
    }, [setTooltipSafe]);

    return {tooltip, show, updatePosition, updateText, set, hide};
};