// frontend/src/types/index.ts

export interface Equipment {
    id: string;
    name: string;
    type: string;
    volume_kg?: number;
    speed_coeff?: number;
    mixer_type?: string;
    is_active: boolean;
}

export interface Product {
    id: string;
    code: string;
    name: string;
    type: 'PF' | 'GP';
    viscosity_coeff?: number;
    requires_heating?: boolean;
    bottle_volume_l?: number;
    fill_speed_per_min?: number;
    parent_pf_id?: string;
}

export interface Operation {
    id: string;
    product_id: string;
    product_name?: string;
    stage_order: number;
    name: string;
    base_duration_mins: number;
    is_setup: boolean;
    is_parallel_group: boolean;
    parallel_group_id?: string;
    needs_boiler: boolean;
    needs_cooling_zone: boolean;
    needs_operator: boolean;
    needs_lab: boolean;
    duration_formula?: string;
    comment?: string;
}

export interface ProductOption {
    id: string;
    name: string;
    code: string;
}

export interface CalendarEvent {
    id: string;
    organization_id: string;
    equipment_id: string | null;
    event_type: 'WEEKEND' | 'REPAIR' | 'BREAKDOWN' | 'SHIFT_END' | 'LUNCH';
    starts_at: string;
    ends_at: string;
    comment?: string | null;
}

// ===== МАТЕРИАЛЫ =====

export type MaterialCategory = 'RAW' | 'PACKAGING' | 'LABEL';
export type MaterialUnit = 'kg' | 'pc' | 'l';

export interface Material {
    id: string;
    code: string;
    name: string;
    unit: MaterialUnit;
    category: MaterialCategory;
    comment?: string | null;
}

export interface MaterialStock {
    id: string;
    material_id: string;
    qty: number;
    reserved_qty: number;
    updated_at: string;
}

// ===== РЕЦЕПТЫ =====

export interface RecipeItem {
    id: string;
    recipe_id: string;
    material_id: string;
    qty_per_base: number;
    material_name?: string;
    material_code?: string;
    material_unit?: string;
}

export interface Recipe {
    id: string;
    product_id: string;
    base_volume_kg: number;
    comment?: string | null;
    product_name?: string;
    product_code?: string;
    items: RecipeItem[];
}

// ===== ЗАКАЗЫ И ПАРТИИ =====

export type OrderStatus = 'PLANNED' | 'IN_PROGRESS' | 'DONE' | 'CANCELLED';
export type BatchStatus = 'NOT_STARTED' | 'IN_PROGRESS' | 'COMPLETED' | 'BLOCKED';

export interface ProductionOrder {
    id: string;
    product_id: string;
    target_qty: number;
    due_date: string;
    priority: number;
    status: OrderStatus;
    created_at: string;
    comment?: string | null;
    product_name?: string;
    product_code?: string;
    batches_count: number;
}

export interface Batch {
    id: string;
    order_id: string;
    product_id: string;
    volume_kg: number;
    assigned_equipment_id?: string | null;
    planned_start?: string | null;
    planned_end?: string | null;
    status: BatchStatus;
    comment?: string | null;
    product_name?: string;
    product_code?: string;
    equipment_name?: string;
}

// ==========================================
// Авторизация
// ==========================================
export interface LoginRequest {
    email: string;
    password: string;
}

export interface TokenResponse {
    access_token: string;
    token_type: string;
    user_id: string;
    organization_id: string;
    role: string;
    full_name?: string;
}

export interface User {
    id: string;
    email: string;
    full_name?: string;
    role: 'ADMIN' | 'PLANNER' | 'MASTER' | 'LAB' | 'VIEWER';
    organization_id: string;
    is_active: boolean;
    last_login_at?: string;
}

export type UserRole = User['role'];


// ==========================================
// ADVISOR
// ==========================================

export type AdvisorSeverity = 'CRITICAL' | 'WARNING' | 'INFO';

export interface AdvisorTip {
    code: string;
    severity: AdvisorSeverity;
    title: string;
    message: string;
    details: Record<string, any>;
}

export interface AdvisorResponse {
    tips: AdvisorTip[];
    critical_count: number;
    warning_count: number;
    info_count: number;
    generated_at: string;
}

export interface FeasibilityIssue {
    code: string;
    severity: 'BLOCKER' | 'WARNING';
    message: string;
    details: Record<string, any>;
}

export interface FeasibilityResponse {
    feasible: boolean;
    issues: FeasibilityIssue[];
    warnings: FeasibilityIssue[];
}