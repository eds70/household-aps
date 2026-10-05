// frontend/src/context/TutorialContext.tsx
/**
 * Контекст интерактивных туров (Итерация 15.3).
 *
 * Управляет состоянием активного тура и сохранением
 * прогресса в localStorage.
 *
 * Не зависит от API react-joyride напрямую — только через
 * Tour и Step (см. `tutorial/types.ts` и `tutorial/tours.ts`).
 *
 * Итерация 15.3 (fix): добавлена функция getRouteForStep —
 * возвращает URL, на который нужно перейти перед показом
 * конкретного шага. Используется в TutorialRunner
 * (см. App.tsx) для навигации между страницами.
 */
import React, {createContext, useCallback, useContext, useMemo, useState,} from 'react';
import type {Tour, TutorialContextType} from '../tutorial/types';
import {getTourById} from '../tutorial/tours';

export const TutorialContext = createContext<TutorialContextType | undefined>(
    undefined,
);

const STORAGE_KEY_PREFIX = 'aps_tutorial_completed_';

export const TutorialProvider: React.FC<{ children: React.ReactNode }> = ({
                                                                              children,
                                                                          }) => {
    const [activeTour, setActiveTour] = useState<Tour | null>(null);
    const [currentStepIndex, setCurrentStepIndex] = useState(0);

    // ==========================================
    // Прогресс
    // ==========================================
    const isTourCompleted = useCallback((tourId: string): boolean => {
        try {
            return localStorage.getItem(STORAGE_KEY_PREFIX + tourId) === '1';
        } catch {
            return false;
        }
    }, []);

    const markTourCompleted = useCallback((tourId: string) => {
        try {
            localStorage.setItem(STORAGE_KEY_PREFIX + tourId, '1');
        } catch {
            // ignore
        }
    }, []);

    const resetTourProgress = useCallback((tourId: string) => {
        try {
            localStorage.removeItem(STORAGE_KEY_PREFIX + tourId);
        } catch {
            // ignore
        }
    }, []);

    // ==========================================
    // Управление туром
    // ==========================================
    const startTour = useCallback((tourId: string) => {
        const tour = getTourById(tourId);
        if (!tour) {
            console.warn(`[Tutorial] Тур "${tourId}" не найден`);
            return;
        }
        setActiveTour(tour);
        setCurrentStepIndex(0);
    }, []);

    const stopTour = useCallback(() => {
        // Если тур дошёл до последнего шага — считаем пройденным
        if (activeTour && currentStepIndex >= activeTour.steps.length - 1) {
            markTourCompleted(activeTour.id);
        }
        setActiveTour(null);
        setCurrentStepIndex(0);
    }, [activeTour, currentStepIndex, markTourCompleted]);

    const nextStep = useCallback(() => {
        if (!activeTour) return;
        setCurrentStepIndex((prev) =>
            Math.min(prev + 1, activeTour.steps.length - 1),
        );
    }, [activeTour]);

    const prevStep = useCallback(() => {
        setCurrentStepIndex((prev) => Math.max(prev - 1, 0));
    }, []);

    const goToStep = useCallback((index: number) => {
        if (!activeTour) return;
        setCurrentStepIndex(
            Math.max(0, Math.min(index, activeTour.steps.length - 1)),
        );
    }, [activeTour]);

    // ==========================================
    // Итерация 15.3 (fix): маршруты для шагов
    // ==========================================
    /**
     * Возвращает URL, на который нужно перейти перед показом
     * шага stepIndex тура tourId.
     *
     * Если для шага маршрут не задан — возвращает null
     * (значит, остаёмся на текущей странице).
     */
    const getRouteForStep = useCallback(
        (tourId: string, stepIndex: number): string | null => {
            const tour = getTourById(tourId);
            if (!tour || !tour.stepRoutes) return null;
            return tour.stepRoutes[stepIndex] ?? null;
        },
        [],
    );

    const value = useMemo<TutorialContextType>(
        () => ({
            activeTour,
            currentStepIndex,
            startTour,
            stopTour,
            nextStep,
            prevStep,
            goToStep,
            isTourCompleted,
            resetTourProgress,
            getRouteForStep,
        }),
        [
            activeTour,
            currentStepIndex,
            startTour,
            stopTour,
            nextStep,
            prevStep,
            goToStep,
            isTourCompleted,
            resetTourProgress,
            getRouteForStep,
        ],
    );

    return (
        <TutorialContext.Provider value={value}>
            {children}
        </TutorialContext.Provider>
    );
};

export const useTutorial = (): TutorialContextType => {
    const ctx = useContext(TutorialContext);
    if (!ctx) {
        throw new Error('useTutorial must be used within TutorialProvider');
    }
    return ctx;
};