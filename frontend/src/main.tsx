// frontend/src/main.tsx
import {StrictMode} from 'react'
import {createRoot} from 'react-dom/client'
import {AllCommunityModule, ModuleRegistry, ValidationModule,} from 'ag-grid-community'
import './index.css'
import App from './App.tsx'

// ==========================================
// AG Grid — регистрация модулей
// ==========================================
// ValidationModule оставляем — полезен для отладки конфигураций Grid.
//
// ⚠️ Итерация 14.0: CSS-импорты AG Grid УБРАНЫ
//    (ag-grid.css, ag-theme-alpine.css). Теперь используется
//    Theming API (см. src/theme/agGridTheme.ts).
//    Больше нет необходимости подавлять warning #239.
// ==========================================
ModuleRegistry.registerModules([
    AllCommunityModule,
    ValidationModule,
])

createRoot(document.getElementById('root')!).render(
    <StrictMode>
        <App/>
    </StrictMode>,
)