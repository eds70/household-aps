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
    getAll: async (category?: string): Promise<import('../types').Material[]> => {
        const params = category ? { category } : {};
        const response = await api.get('/api/v1/materials', { params });
        return response.data;
    },
    create: async (data: any): Promise<import('../types').Material> => {
        const response = await api.post('/api/v1/materials', data);
        return response.data;
    },
    update: async (id: string, data: any): Promise<import('../types').Material> => {
        const response = await api.put(`/api/v1/materials/${id}`, data);
        return response.data;
    },
    delete: async (id: string): Promise<{ message: string }> => {
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
    getStockLog: async (params?: {
        material_id?: string;
        source?: string;
        date_from?: string;
        date_to?: string;
        limit?: number;
    }): Promise<import('../types').MaterialStockLogListResponse> => {
        const response = await api.get('/api/v1/materials/stock-log', { params });
        return response.data;
    },
    getMaterialLog: async (
        materialId: string,
        limit: number = 100,
    ): Promise<import('../types').MaterialStockLogEntry[]> => {
        const response = await api.get(`/api/v1/materials/${materialId}/log`, {
            params: { limit },
        });
        return response.data;
    },
    importExcel: async (
        file: File,
    ): Promise<import('../types').MaterialImportResponse> => {
        const formData = new FormData();
        formData.append('file', file);
        const response = await api.post('/api/v1/materials/import-excel', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
        });
        return response.data;
    },
    downloadImportTemplate: async (): Promise<Blob> => {
        const response = await api.get('/api/v1/materials/import-template', {
            responseType: 'blob',
        });
        return response.data;
    },
    exportExcel: async (): Promise<Blob> => {
        const response = await api.get('/api/v1/materials/export-excel', {
            responseType: 'blob',
        });
        return response.data;
    },
    revertStockLog: async (logId: string) => {
        const response = await api.post(`/api/v1/materials/stock-log/${logId}/revert`);
        return response.data;
    },
    cleanupStockLog: async (olderThanDays: number = 90, source?: string) => {
        const params: any = { older_than_days: olderThanDays };
        if (source) params.source = source;
        const response = await api.delete('/api/v1/materials/stock-log/cleanup', { params });
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
// Advisor API (Итерация 13.14: + version_id)
// ==========================================
export const advisorApi = {
    getAdvice: async (versionId?: string): Promise<import('../types').AdvisorResponse> => {
        const params = versionId ? { version_id: versionId } : {};
        const response = await api.get('/api/v1/schedule/advice', { params });
        return response.data;
    },
    checkFeasibility: async (versionId?: string): Promise<import('../types').FeasibilityResponse> => {
        const params = versionId ? { version_id: versionId } : {};
        const response = await api.post('/api/v1/schedule/feasibility', null, { params });
        return response.data;
    },
};

// ==========================================
// Shift API (Итерация 13.14: + version_id)
// ==========================================
export const shiftApi = {
    list: async (params?: {
        date_from?: string;
        date_to?: string;
        only_working?: boolean;
        version_id?: string;
    }): Promise<import('../types').Shift[]> => {
        const response = await api.get('/api/v1/shift/list', { params });
        return response.data;
    },
    getByDate: async (
        shiftDate: string,
        versionId?: string,
    ): Promise<import('../types').Shift[]> => {
        const params = versionId ? { version_id: versionId } : {};
        const response = await api.get(`/api/v1/shift/by-date/${shiftDate}`, { params });
        return response.data;
    },
    getTasks: async (
        shiftId: string,
        versionId?: string,
    ): Promise<import('../types').ShiftTasksResponse> => {
        const params = versionId ? { version_id: versionId } : {};
        const response = await api.get(`/api/v1/shift/${shiftId}/tasks`, { params });
        return response.data;
    },
    getCarryover: async (
        shiftId: string,
        versionId?: string,
    ): Promise<import('../types').ShiftTask[]> => {
        const params = versionId ? { version_id: versionId } : {};
        const response = await api.get(`/api/v1/shift/${shiftId}/carryover`, { params });
        return response.data;
    },
    updateTaskFact: async (
        taskId: string,
        fact: import('../types').TaskFactRequest,
        versionId?: string,
    ): Promise<import('../types').TaskFactResponse> => {
        const params = versionId ? { version_id: versionId } : {};
        const response = await api.post(
            `/api/v1/shift/task/${taskId}/fact`,
            fact,
            { params },
        );
        return response.data;
    },
};

// ==========================================
// Reschedule API (Итерация 13.14: + version_id)
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
        isPinned: boolean,
        versionId?: string,
    ): Promise<import('../types').PinTaskResponse> => {
        const params = versionId ? { version_id: versionId } : {};
        const response = await api.put(
            `/api/v1/schedule/task/${taskId}/pin`,
            { is_pinned: isPinned },
            { params },
        );
        return response.data;
    },
    moveTask: async (
        taskId: string,
        newStart: string,
        newEnd: string,
        versionId?: string,
    ): Promise<import('../types').MoveTaskResponse> => {
        const params = versionId ? { version_id: versionId } : {};
        const response = await api.put(
            `/api/v1/schedule/task/${taskId}/move`,
            {
                new_start: newStart,
                new_end: newEnd,
            },
            { params },
        );
        return response.data;
    },
};

// ==========================================
// Lab API (Итерация 5; 13.14: + version_id)
// ==========================================
export const labApi = {
    getPending: async (params?: {
        include_blocked?: boolean;
        include_pending?: boolean;
        version_id?: string;
    }): Promise<import('../types').LabPendingBatch[]> => {
        const response = await api.get('/api/v1/lab/pending', { params });
        return response.data;
    },
    getBatchStatus: async (
        batchId: string,
        versionId?: string,
    ): Promise<import('../types').BatchLabStatus> => {
        const params = versionId ? { version_id: versionId } : {};
        const response = await api.get(`/api/v1/lab/batch/${batchId}`, { params });
        return response.data;
    },
    getBatchLog: async (
        batchId: string,
        limit = 50,
        versionId?: string,
    ): Promise<import('../types').LabAnalysisLogEntry[]> => {
        const params: any = { limit };
        if (versionId) params.version_id = versionId;
        const response = await api.get(`/api/v1/lab/batch/${batchId}/log`, { params });
        return response.data;
    },
    blockBatch: async (
        batchId: string,
        data: import('../types').BlockBatchRequest,
        versionId?: string,
    ): Promise<import('../types').LabActionResponse> => {
        const params = versionId ? { version_id: versionId } : {};
        const response = await api.post(
            `/api/v1/lab/batch/${batchId}/block`,
            data,
            { params },
        );
        return response.data;
    },
    unblockBatch: async (
        batchId: string,
        data: import('../types').UnblockBatchRequest,
        versionId?: string,
    ): Promise<import('../types').LabActionResponse> => {
        const params = versionId ? { version_id: versionId } : {};
        const response = await api.post(
            `/api/v1/lab/batch/${batchId}/unblock`,
            data,
            { params },
        );
        return response.data;
    },
    approveBatch: async (
        batchId: string,
        data: import('../types').ApproveBatchRequest,
        versionId?: string,
    ): Promise<import('../types').LabActionResponse> => {
        const params = versionId ? { version_id: versionId } : {};
        const response = await api.post(
            `/api/v1/lab/batch/${batchId}/approve`,
            data,
            { params },
        );
        return response.data;
    },
    requestAnalysis: async (
        batchId: string,
        data: import('../types').RequestAnalysisRequest,
        versionId?: string,
    ): Promise<import('../types').LabActionResponse> => {
        const params = versionId ? { version_id: versionId } : {};
        const response = await api.post(
            `/api/v1/lab/batch/${batchId}/request`,
            data,
            { params },
        );
        return response.data;
    },
};

// ==========================================
// Personnel API (Итерация 6)
// ==========================================
export const personnelApi = {
    listPools: async (versionId?: string): Promise<import('../types').PersonnelPoolList> => {
        const params = versionId ? { version_id: versionId } : {};
        const response = await api.get('/api/v1/personnel/pools', { params });
        return response.data;
    },
    getPool: async (
        poolId: string,
        versionId?: string,
    ): Promise<import('../types').PersonnelPool> => {
        const params = versionId ? { version_id: versionId } : {};
        const response = await api.get(`/api/v1/personnel/pools/${poolId}`, { params });
        return response.data;
    },
    updatePool: async (
        poolId: string,
        data: import('../types').PersonnelPoolUpdate,
        versionId?: string,
    ): Promise<import('../types').PersonnelPool> => {
        const params = versionId ? { version_id: versionId } : {};
        const response = await api.put(
            `/api/v1/personnel/pools/${poolId}`,
            data,
            { params },
        );
        return response.data;
    },
    getLoad: async (versionId?: string): Promise<import('../types').PersonnelLoadItem[]> => {
        const params = versionId ? { version_id: versionId } : {};
        const response = await api.get('/api/v1/personnel/load', { params });
        return response.data;
    },
};

// ==========================================
// CZ API (Честный Знак, Итерация 8; 13.14: + version_id)
// ==========================================
export const czApi = {
    scan: async (
        data: import('../types').CzScanRequest,
        apiKey: string,
        versionId?: string,
    ): Promise<import('../types').CzScanResponse> => {
        const params = versionId ? { version_id: versionId } : {};
        const response = await api.post('/api/v1/cz/scan', data, {
            headers: { 'X-CZ-Api-Key': apiKey },
            params,
        });
        return response.data;
    },
    getBatchProgress: async (
        batchId: string,
        versionId?: string,
    ): Promise<import('../types').CzProgress> => {
        const params = versionId ? { version_id: versionId } : {};
        const response = await api.get(`/api/v1/cz/batch/${batchId}/progress`, { params });
        return response.data;
    },
    getPending: async (params?: {
        include_completed?: boolean;
        limit?: number;
        version_id?: string;
    }): Promise<import('../types').CzPendingBatch[]> => {
        const response = await api.get('/api/v1/cz/pending', { params });
        return response.data;
    },
    getLog: async (params?: {
        batch_id?: string;
        line_code?: string;
        camera_id?: string;
        only_unresolved?: boolean;
        limit?: number;
        version_id?: string;
    }): Promise<import('../types').CzScanLogEntry[]> => {
        const response = await api.get('/api/v1/cz/log', { params });
        return response.data;
    },
    getStats: async (versionId?: string): Promise<import('../types').CzStats> => {
        const params = versionId ? { version_id: versionId } : {};
        const response = await api.get('/api/v1/cz/stats', { params });
        return response.data;
    },
    attachScan: async (
        scanId: string,
        data: import('../types').CzAttachRequest,
        versionId?: string,
    ): Promise<import('../types').CzActionResponse> => {
        const params = versionId ? { version_id: versionId } : {};
        const response = await api.post(
            `/api/v1/cz/scan/${scanId}/attach`,
            data,
            { params },
        );
        return response.data;
    },
    deleteScan: async (
        scanId: string,
        versionId?: string,
    ): Promise<import('../types').CzActionResponse> => {
        const params = versionId ? { version_id: versionId } : {};
        const response = await api.delete(`/api/v1/cz/scan/${scanId}`, { params });
        return response.data;
    },
};

// ==========================================
// Settings API (Итерация 11)
// ==========================================
export const settingsApi = {
    getSchema: async (): Promise<import('../types').SettingsSchema> => {
        const response = await api.get('/api/v1/settings/schema');
        return response.data;
    },
    getCategories: async (): Promise<import('../types').SettingsCategory[]> => {
        const response = await api.get('/api/v1/settings/categories');
        return response.data;
    },
    getAll: async (): Promise<Record<string, any>> => {
        const response = await api.get('/api/v1/settings/');
        return response.data;
    },
    getCategory: async (category: string): Promise<Record<string, any>> => {
        const response = await api.get(`/api/v1/settings/category/${category}`);
        return response.data;
    },
    updateBulk: async (settings: Record<string, any>): Promise<any> => {
        const response = await api.put('/api/v1/settings/', { settings });
        return response.data;
    },
    updateSingle: async (key: string, value: any): Promise<any> => {
        const response = await api.put(`/api/v1/settings/${key}`, { value });
        return response.data;
    },
    changeShiftMode: async (shiftMode: string): Promise<any> => {
        const response = await api.post('/api/v1/settings/shift-mode', {
            shift_mode: shiftMode,
        });
        return response.data;
    },
};

// ==========================================
// Plan Settings API (Итерация 13.14)
// ==========================================
export const planSettingsApi = {
    /**
     * Настройки конкретного плана (snapshot).
     *
     * Возвращает:
     *   - settings: {key: value} — для чтения
     *   - schema: полный реестр с метаданными
     *   - categories: список категорий с label
     */
    getForVersion: async (versionId: string): Promise<{
        version_id: string;
        settings: Record<string, any>;
        schema: any[];
        categories: {key: string; label: string}[];
    }> => {
        const response = await api.get(`/api/v1/plan-settings/version/${versionId}`);
        return response.data;
    },

    /** Массовое обновление настроек плана. */
    updateForVersion: async (
        versionId: string,
        settings: Record<string, any>,
    ): Promise<any> => {
        const response = await api.put(
            `/api/v1/plan-settings/version/${versionId}`,
            {settings},
        );
        return response.data;
    },

    /** Сброс настроек плана к глобальным app_settings. */
    resetForVersion: async (versionId: string): Promise<any> => {
        const response = await api.post(
            `/api/v1/plan-settings/version/${versionId}/reset`,
        );
        return response.data;
    },
};

// ==========================================
// What-If API (Итерация 12)
// ==========================================
export const whatifApi = {
    listScenarios: async (
        status?: import('../types').WhatIfStatus,
        limit: number = 100,
    ): Promise<import('../types').WhatIfScenarioListItem[]> => {
        const params: any = { limit };
        if (status) params.status = status;
        const response = await api.get('/api/v1/whatif/scenarios', { params });
        return response.data;
    },
    getScenario: async (
        id: string,
    ): Promise<import('../types').WhatIfScenario> => {
        const response = await api.get(`/api/v1/whatif/scenarios/${id}`);
        return response.data;
    },
    createScenario: async (
        data: import('../types').WhatIfScenarioCreate,
    ): Promise<import('../types').WhatIfScenario> => {
        const response = await api.post('/api/v1/whatif/scenarios', data);
        return response.data;
    },
    updateScenario: async (
        id: string,
        data: import('../types').WhatIfScenarioUpdate,
    ): Promise<import('../types').WhatIfScenario> => {
        const response = await api.put(
            `/api/v1/whatif/scenarios/${id}`,
            data,
        );
        return response.data;
    },
    deleteScenario: async (id: string): Promise<{ message: string }> => {
        const response = await api.delete(
            `/api/v1/whatif/scenarios/${id}`,
        );
        return response.data;
    },
    runScenario: async (
        id: string,
        data?: import('../types').WhatIfRunRequest,
    ): Promise<import('../types').WhatIfRunResponse> => {
        const response = await api.post(
            `/api/v1/whatif/scenarios/${id}/run`,
            data || {},
            { timeout: 300_000 },
        );
        return response.data;
    },
    compareScenario: async (
        id: string,
    ): Promise<import('../types').WhatIfCompareResponse> => {
        const response = await api.get(
            `/api/v1/whatif/scenarios/${id}/compare`,
        );
        return response.data;
    },
};

// ==========================================
// Audit API (Итерация 13.3)
// ==========================================
export const auditApi = {
    getLog: async (params?: {
        sources?: string;
        date_from?: string;
        date_to?: string;
        severity?: string;
        search?: string;
        limit?: number;
    }): Promise<import('../types').AuditListResponse> => {
        const response = await api.get('/api/v1/audit/log', { params });
        return response.data;
    },
    getStats: async (days: number = 7): Promise<import('../types').AuditStatsResponse> => {
        const response = await api.get('/api/v1/audit/stats', { params: { days } });
        return response.data;
    },
    getSources: async (): Promise<{ sources: import('../types').AuditSourceInfo[] }> => {
        const response = await api.get('/api/v1/audit/sources');
        return response.data;
    },
};

export default api;