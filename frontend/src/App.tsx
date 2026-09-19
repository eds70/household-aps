// frontend/src/App.tsx
import React from 'react';
import {BrowserRouter, Navigate, Route, Routes} from 'react-router-dom';
import {createTheme, ThemeProvider} from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import {AuthProvider, useAuth} from './context/AuthContext';
import {PlanProvider} from './context/PlainContext';
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
import {Box, CircularProgress} from '@mui/material';
import SettingsPage from "./pages/SettingsPage.tsx";

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
                <Route path="settings" element={<SettingsPage />} />
            </Route>

            <Route path="*" element={<Navigate to="/equipment" replace />} />
        </Routes>
    );
};

const App: React.FC = () => {
    return (
        <ThemeProvider theme={theme}>
            <CssBaseline />
            <AuthProvider>
                <PlanProvider>
                    <BrowserRouter>
                        <AppRoutes />
                    </BrowserRouter>
                </PlanProvider>
            </AuthProvider>
        </ThemeProvider>
    );
};

export default App;