// frontend/src/context/AuthContext.tsx
import React, {createContext, useCallback, useContext, useEffect, useState} from 'react';
import api from '../services/api';

export interface UserData {
    id: string;
    email: string;
    full_name?: string;
    role: string;
    organization_id: string;
    is_active: boolean;
    last_login_at?: string;
}

interface AuthContextType {
    user: UserData | null;
    token: string | null;
    isAuthenticated: boolean;
    isLoading: boolean;
    login: (email: string, password: string) => Promise<void>;
    logout: () => void;
    refreshUser: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined);

/**
 * Итерация 17.x: нормализует `detail` из ответа backend в строку.
 *
 * Backend возвращает `detail` в двух форматах:
 *   1. Строка — обычные HTTPException(detail="...").
 *   2. Объект  — LicenseMiddleware / require_feature:
 *                {"code": "LICENSE_INVALID", "message": "..."}
 *
 * До этого патча `err.response?.data?.detail` мог попасть в
 * `new Error(detail)`, и дальше — в UI — рендерился объект.
 * React падал с "Objects are not valid as a React child".
 *
 * Примечание: интерцептор в `services/api.ts` уже нормализует
 * `detail` в строку, но подстраховываемся здесь на случай, если
 * интерцептор будет снят или сработает до него.
 */
function normalizeDetail(raw: unknown, fallback: string): string {
    if (typeof raw === 'string' && raw) return raw;
    if (raw && typeof raw === 'object' && 'message' in raw) {
        const msg = (raw as { message?: unknown }).message;
        if (typeof msg === 'string' && msg) return msg;
    }
    return fallback;
}

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [user, setUser] = useState<UserData | null>(null);
    const [token, setToken] = useState<string | null>(() => localStorage.getItem('access_token'));
    const [isLoading, setIsLoading] = useState(true);

    // ==========================================
    // Итерация 17.x: убран глобальный axios.defaults.
    //
    // Раньше здесь был useEffect, который писал
    //   axios.defaults.headers.common['Authorization'] = `Bearer ${token}`.
    //
    // Это работало на ГЛОБАЛЬНОМ axios и не влияло на инстанс `api`
    // из services/api.ts. Теперь мы везде ходим через `api`, а он
    // сам подставляет заголовок из localStorage через request-интерцептор.
    // Поэтому этот useEffect больше не нужен.
    // ==========================================

    // Загрузка данных пользователя при монтировании
    const refreshUser = useCallback(async () => {
        if (!token) {
            setUser(null);
            setIsLoading(false);
            return;
        }

        try {
            const response = await api.get('/api/v1/auth/me');
            setUser(response.data);
        } catch (err) {
            console.error('Ошибка загрузки данных пользователя:', err);
            localStorage.removeItem('access_token');
            setToken(null);
            setUser(null);
        } finally {
            setIsLoading(false);
        }
    }, [token]);

    useEffect(() => {
        refreshUser();
    }, [refreshUser]);

    const login = async (email: string, password: string) => {
        try {
            const response = await api.post('/api/v1/auth/login', {
                email,
                password,
            });

            const { access_token } = response.data;
            localStorage.setItem('access_token', access_token);
            setToken(access_token);

            await refreshUser();
        } catch (err: any) {
            const message = normalizeDetail(
                err.response?.data?.detail,
                'Ошибка авторизации',
            );
            throw new Error(message);
        }
    };

    const logout = () => {
        localStorage.removeItem('access_token');
        setToken(null);
        setUser(null);
        // Глобальный axios.defaults больше не используется —
        // чистить нечего, `api` берёт токен из localStorage при каждом запросе.
    };

    return (
        <AuthContext.Provider
            value={{
                user,
                token,
                isAuthenticated: !!user,
                isLoading,
                login,
                logout,
                refreshUser,
            }}
        >
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error('useAuth must be used within AuthProvider');
    }
    return context;
};