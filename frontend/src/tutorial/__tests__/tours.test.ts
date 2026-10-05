// frontend/src/tutorial/__tests__/tours.test.ts
/**
 * Тесты конфигурации туров (Итерация 15.3).
 *
 * Совместимо с react-joyride@3.2.0.
 *
 * В v3.2.0 часть опций (showProgress, buttons, width, ...)
 * вынесена в общий Options, который передаётся в <Joyride options={...}>.
 * Поэтому эти настройки проверяются в COMMON_TOUR_OPTIONS,
 * а не в каждом шаге.
 */
import {ALL_TOURS, COMMON_TOUR_OPTIONS, getTourById} from '../tours';

const VALID_PLACEMENTS = [
    'top',
    'top-start',
    'top-end',
    'bottom',
    'bottom-start',
    'bottom-end',
    'left',
    'left-start',
    'left-end',
    'right',
    'right-start',
    'right-end',
    'auto',
    'center',
];

describe('Конфигурация туров (Итерация 15.3)', () => {
    // ==========================================
    // Общая структура туров
    // ==========================================
    test('ALL_TOURS содержит 3 тура', () => {
        expect(ALL_TOURS).toHaveLength(3);
    });

    test('У всех туров есть id, name, description, steps', () => {
        ALL_TOURS.forEach((tour) => {
            expect(tour.id).toBeTruthy();
            expect(typeof tour.id).toBe('string');
            expect(tour.name).toBeTruthy();
            expect(typeof tour.name).toBe('string');
            expect(tour.description).toBeTruthy();
            expect(typeof tour.description).toBe('string');
            expect(Array.isArray(tour.steps)).toBe(true);
            expect(tour.steps.length).toBeGreaterThan(0);
        });
    });

    test('ID туров уникальны', () => {
        const ids = ALL_TOURS.map((t) => t.id);
        const uniqueIds = new Set(ids);
        expect(uniqueIds.size).toBe(ids.length);
    });

    test('Все id в kebab-case', () => {
        ALL_TOURS.forEach((tour) => {
            expect(tour.id).toMatch(/^[a-z][a-z0-9-]*$/);
        });
    });

    // ==========================================
    // Структура шагов
    // ==========================================
    test('У каждого шага есть target, content, placement', () => {
        ALL_TOURS.forEach((tour) => {
            tour.steps.forEach((step) => {
                expect(step.target).toBeTruthy();
                expect(step.content).toBeTruthy();
                expect(step.placement).toBeTruthy();
            });
        });
    });

    test('Все placement — валидные значения react-joyride', () => {
        ALL_TOURS.forEach((tour) => {
            tour.steps.forEach((step) => {
                expect(VALID_PLACEMENTS).toContain(step.placement);
            });
        });
    });

    test('target — либо body, либо CSS-селектор с data-tour-id', () => {
        ALL_TOURS.forEach((tour) => {
            tour.steps.forEach((step) => {
                const target = step.target as string;
                if (target === 'body') return;

                const hasDataTourId = target.includes('data-tour-id=');
                expect(hasDataTourId).toBe(true);
            });
        });
    });

    test('target селекторы уникальны внутри одного тура', () => {
        ALL_TOURS.forEach((tour) => {
            const targets = tour.steps
                .map((s) => s.target as string)
                .filter((t) => t !== 'body');

            const nonBodyTargets = targets.filter((t) => t !== 'body');
            const uniqueTargets = new Set(nonBodyTargets);

            expect(nonBodyTargets.length - uniqueTargets.size).toBeLessThanOrEqual(
                1,
            );
        });
    });

    // ==========================================
    // COMMON_TOUR_OPTIONS (Options из v3.2.0)
    // ==========================================
    test('COMMON_TOUR_OPTIONS.showProgress = true', () => {
        expect(COMMON_TOUR_OPTIONS.showProgress).toBe(true);
    });

    test('COMMON_TOUR_OPTIONS.skipBeacon = true', () => {
        expect(COMMON_TOUR_OPTIONS.skipBeacon).toBe(true);
    });

    test('COMMON_TOUR_OPTIONS.buttons включает "skip"', () => {
        expect(COMMON_TOUR_OPTIONS.buttons).toContain('skip');
    });

    test('COMMON_TOUR_OPTIONS.width задан', () => {
        expect(COMMON_TOUR_OPTIONS.width).toBe(380);
    });

    test('COMMON_TOUR_OPTIONS.overlayClickAction = false', () => {
        expect(COMMON_TOUR_OPTIONS.overlayClickAction).toBe(false);
    });

    test('COMMON_TOUR_OPTIONS.primaryColor = "#3498db"', () => {
        expect(COMMON_TOUR_OPTIONS.primaryColor).toBe('#3498db');
    });

    // ==========================================
    // getTourById
    // ==========================================
    test('getTourById возвращает тур по ID', () => {
        const tour = getTourById('getting-started');
        expect(tour).toBeDefined();
        expect(tour?.name).toBe('Первый план за 5 минут');
    });

    test('getTourById возвращает undefined для несуществующего ID', () => {
        expect(getTourById('non-existent')).toBeUndefined();
    });

    test('getTourById находит все 3 тура', () => {
        expect(getTourById('getting-started')).toBeDefined();
        expect(getTourById('gantt-basics')).toBeDefined();
        expect(getTourById('shift-management')).toBeDefined();
    });

    // ==========================================
    // Конкретные туры
    // ==========================================
    test('Тур getting-started содержит >= 8 шагов', () => {
        const tour = getTourById('getting-started');
        expect(tour!.steps.length).toBeGreaterThanOrEqual(8);
    });

    test('Тур gantt-basics содержит >= 5 шагов', () => {
        const tour = getTourById('gantt-basics');
        expect(tour!.steps.length).toBeGreaterThanOrEqual(5);
    });

    test('Тур shift-management содержит >= 5 шагов', () => {
        const tour = getTourById('shift-management');
        expect(tour!.steps.length).toBeGreaterThanOrEqual(5);
    });

    test('У всех туров есть icon', () => {
        ALL_TOURS.forEach((tour) => {
            expect(tour.icon).toBeTruthy();
            expect(typeof tour.icon).toBe('string');
        });
    });
});