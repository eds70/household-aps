// frontend/src/services/api.ts
import axios from 'axios';
import {API_BASE_URL} from '../config';

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
    getByEquipment: async (equipmentId: string, versionId?: string) => {
        const params: any = { equipment_id: equipmentId };
        if (versionId) params.version_id = versionId;
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

// ==========================================
// Advisor API
// ==========================================
export const advisorApi = {
    getAdvice: async (): Promise<import('../types').AdvisorResponse> => {
        const response = await api.get('/api/v1/schedule/advice');
        return response.data;
    },
    checkFeasibility: async (): Promise<import('../types').FeasibilityResponse> => {
        const response = await api.post('/api/v1/schedule/feasibility');
        return response.data;
    },
};

// ==========================================
// Shift API
// ==========================================
export const shiftApi = {
    list: async (params?: {
        date_from?: string;
        date_to?: string;
        only_working?: boolean;
    }): Promise<import('../types').Shift[]> => {
        const response = await api.get('/api/v1/shift/list', { params });
        return response.data;
    },

    /**
     * Итерация 11: возвращает МАССИВ смен за день
     * (для режимов 3x8 и 2x12 в день несколько смен).
     */
    getByDate: async (shiftDate: string): Promise<import('../types').Shift[]> => {
        const response = await api.get(`/api/v1/shift/by-date/${shiftDate}`);
        return response.data;
    },

    getTasks: async (shiftId: string): Promise<import('../types').ShiftTasksResponse> => {
        const response = await api.get(`/api/v1/shift/${shiftId}/tasks`);
        return response.data;
    },

    getCarryover: async (shiftId: string): Promise<import('../types').ShiftTask[]> => {
        const response = await api.get(`/api/v1/shift/${shiftId}/carryover`);
        return response.data;
    },

    updateTaskFact: async (
        taskId: string,
        fact: import('../types').TaskFactRequest,
    ): Promise<import('../types').TaskFactResponse> => {
        const response = await api.post(`/api/v1/shift/task/${taskId}/fact`, fact);
        return response.data;
    },
};

// ==========================================
// Reschedule API
// ==========================================
export const rescheduleApi = {
    reschedule: async (
        data: import('../types').RescheduleRequest
    ): Promise<import('../types').RescheduleResponse> => {
        const response = await api.post('/api/v1/schedule/reschedule', data);
        return response.data;
    },

    compare: async (v1: string, v2: string): Promise<import('../types').CompareResponse> => {
        const response = await api.get('/api/v1/schedule/compare', {
            params: { v1, v2 },
        });
        return response.data;
    },

    pinTask: async (
        taskId: string,
        isPinned: boolean
    ): Promise<import('../types').PinTaskResponse> => {
        const response = await api.put(`/api/v1/schedule/task/${taskId}/pin`, {
            is_pinned: isPinned,
        });
        return response.data;
    },

    // Итерация 9 (C2): перемещение задачи drag-and-drop на Ганте.
    // Меняет planned_start/planned_end и ставит is_pinned=TRUE.
    // Валидация на backend: длительность не должна меняться.
    moveTask: async (
        taskId: string,
        newStart: string,
        newEnd: string,
    ): Promise<import('../types').MoveTaskResponse> => {
        const response = await api.put(`/api/v1/schedule/task/${taskId}/move`, {
            new_start: newStart,
            new_end: newEnd,
        });
        return response.data;
    },
};

// ==========================================
// Lab API (Итерация 5)
// ==========================================
export const labApi = {
    /** Партии, ожидающие анализа или заблокированные */
    getPending: async (params?: {
        include_blocked?: boolean;
        include_pending?: boolean;
    }): Promise<import('../types').LabPendingBatch[]> => {
        const response = await api.get('/api/v1/lab/pending', { params });
        return response.data;
    },

    /** Статус партии по лаборатории */
    getBatchStatus: async (batchId: string): Promise<import('../types').BatchLabStatus> => {
        const response = await api.get(`/api/v1/lab/batch/${batchId}`);
        return response.data;
    },

    /** Журнал проверок партии */
    getBatchLog: async (batchId: string, limit = 50): Promise<import('../types').LabAnalysisLogEntry[]> => {
        const response = await api.get(`/api/v1/lab/batch/${batchId}/log`, {
            params: { limit },
        });
        return response.data;
    },

    /** Заблокировать партию */
    blockBatch: async (
        batchId: string,
        data: import('../types').BlockBatchRequest
    ): Promise<import('../types').LabActionResponse> => {
        const response = await api.post(`/api/v1/lab/batch/${batchId}/block`, data);
        return response.data;
    },

    /** Разблокировать партию */
    unblockBatch: async (
        batchId: string,
        data: import('../types').UnblockBatchRequest
    ): Promise<import('../types').LabActionResponse> => {
        const response = await api.post(`/api/v1/lab/batch/${batchId}/unblock`, data);
        return response.data;
    },

    /** Одобрить партию после анализа */
    approveBatch: async (
        batchId: string,
        data: import('../types').ApproveBatchRequest
    ): Promise<import('../types').LabActionResponse> => {
        const response = await api.post(`/api/v1/lab/batch/${batchId}/approve`, data);
        return response.data;
    },

    /** Запросить анализ для партии */
    requestAnalysis: async (
        batchId: string,
        data: import('../types').RequestAnalysisRequest
    ): Promise<import('../types').LabActionResponse> => {
        const response = await api.post(`/api/v1/lab/batch/${batchId}/request`, data);
        return response.data;
    },
};

// ==========================================
// Personnel API (Итерация 6)
// ==========================================
export const personnelApi = {
    /** Список пулов операторов с загрузкой */
    listPools: async (versionId?: string): Promise<import('../types').PersonnelPoolList> => {
        const params = versionId ? { version_id: versionId } : {};
        const response = await api.get('/api/v1/personnel/pools', { params });
        return response.data;
    },

    /** Один пул */
    getPool: async (
        poolId: string,
        versionId?: string,
    ): Promise<import('../types').PersonnelPool> => {
        const params = versionId ? { version_id: versionId } : {};
        const response = await api.get(`/api/v1/personnel/pools/${poolId}`, { params });
        return response.data;
    },

    /** Обновить capacity / name / comment */
    updatePool: async (
        poolId: string,
        data: import('../types').PersonnelPoolUpdate,
    ): Promise<import('../types').PersonnelPool> => {
        const response = await api.put(`/api/v1/personnel/pools/${poolId}`, data);
        return response.data;
    },

    /** Краткая информация о загрузке */
    getLoad: async (versionId?: string): Promise<import('../types').PersonnelLoadItem[]> => {
        const params = versionId ? { version_id: versionId } : {};
        const response = await api.get('/api/v1/personnel/load', { params });
        return response.data;
    },
};

// ==========================================
// CZ API (Честный Знак, Итерация 8)
// ==========================================
export const czApi = {
    /**
     * Приём скана от камеры.
     * Требует заголовок X-CZ-Api-Key.
     */
    scan: async (
        data: import('../types').CzScanRequest,
        apiKey: string,
    ): Promise<import('../types').CzScanResponse> => {
        const response = await api.post('/api/v1/cz/scan', data, {
            headers: { 'X-CZ-Api-Key': apiKey },
        });
        return response.data;
    },

    /** Прогресс маркировки партии */
    getBatchProgress: async (batchId: string): Promise<import('../types').CzProgress> => {
        const response = await api.get(`/api/v1/cz/batch/${batchId}/progress`);
        return response.data;
    },

    /** Партии, ожидающие маркировки */
    getPending: async (params?: {
        include_completed?: boolean;
        limit?: number;
    }): Promise<import('../types').CzPendingBatch[]> => {
        const response = await api.get('/api/v1/cz/pending', { params });
        return response.data;
    },

    /** Журнал сканирований */
    getLog: async (params?: {
        batch_id?: string;
        line_code?: string;
        camera_id?: string;
        only_unresolved?: boolean;
        limit?: number;
    }): Promise<import('../types').CzScanLogEntry[]> => {
        const response = await api.get('/api/v1/cz/log', { params });
        return response.data;
    },

    /** Сводная статистика */
    getStats: async (): Promise<import('../types').CzStats> => {
        const response = await api.get('/api/v1/cz/stats');
        return response.data;
    },

    /** Ручное сопоставление скана-сироты (ADMIN, PLANNER, MASTER) */
    attachScan: async (
        scanId: string,
        data: import('../types').CzAttachRequest,
    ): Promise<import('../types').CzActionResponse> => {
        const response = await api.post(`/api/v1/cz/scan/${scanId}/attach`, data);
        return response.data;
    },

    /** Удаление скана (только ADMIN) */
    deleteScan: async (scanId: string): Promise<import('../types').CzActionResponse> => {
        const response = await api.delete(`/api/v1/cz/scan/${scanId}`);
        return response.data;
    },
};

// ==========================================
// Settings API (Итерация 11)
// ==========================================
export const settingsApi = {
    /** Полный реестр настроек с метаданными */
    getSchema: async (): Promise<import('../types').SettingsSchema> => {
        const response = await api.get('/api/v1/settings/schema');
        return response.data;
    },

    /** Список категорий */
    getCategories: async (): Promise<import('../types').SettingsCategory[]> => {
        const response = await api.get('/api/v1/settings/categories');
        return response.data;
    },

    /** Все настройки организации */
    getAll: async (): Promise<Record<string, any>> => {
        const response = await api.get('/api/v1/settings/');
        return response.data;
    },

    /** Настройки одной категории */
    getCategory: async (category: string): Promise<Record<string, any>> => {
        const response = await api.get(`/api/v1/settings/category/${category}`);
        return response.data;
    },

    /** Массовое обновление */
    updateBulk: async (settings: Record<string, any>): Promise<any> => {
        const response = await api.put('/api/v1/settings/', { settings });
        return response.data;
    },

    /** Обновление одной настройки */
    updateSingle: async (key: string, value: any): Promise<any> => {
        const response = await api.put(`/api/v1/settings/${key}`, { value });
        return response.data;
    },

    /** Смена режима смен (ADMIN) */
    changeShiftMode: async (shiftMode: string): Promise<any> => {
        const response = await api.post('/api/v1/settings/shift-mode', {
            shift_mode: shiftMode,
        });
        return response.data;
    },
};

export default api;