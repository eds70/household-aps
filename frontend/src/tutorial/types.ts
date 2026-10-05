// frontend/src/tutorial/types.ts
/**
 * Типы для интерактивных туров (Итерация 15.3).
 *
 * Используется вместе с react-joyride@3.2.0.
 * Тип `Step` импортируется из пакета и реэкспортируется
 * через Tour.steps — так что при смене версии библиотеки
 * достаточно поменять один импорт.
 */
import type {Step} from 'react-joyride';

/**
 * Один тур (последовательность шагов).
 */
export interface Tour {
    /** Уникальный ID тура (используется в localStorage). */
    id: string;

    /** Человекочитаемое название. */
    name: string;

    /** Краткое описание тура. */
    description: string;

    /** Массив шагов react-joyride. */
    steps: Step[];

    /**
     * Иконка (ключ из TOUR_ICONS в HelpPage).
     * Используется на HelpPage для карточки тура.
     */
    icon?: string;

    /**
     * Итерация 15.3 (fix): карта «индекс шага → URL».
     *
     * Если для шага указан URL, перед его показом
     * TutorialRunner перейдёт на этот URL через react-router.
     * Это нужно, потому что react-joyride не умеет
     * навигировать между страницами самостоятельно.
     *
     * Пример:
     *   stepRoutes: {
     *     6: '/schedule',  // шаг «Планирование» → страница /schedule
     *     1: '/gantt',     // шаг «Тулбар» → страница /gantt
     *   }
     */
    stepRoutes?: Record<number, string>;
}

/**
 * Состояние контекста туториала.
 */
export interface TutorialContextType {
    /** Запущенный тур (null, если ничего не запущено). */
    activeTour: Tour | null;

    /** Номер текущего шага (0-based). */
    currentStepIndex: number;

    /** Запустить тур по ID. */
    startTour: (tourId: string) => void;

    /** Остановить текущий тур. */
    stopTour: () => void;

    /** Перейти к следующему шагу. */
    nextStep: () => void;

    /** Перейти к предыдущему шагу. */
    prevStep: () => void;

    /** Перейти к шагу по индексу. */
    goToStep: (index: number) => void;

    /** Проверить, пройден ли тур. */
    isTourCompleted: (tourId: string) => boolean;

    /** Сбросить прогресс тура. */
    resetTourProgress: (tourId: string) => void;

    /**
     * Итерация 15.3 (fix): получить URL, на который нужно
     * перейти перед показом шага stepIndex тура tourId.
     * Возвращает null, если для шага маршрут не задан.
     */
    getRouteForStep: (tourId: string, stepIndex: number) => string | null;
}