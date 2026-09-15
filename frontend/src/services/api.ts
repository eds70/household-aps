// frontend/src/services/api.ts
import axios from 'axios';
import { API_BASE_URL } from '../config';

const api = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

// ==========================================
// Интерсептор запросов — добавление токена
// ==========================================
api.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem('access_token');
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
    },
    (error) => Promise.reject(error)
);

// ==========================================
// Интерсептор ответов — обработка 401
// ==========================================
api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401) {
            localStorage.removeItem('access_token');
            if (!window.location.pathname.includes('/login')) {
                window.location.href = '/login';
            }
        }
        return Promise.reject(error);
    }
);

// ==========================================
// Auth API
// ==========================================
export const authApi = {
    login: async (email: string, password: string) => {
        const response = await api.post('/api/v1/auth/login', { email, password });
        return response.data;
    },
    me: async () => {
        const response = await api.get('/api/v1/auth/me');
        return response.data;
    },
    changePassword: async (old_password: string, new_password: string) => {
        const response = await api.post('/api/v1/auth/change-password', {
            old_password,
            new_password,
        });
        return response.data;
    },
};

// ==========================================
// Equipment API
// ==========================================
export const equipmentApi = {
    getAll: async (versionId?: string) => {
        const params = versionId ? { version_id: versionId } : {};
        const response = await api.get('/api/v1/equipment', { params });
        return response.data;
    },
    create: async (data: any) => {
        const response = await api.post('/api/v1/equipment', data);
        return response.data;
    },
    update: async (id: string, data: any) => {
        const response = await api.put(`/api/v1/equipment/${id}`, data);
        return response.data;
    },
    delete: async (id: string) => {
        const response = await api.delete(`/api/v1/equipment/${id}`);
        return response.data;
    },
};

// ==========================================
// Products API
// ==========================================
export const productsApi = {
    getAll: async (versionId?: string) => {
        const params = versionId ? { version_id: versionId } : {};
        const response = await api.get('/api/v1/products', { params });
        return response.data;
    },
    create: async (data: any) => {
        const response = await api.post('/api/v1/products', data);
        return response.data;
    },
    update: async (id: string, data: any) => {
        const response = await api.put(`/api/v1/products/${id}`, data);
        return response.data;
    },
    delete: async (id: string) => {
        const response = await api.delete(`/api/v1/products/${id}`);
        return response.data;
    },
};

// ==========================================
// Materials API
// ==========================================
export const materialsApi = {
    getAll: async (category?: string) => {
        const params = category ? { category } : {};
        const response = await api.get('/api/v1/materials', { params });
        return response.data;
    },
    create: async (data: any) => {
        const response = await api.post('/api/v1/materials', data);
        return response.data;
    },
    update: async (id: string, data: any) => {
        const response = await api.put(`/api/v1/materials/${id}`, data);
        return response.data;
    },
    delete: async (id: string) => {
        const response = await api.delete(`/api/v1/materials/${id}`);
        return response.data;
    },
    getStock: async (materialId?: string) => {
        const params = materialId ? { material_id: materialId } : {};
        const response = await api.get('/api/v1/materials/stock', { params });
        return response.data;
    },
    updateStock: async (materialId: string, data: any) => {
        const response = await api.put(`/api/v1/materials/${materialId}/stock`, data);
        return response.data;
    },
};

// ==========================================
// Recipes API
// ==========================================
export const recipesApi = {
    getAll: async (productId?: string) => {
        const params = productId ? { product_id: productId } : {};
        const response = await api.get('/api/v1/recipes', { params });
        return response.data;
    },
    create: async (data: any) => {
        const response = await api.post('/api/v1/recipes', data);
        return response.data;
    },
    update: async (id: string, data: any) => {
        const response = await api.put(`/api/v1/recipes/${id}`, data);
        return response.data;
    },
    delete: async (id: string) => {
        const response = await api.delete(`/api/v1/recipes/${id}`);
        return response.data;
    },
    addItem: async (recipeId: string, materialId: string, qtyPerBase: number) => {
        const response = await api.post(`/api/v1/recipes/${recipeId}/items`, null, {
            params: { material_id: materialId, qty_per_base: qtyPerBase },
        });
        return response.data;
    },
    deleteItem: async (recipeId: string, itemId: string) => {
        const response = await api.delete(`/api/v1/recipes/${recipeId}/items/${itemId}`);
        return response.data;
    },
};

// ==========================================
// Operations API
// ==========================================
export const operationsApi = {
    getAll: async (versionId?: string) => {
        const params = versionId ? { version_id: versionId } : {};
        const response = await api.get('/api/v1/operations', { params });
        return response.data;
    },
    getProducts: async () => {
        const response = await api.get('/api/v1/operations/products');
        return response.data;
    },
    create: async (data: any) => {
        const response = await api.post('/api/v1/operations', data);
        return response.data;
    },
    update: async (id: string, data: any) => {
        const response = await api.put(`/api/v1/operations/${id}`, data);
        return response.data;
    },
    delete: async (id: string) => {
        const response = await api.delete(`/api/v1/operations/${id}`);
        return response.data;
    },
};

// ==========================================
// Calendar API
// ==========================================
export const calendarApi = {
    getAll: async (params?: { equipment_id?: string; version_id?: string; include_global?: boolean }) => {
        const response = await api.get('/api/v1/calendar', { params });
        return response.data;
    },
    create: async (data: any) => {
        const response = await api.post('/api/v1/calendar', data);
        return response.data;
    },
    update: async (id: string, data: any) => {
        const response = await api.put(`/api/v1/calendar/${id}`, data);
        return response.data;
    },
    delete: async (id: string) => {
        const response = await api.delete(`/api/v1/calendar/${id}`);
        return response.data;
    },
};

// ==========================================
// Orders API
// ==========================================
export const ordersApi = {
    getAll: async (status?: string) => {
        const params = status ? { status } : {};
        const response = await api.get('/api/v1/orders', { params });
        return response.data;
    },
    create: async (data: any) => {
        const response = await api.post('/api/v1/orders', data);
        return response.data;
    },
    update: async (id: string, data: any) => {
        const response = await api.put(`/api/v1/orders/${id}`, data);
        return response.data;
    },
    delete: async (id: string) => {
        const response = await api.delete(`/api/v1/orders/${id}`);
        return response.data;
    },
    getBatches: async (orderId: string) => {
        const response = await api.get(`/api/v1/orders/${orderId}/batches`);
        return response.data;
    },
    createBatch: async (orderId: string, data: any) => {
        const response = await api.post(`/api/v1/orders/${orderId}/batches`, data);
        return response.data;
    },
    updateBatch: async (orderId: string, batchId: string, data: any) => {
        const response = await api.put(`/api/v1/orders/${orderId}/batches/${batchId}`, data);
        return response.data;
    },
    deleteBatch: async (orderId: string, batchId: string) => {
        const response = await api.delete(`/api/v1/orders/${orderId}/batches/${batchId}`);
        return response.data;
    },
    autoSplit: async (orderId: string, equipmentId: string, maxFillPercent = 0.70) => {
        const response = await api.post(`/api/v1/orders/${orderId}/auto-split`, null, {
            params: { equipment_id: equipmentId, max_fill_percent: maxFillPercent },
        });
        return response.data;
    },
};

// ==========================================
// Schedule API
// ==========================================
export const scheduleApi = {
    build: async (data: { horizon_hours?: number; timeout_seconds?: number }) => {
        const response = await api.post('/api/v1/schedule/build', data);
        return response.data;
    },
    getLastResult: async () => {
        const response = await api.get('/api/v1/schedule/last-result');
        return response.data;
    },
    save: async () => {
        const response = await api.post('/api/v1/schedule/save');
        return response.data;
    },
    getVersions: async () => {
        const response = await api.get('/api/v1/schedule/versions');
        return response.data;
    },
    createVersion: async (data: { name: string; version_type: string; comment?: string }) => {
        const response = await api.post('/api/v1/schedule/versions', data);
        return response.data;
    },
    deleteVersion: async (versionId: string) => {
        const response = await api.delete(`/api/v1/schedule/versions/${versionId}`);
        return response.data;
    },
};

// ==========================================
// Gantt API
// ==========================================
export const ganttApi = {
    getData: async (versionId?: string) => {
        const params = versionId ? { version_id: versionId } : {};
        const response = await api.get('/api/v1/gantt', { params });
        return response.data;
    },
    exportExcel: async (versionId?: string) => {
        const params = versionId ? { version_id: versionId } : {};
        const response = await api.get('/api/v1/gantt/export', {
            params,
            responseType: 'blob',
        });
        return response.data;
    },
};

export default api;