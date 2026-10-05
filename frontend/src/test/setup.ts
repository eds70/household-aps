// frontend/src/test/setup.ts
/**
 * Настройка окружения тестов (Итерация 15.3).
 *
 * Подключает матчеры @testing-library/jest-dom,
 * которые расширяют стандартные expect() (toBeInTheDocument, toHaveTextContent и т.п.).
 *
 * Также очищает localStorage перед каждым тестом — чтобы прогресс туров
 * не протекал между тестами.
 */
import '@testing-library/jest-dom/vitest';
import {afterEach, beforeEach} from 'vitest';

// Очистка localStorage перед каждым тестом
beforeEach(() => {
    try {
        localStorage.clear();
    } catch {
        // ignore
    }
});

afterEach(() => {
    try {
        localStorage.clear();
    } catch {
        // ignore
    }
});