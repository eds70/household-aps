// frontend/src/theme/agGridTheme.ts
/**
 * Единая тема AG Grid для всего приложения.
 *
 * Итерация 14.0: миграция с legacy CSS-тем (ag-theme-alpine)
 * на Theming API (AG Grid 33+). Это убирает warning #239
 * и даёт TypeScript-валидацию параметров темы.
 *
 * Основа — themeAlpine (визуально максимально близко к прежней
 * ag-theme-alpine). Параметры подобраны под текущий дизайн APS:
 *   - тёмно-синий header (#2c3e50),
 *   - белый фон,
 *   - стандартные размеры и отступы.
 *
 * Параметры можно менять централизованно — все Grid'ы подхватят.
 * Полный список параметров: https://www.ag-grid.com/react-data-grid/theming-parameters/
 */
import {type Theme, themeAlpine} from 'ag-grid-community';

export const agGridTheme: Theme = themeAlpine.withParams({
    // ==========================================
    // Ключевые цвета (под текущий дизайн APS)
    // ==========================================
    backgroundColor: '#ffffff',
    foregroundColor: '#2c3e50',

    // Header: тёмно-синий фон, белый текст (как было в ag-theme-alpine
    // с MUI-темой primary #2c3e50)
    headerBackgroundColor: '#2c3e50',
    headerTextColor: '#ffffff',

    // Акцентный цвет (выделение, фокус, чипы «активный»)
    accentColor: '#3498db',

    // Границы
    borderColor: '#e0e0e0',

    // Вертикальные границы между колонками.
    columnBorder: {
        style: 'solid',
        width: 1,
    },

    // Горизонтальные границы между строками.
    rowBorder: {
        style: 'solid',
        width: 1,
    },

    // Границы вокруг header-ячеек.
    headerColumnBorder: {
        color: '#1a252f',           // чуть темнее header'а
        style: 'solid',
        width: 1,
    },
    headerRowBorder: {
        color: '#1a252f',
        style: 'solid',
        width: 1,
    },

    // ==========================================
    // Размеры (под текущую плотность)
    // ==========================================
    // spacing — это padding вокруг элементов (не путать со старым grid-size)
    spacing: 8,
    fontSize: 14,
    fontFamily: [
        '-apple-system',
        'BlinkMacSystemFont',
        '"Segoe UI"',
        'Roboto',
        'sans-serif',
    ].join(', '),

    // Высота строки
    rowHeight: 42,
    headerHeight: 44,
});

export default agGridTheme;