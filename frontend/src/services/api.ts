// frontend/src/services/api.ts
import axios from 'axios';
import { API_BASE_URL } from '../config';

const api = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

// Equipment API
export const equipmentApi = {
    getAll: async (versionId?: string) => {
        const params = versionId ? { version_id: versionId } : {};
        const response = await api.get('/api/v1/equipment', { params });
        return response.data;
    },
};

// Products API
export const productsApi = {
    getAll: async (versionId?: string) => {
        const params = versionId ? { version_id: versionId } : {};
        const response = await api.get('/api/v1/products', { params });
        return response.data;
    },
};

// Operations API
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
};

// Schedule API
export const scheduleApi = {
    build: async (data: { horizon_hours?: number; timeout_seconds?: number }) => {
        const response = await api.post('/api/v1/schedule/build', data);
        return response.data;
    },
    getLastResult: async () => {
        const response = await api.get('/api/v1/schedule/last-result');
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

// Gantt API
export const ganttApi = {
    getData: async (versionId?: string) => {
        const params = versionId ? { version_id: versionId } : {};
        const response = await api.get('/api/v1/gantt/', { params });
        return response.data;
    },
};

// Calendar API
export const calendarApi = {
    getByEquipment: async (equipmentId: string, versionId?: string) => {
        const params: any = { equipment_id: equipmentId, include_global: false };
        if (versionId) params.version_id = versionId;
        const response = await api.get('/api/v1/calendar/', { params });
        return response.data;
    },
    create: async (data: {
        equipment_id: string | null;
        event_type: string;
        starts_at: string;
        ends_at: string;
        comment?: string;
    }) => {
        const response = await api.post('/api/v1/calendar/', {
            ...data,
            organization_id: '00000000-0000-0000-0000-000000000001',
        });
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

// Materials API
export const materialsApi = {
    getAll: async (category?: string) => {
        const params = category ? { category } : {};
        const response = await api.get('/api/v1/materials/', { params });
        return response.data;
    },
    create: async (data: any) => {
        const response = await api.post('/api/v1/materials/', data);
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
    updateStock: async (materialId: string, data: { qty?: number; reserved_qty?: number }) => {
        const response = await api.put(`/api/v1/materials/${materialId}/stock`, data);
        return response.data;
    },
};

// Recipes API
export const recipesApi = {
    getAll: async (productId?: string) => {
        const params = productId ? { product_id: productId } : {};
        const response = await api.get('/api/v1/recipes/', { params });
        return response.data;
    },
    create: async (data: any) => {
        const response = await api.post('/api/v1/recipes/', data);
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

// Orders API
export const ordersApi = {
    getAll: async (status?: string) => {
        const params = status ? { status } : {};
        const response = await api.get('/api/v1/orders/', { params });
        return response.data;
    },
    create: async (data: any) => {
        const response = await api.post('/api/v1/orders/', data);
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
    autoSplit: async (orderId: string, equipmentId: string, maxFillPercent: number = 0.70) => {
        const response = await api.post(`/api/v1/orders/${orderId}/auto-split`, null, {
            params: { equipment_id: equipmentId, max_fill_percent: maxFillPercent },
        });
        return response.data;
    },
};

export default api;