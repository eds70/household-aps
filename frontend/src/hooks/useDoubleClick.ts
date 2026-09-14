// frontend/src/hooks/useDoubleClick.ts
import React, { useRef, useCallback } from 'react';

interface UseDoubleClickOptions {
    onDoubleClick: (item: any) => void;
    onClick?: (item: any) => void;
    delay?: number;
}

export const useDoubleClick = ({
                                   onDoubleClick,
                                   onClick,
                                   delay = 300,
                               }: UseDoubleClickOptions) => {
    const clickTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const lastClickTimeRef = useRef<number>(0);
    const lastClickItemRef = useRef<any>(null);

    const handleClick = useCallback(
        (item: any) => {
            const now = Date.now();
            const timeDiff = now - lastClickTimeRef.current;
            const isSameItem = lastClickItemRef.current === item;

            // Очищаем предыдущий таймаут
            if (clickTimeoutRef.current) {
                clearTimeout(clickTimeoutRef.current);
                clickTimeoutRef.current = null;
            }

            // Проверяем, является ли это двойным кликом
            if (timeDiff < delay && isSameItem) {
                // Это двойной клик
                lastClickTimeRef.current = 0;
                lastClickItemRef.current = null;
                onDoubleClick(item);
            } else {
                // Это первый клик или одинарный клик
                lastClickTimeRef.current = now;
                lastClickItemRef.current = item;

                // Устанавливаем таймаут для обработки одинарного клика
                clickTimeoutRef.current = setTimeout(() => {
                    if (onClick) {
                        onClick(item);
                    }
                    lastClickTimeRef.current = 0;
                    lastClickItemRef.current = null;
                    clickTimeoutRef.current = null;
                }, delay);
            }
        },
        [onDoubleClick, onClick, delay]
    );

    // Очистка при размонтировании
    React.useEffect(() => {
        return () => {
            if (clickTimeoutRef.current) {
                clearTimeout(clickTimeoutRef.current);
            }
        };
    }, []);

    return handleClick;
};

export default useDoubleClick;