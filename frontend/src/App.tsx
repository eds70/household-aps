// frontend/src/App.tsx
import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { AuthProvider, useAuth } from './context/AuthContext';
import { PlanProvider } from './context/PlainContext';
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
import { CircularProgress, Box } from '@mui/material';

const theme = createTheme({
  palette: {
    primary: { main: '#2c3e50' },
    secondary: { main: '#3498db' },
  },
});

// Компонент-обёртка для защиты маршрутов
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

// Компонент-обёртка для публичных маршрутов (редирект если уже залогинен)
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
        {/* Публичный маршрут — логин */}
        <Route
            path="/login"
            element={
              <PublicRoute>
                <LoginPage />
              </PublicRoute>
            }
        />

        {/* Защищённые маршруты */}
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
        </Route>

        {/* Fallback */}
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