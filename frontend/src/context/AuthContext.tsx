// frontend/src/context/AuthContext.tsx
import React, { createContext, useState, useEffect, useContext, useCallback } from 'react';
import axios from 'axios';
import { API_BASE_URL } from '../config';

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

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [user, setUser] = useState<UserData | null>(null);
    const [token, setToken] = useState<string | null>(() => localStorage.getItem('access_token'));
    const [isLoading, setIsLoading] = useState(true);

    // Настройка axios для отправки токена во всех запросах
    useEffect(() => {
        if (token) {
            axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
        } else {
            delete axios.defaults.headers.common['Authorization'];
        }
    }, [token]);

    // Загрузка данных пользователя при монтировании
    const refreshUser = useCallback(async () => {
        if (!token) {
            setUser(null);
            setIsLoading(false);
            return;
        }

        try {
            const response = await axios.get(`${API_BASE_URL}/api/v1/auth/me`);
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
            const response = await axios.post(`${API_BASE_URL}/api/v1/auth/login`, {
                email,
                password,
            });

            const { access_token } = response.data;
            localStorage.setItem('access_token', access_token);
            setToken(access_token);

            await refreshUser();
        } catch (err: any) {
            const message = err.response?.data?.detail || 'Ошибка авторизации';
            throw new Error(message);
        }
    };

    const logout = () => {
        localStorage.removeItem('access_token');
        setToken(null);
        setUser(null);
        delete axios.defaults.headers.common['Authorization'];
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