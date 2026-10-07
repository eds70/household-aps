// frontend/src/config.ts

export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const PAGINATION_PAGE_SIZE = 20;

/**
 * Название приложения.
 * Используется в document.title (App.tsx) и в UI (header, help).
 */
export const APP_NAME = 'APS Production Scheduler';