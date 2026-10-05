// frontend/src/context/__tests__/TutorialContext.test.tsx
/**
 * Тесты контекста туториала (Итерация 15.3).
 *
 * ВАЖНО: каждый setState-вызов обёрнут в отдельный `act()`.
 * React 18/19 батчит обновления внутри одного `act()`,
 * из-за чего цепочка `startTour() → nextStep() → nextStep()`
 * в одном `act()` не сработала бы (nextStep видит старый activeTour).
 */
import {act, renderHook} from '@testing-library/react';
import {TutorialProvider, useTutorial} from '../../context/TutorialContext.tsx';
import React from 'react';

const wrapper: React.FC<{ children: React.ReactNode }> = ({children}) => (
    <TutorialProvider>{children}</TutorialProvider>
);

describe('TutorialContext', () => {
    beforeEach(() => {
        localStorage.clear();
    });

    // ==========================================
    // Инициализация
    // ==========================================
    test('инициализируется с activeTour = null', () => {
        const {result} = renderHook(() => useTutorial(), {wrapper});
        expect(result.current.activeTour).toBeNull();
        expect(result.current.currentStepIndex).toBe(0);
    });

    test('isTourCompleted возвращает false для нового тура', () => {
        const {result} = renderHook(() => useTutorial(), {wrapper});
        expect(result.current.isTourCompleted('getting-started')).toBe(false);
    });

    // ==========================================
    // startTour / stopTour
    // ==========================================
    test('startTour запускает тур по ID', () => {
        const {result} = renderHook(() => useTutorial(), {wrapper});

        act(() => {
            result.current.startTour('getting-started');
        });

        expect(result.current.activeTour).not.toBeNull();
        expect(result.current.activeTour?.id).toBe('getting-started');
        expect(result.current.currentStepIndex).toBe(0);
    });

    test('startTour с несуществующим ID не запускает тур', () => {
        const {result} = renderHook(() => useTutorial(), {wrapper});

        act(() => {
            result.current.startTour('non-existent-tour');
        });

        expect(result.current.activeTour).toBeNull();
    });

    test('stopTour останавливает тур и сбрасывает шаг', () => {
        const {result} = renderHook(() => useTutorial(), {wrapper});

        act(() => {
            result.current.startTour('getting-started');
        });
        expect(result.current.activeTour).not.toBeNull();

        act(() => {
            result.current.stopTour();
        });

        expect(result.current.activeTour).toBeNull();
        expect(result.current.currentStepIndex).toBe(0);
    });

    // ==========================================
    // Навигация по шагам
    // ==========================================
    test('nextStep увеличивает индекс шага', () => {
        const {result} = renderHook(() => useTutorial(), {wrapper});

        act(() => {
            result.current.startTour('getting-started');
        });

        act(() => {
            result.current.nextStep();
        });
        expect(result.current.currentStepIndex).toBe(1);

        act(() => {
            result.current.nextStep();
        });
        expect(result.current.currentStepIndex).toBe(2);
    });

    test('nextStep не выходит за пределы последнего шага', () => {
        const {result} = renderHook(() => useTutorial(), {wrapper});

        act(() => {
            result.current.startTour('getting-started');
        });

        const lastIndex = result.current.activeTour!.steps.length - 1;

        for (let i = 0; i < lastIndex + 5; i++) {
            act(() => {
                result.current.nextStep();
            });
        }

        expect(result.current.currentStepIndex).toBe(lastIndex);
    });

    test('prevStep уменьшает индекс шага', () => {
        const {result} = renderHook(() => useTutorial(), {wrapper});

        act(() => {
            result.current.startTour('getting-started');
        });

        act(() => {
            result.current.nextStep();
        });

        act(() => {
            result.current.nextStep();
        });

        expect(result.current.currentStepIndex).toBe(2);

        act(() => {
            result.current.prevStep();
        });

        expect(result.current.currentStepIndex).toBe(1);
    });

    test('prevStep не уходит ниже 0', () => {
        const {result} = renderHook(() => useTutorial(), {wrapper});

        act(() => {
            result.current.startTour('getting-started');
        });

        act(() => {
            result.current.prevStep();
        });
        expect(result.current.currentStepIndex).toBe(0);
    });

    test('goToStep переходит на конкретный шаг', () => {
        const {result} = renderHook(() => useTutorial(), {wrapper});

        act(() => {
            result.current.startTour('getting-started');
        });

        act(() => {
            result.current.goToStep(5);
        });
        expect(result.current.currentStepIndex).toBe(5);
    });

    test('goToStep ограничивает индекс допустимым диапазоном', () => {
        const {result} = renderHook(() => useTutorial(), {wrapper});

        act(() => {
            result.current.startTour('getting-started');
        });

        const lastIndex = result.current.activeTour!.steps.length - 1;

        act(() => {
            result.current.goToStep(999);
        });
        expect(result.current.currentStepIndex).toBe(lastIndex);

        act(() => {
            result.current.goToStep(-5);
        });
        expect(result.current.currentStepIndex).toBe(0);
    });

    // ==========================================
    // Прогресс и localStorage
    // ==========================================
    test('stopTour на последнем шаге сохраняет прогресс', () => {
        const {result} = renderHook(() => useTutorial(), {wrapper});

        act(() => {
            result.current.startTour('getting-started');
        });
        const lastIndex = result.current.activeTour!.steps.length - 1;

        act(() => {
            result.current.goToStep(lastIndex);
        });

        act(() => {
            result.current.stopTour();
        });

        expect(result.current.isTourCompleted('getting-started')).toBe(true);
        expect(
            localStorage.getItem('aps_tutorial_completed_getting-started'),
        ).toBe('1');
    });

    test('stopTour на промежуточном шаге НЕ сохраняет прогресс', () => {
        const {result} = renderHook(() => useTutorial(), {wrapper});

        act(() => {
            result.current.startTour('getting-started');
        });

        act(() => {
            result.current.goToStep(2);
        });

        act(() => {
            result.current.stopTour();
        });

        expect(result.current.isTourCompleted('getting-started')).toBe(false);
        expect(
            localStorage.getItem('aps_tutorial_completed_getting-started'),
        ).toBeNull();
    });

    test('resetTourProgress очищает прогресс', () => {
        const {result} = renderHook(() => useTutorial(), {wrapper});

        // Сначала проходим тур
        act(() => {
            result.current.startTour('getting-started');
        });

        act(() => {
            result.current.goToStep(result.current.activeTour!.steps.length - 1);
        });

        act(() => {
            result.current.stopTour();
        });

        expect(result.current.isTourCompleted('getting-started')).toBe(true);

        // Теперь сбрасываем
        act(() => {
            result.current.resetTourProgress('getting-started');
        });

        expect(result.current.isTourCompleted('getting-started')).toBe(false);
        expect(
            localStorage.getItem('aps_tutorial_completed_getting-started'),
        ).toBeNull();
    });

    test('прогресс разных туров хранится независимо', () => {
        const {result} = renderHook(() => useTutorial(), {wrapper});

        // Проходим getting-started
        act(() => {
            result.current.startTour('getting-started');
        });

        act(() => {
            result.current.goToStep(result.current.activeTour!.steps.length - 1);
        });

        act(() => {
            result.current.stopTour();
        });

        expect(result.current.isTourCompleted('getting-started')).toBe(true);
        expect(result.current.isTourCompleted('gantt-basics')).toBe(false);
    });
});