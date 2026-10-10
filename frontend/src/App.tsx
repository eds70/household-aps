// frontend/src/App.tsx
import React, {useEffect, useMemo} from 'react';
import {BrowserRouter, Navigate, Route, Routes, useNavigate} from 'react-router-dom';
import {createTheme, ThemeProvider} from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import {Joyride} from 'react-joyride';
import {AuthProvider, useAuth} from './context/AuthContext';
import {PlanProvider} from './context/PlainContext';
import {HelpHintsProvider} from './context/HelpHintsContext';
import {TutorialProvider, useTutorial} from './context/TutorialContext';
import MainLayout from './components/layout/MainLayout';
import LoginPage from './pages/LoginPage';
import EquipmentPage from './pages/EquipmentPage';
import ProductsPage from './pages/ProductsPage';
import MaterialsPage from './pages/MaterialsPage';
import RecipesPage from './pages/RecipesPage';
import OperationsPage from './pages/OperationsPage';
import OrdersPage from './pages/OrdersPage';
import SchedulePage from './pages/SchedulePage';
import GanttPage from './pages/GanttPage';
import ShiftPage from './pages/ShiftPage';
import PersonnelPage from './pages/PersonnelPage';
import CzPage from './pages/CzPage';
import SettingsPage from './pages/SettingsPage';
import WhatIfPage from './pages/WhatIfPage';
import AuditPage from './pages/AuditPage';
import HelpPage from './pages/HelpPage';
import LicensePage from './pages/LicensePage'; // ← НОВОЕ
import {Box, CircularProgress} from '@mui/material';
import {COMMON_TOUR_OPTIONS} from './tutorial/tours';
import {APP_NAME} from './config';

const theme = createTheme({
    palette: {
        primary: { main: '#2c3e50' },
        secondary: { main: '#3498db' },
    },
});

const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const { isAuthenticated, isLoading } = useAuth();

    if (isLoading) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh' }}>
                <CircularProgress />
            </Box>
        );
    }

    if (!isAuthenticated) {
        return <Navigate to="/login" replace />;
    }

    return <>{children}</>;
};

const PublicRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const { isAuthenticated, isLoading } = useAuth();

    if (isLoading) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh' }}>
                <CircularProgress />
            </Box>
        );
    }

    if (isAuthenticated) {
        return <Navigate to="/equipment" replace />;
    }

    return <>{children}</>;
};

// ==========================================
// ИТЕРАЦИЯ 15.3 (fix): TutorialRunner с навигацией
// ==========================================
// API react-joyride@3.2.0:
//   - <Joyride> принимает prop `options: Partial<Options>`
//     с общими настройками для всех шагов (showProgress, buttons,
//     width, overlayClickAction, ...).
//   - prop `onEvent` вместо `callback` из v2.
//   - Стили (Styles) — плоские ключи без options-обёртки.
//   - Кнопка «Далее» — `styles.buttonPrimary` (не buttonNext).
//   - Затемнение — `styles.overlay.backgroundColor`.
//
// Итерация 15.3 (fix): добавлен `before`-колбэк на каждом шаге.
// Он вызывается react-joyride ПЕРЕД показом шага. Если для шага
// задан маршрут (tour.stepRoutes[stepIndex]) — переходим на него
// через useNavigate и ждём 400 мс, чтобы страница успела
// отрендериться. Без этого тур «застревает» на шаге, где target
// находится на другой странице.
//
// ВАЖНО: мы НЕ используем currentStepIndex — react-joyride сам
// управляет шагами (uncontrolled mode). stepIndex не передаём,
// nextStep/prevStep/goToStep не вызываем. Только stopTour по
// событиям finished/skipped/close.
//
// TutorialRunner ДОЛЖЕН быть внутри <BrowserRouter>, потому что
// использует useNavigate().

const TutorialRunner: React.FC = () => {
    const {activeTour, stopTour, getRouteForStep} = useTutorial();
    const navigate = useNavigate();

    // Строим steps с динамическим `before` для каждого шага.
    // useMemo — чтобы не пересоздавать массив на каждый рендер
    // (react-joyride это чувствительно).
    const steps = useMemo(() => {
        if (!activeTour) return [];

        return activeTour.steps.map((step, index) => ({
            ...step,
            before: (): Promise<void> => {
                const route = getRouteForStep(activeTour.id, index);
                if (route && window.location.pathname !== route) {
                    console.log(
                        `[Tutorial] Навигация перед шагом ${index}: ` +
                        `${window.location.pathname} → ${route}`,
                    );
                    navigate(route);
                    // Ждём, пока React Router отрендерит новую страницу
                    // и её useEffect'ы отработают (загрузка данных).
                    return new Promise<void>((resolve) => {
                        setTimeout(() => resolve(), 400);
                    });
                }
                return Promise.resolve();
            },
        }));
    }, [activeTour, getRouteForStep, navigate]);

    if (!activeTour) return null;

    return (
        <Joyride
            steps={steps}
            run={true}
            continuous
            scrollToFirstStep
            options={COMMON_TOUR_OPTIONS}
            onEvent={(data) => {
                const {action, status, type} = data;

                // Тур завершён / пропущен / закрыт — останавливаем
                if (
                    status === 'finished' ||
                    status === 'skipped' ||
                    type === 'tour:end'
                ) {
                    stopTour();
                    return;
                }

                if (action === 'close') {
                    stopTour();
                    return;
                }
            }}
            styles={{
                // ==========================================
                // v3.2.0: плоская структура Styles
                // ==========================================
                tooltip: {
                    borderRadius: 8,
                    padding: 16,
                    backgroundColor: '#ffffff',
                    color: '#2c3e50',
                    boxShadow: '0 8px 24px rgba(0,0,0,0.25)',
                },
                tooltipTitle: {
                    fontSize: '1rem',
                    fontWeight: 700,
                    marginBottom: 8,
                    color: '#2c3e50',
                },
                tooltipContent: {
                    fontSize: '0.875rem',
                    lineHeight: 1.6,
                    padding: '4px 0',
                    color: '#2c3e50',
                },
                buttonPrimary: {
                    backgroundColor: '#3498db',
                    color: '#ffffff',
                    borderRadius: 6,
                    fontSize: '0.85rem',
                    padding: '8px 16px',
                    fontWeight: 600,
                    border: 'none',
                    cursor: 'pointer',
                },
                buttonBack: {
                    color: '#7f8c8d',
                    fontSize: '0.85rem',
                    marginRight: 8,
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                },
                buttonSkip: {
                    color: '#e67e22',
                    fontSize: '0.8rem',
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                },
                buttonClose: {
                    color: '#7f8c8d',
                },
                overlay: {
                    backgroundColor: 'rgba(0, 0, 0, 0.55)',
                },
                floater: {
                    zIndex: 10000,
                },
            }}
            locale={{
                back: 'Назад',
                close: 'Закрыть',
                last: 'Завершить',
                next: 'Далее',
                skip: 'Пропустить',
            }}
        />
    );
};

// ==========================================
// AppRoutes
// ==========================================

const AppRoutes: React.FC = () => {
    return (
        <Routes>
            <Route
                path="/login"
                element={
                    <PublicRoute>
                        <LoginPage />
                    </PublicRoute>
                }
            />

            <Route
                path="/"
                element={
                    <ProtectedRoute>
                        <MainLayout />
                    </ProtectedRoute>
                }
            >
                <Route index element={<Navigate to="/equipment" replace />} />
                <Route path="equipment" element={<EquipmentPage />} />
                <Route path="products" element={<ProductsPage />} />
                <Route path="materials" element={<MaterialsPage />} />
                <Route path="recipes" element={<RecipesPage />} />
                <Route path="operations" element={<OperationsPage />} />
                <Route path="orders" element={<OrdersPage />} />
                <Route path="schedule" element={<SchedulePage />} />
                <Route path="gantt" element={<GanttPage />} />
                <Route path="shift" element={<ShiftPage />} />
                <Route path="personnel" element={<PersonnelPage />} />
                <Route path="cz" element={<CzPage />} />
                <Route path="whatif" element={<WhatIfPage />} />
                {/* Итерация 16.0: возврат страницы аудита в UI */}
                <Route path="audit" element={<AuditPage />} />
                <Route path="settings" element={<SettingsPage />} />
                <Route path="help" element={<HelpPage />} />
                <Route path="help/:slug" element={<HelpPage />} />
                {/* Итерация 17.1: страница лицензии */}
                <Route path="license" element={<LicensePage />} />
            </Route>

            <Route path="*" element={<Navigate to="/equipment" replace />} />
        </Routes>
    );
};

// ==========================================
// App
// ==========================================

const App: React.FC = () => {
    // Итерация 16.x: устанавливаем title вкладки браузера.
    // Значение берётся из config.ts (APP_NAME) — единый источник правды.
    useEffect(() => {
        document.title = APP_NAME;
    }, []);

    return (
        <ThemeProvider theme={theme}>
            <CssBaseline />
            <AuthProvider>
                <PlanProvider>
                    {/* Итерация 15.2: глобальный кэш контекстных подсказок */}
                    <HelpHintsProvider>
                        {/* Итерация 15.3: провайдер интерактивных туров */}
                        <TutorialProvider>
                            <BrowserRouter>
                                {/* Итерация 15.3: рендер react-joyride
                                    поверх всего приложения, если
                                    активен тур.
                                    TutorialRunner использует useNavigate,
                                    поэтому он ДОЛЖЕН быть внутри
                                    BrowserRouter. */}
                                <TutorialRunner />
                                <AppRoutes />
                            </BrowserRouter>
                        </TutorialProvider>
                    </HelpHintsProvider>
                </PlanProvider>
            </AuthProvider>
        </ThemeProvider>
    );
};

export default App;