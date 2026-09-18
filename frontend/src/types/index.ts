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

// Итерация 5: статус лабораторной проверки партии
export type LabStatus = 'NOT_REQUIRED' | 'PENDING_LAB' | 'APPROVED' | 'BLOCKED';

// Итерация 7: режим охлаждения
export type CoolingMode = 'fast' | 'slow' | null;

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
    // Итерация 5
    is_lab_blocked: boolean;
    lab_status: LabStatus;
    lab_block_reason?: string | null;
    lab_blocked_at?: string | null;
    lab_blocked_by?: string | null;
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

// ==========================================
// SHIFT PLANNING
// ==========================================

export interface Shift {
    id: string;
    name: string;
    starts_at: string;
    ends_at: string;
    is_working: boolean;
    comment?: string | null;
}

export type ShiftTaskStatus = 'PLANNED' | 'IN_PROGRESS' | 'DONE' | 'CANCELLED';

export interface ShiftTask {
    id: string;
    batch_id?: string | null;
    batch_name?: string | null;
    product_id?: string | null;
    product_code?: string | null;
    product_name?: string | null;
    operation_name: string;
    task_role?: string | null;
    equipment_id: string;
    equipment_name: string;
    linked_equipment_id?: string | null;
    linked_equipment_name?: string | null;
    planned_start: string;
    planned_end: string;
    actual_start?: string | null;
    actual_end?: string | null;
    actual_qty?: number | null;
    material_load_at?: string | null;
    status: ShiftTaskStatus;
    duration_minutes: number;
    is_carryover: boolean;
    // Итерация 5: блокировка лабораторией
    is_lab_blocked?: boolean;
    lab_status?: LabStatus | null;
    lab_block_reason?: string | null;
    // Итерация 7: режим охлаждения
    cooling_mode?: CoolingMode;
}

export interface ShiftTasksGrouped {
    equipment_id: string;
    equipment_name: string;
    equipment_code?: string | null;
    tasks: ShiftTask[];
}

export interface ShiftTasksResponse {
    shift: Shift;
    groups: ShiftTasksGrouped[];
    total_tasks: number;
    carryover_count: number;
    done_count: number;
}

export interface TaskFactRequest {
    actual_start?: string | null;
    actual_end?: string | null;
    actual_qty?: number | null;
    material_load_at?: string | null;
    status?: ShiftTaskStatus | null;
    comment?: string | null;
}

export interface TaskFactResponse {
    id: string;
    status: ShiftTaskStatus;
    actual_start?: string | null;
    actual_end?: string | null;
    actual_qty?: number | null;
    material_load_at?: string | null;
    message: string;
}

// ==========================================
// RESCHEDULING
// ==========================================

export type RescheduleReason = 'DELAY' | 'BREAKDOWN' | 'QTY_CHANGE' | 'MANUAL';

export interface RescheduleRequest {
    from_version_id: string;
    reason: RescheduleReason;
    changes: Record<string, any>;
    frozen_before?: string | null;
    comment?: string | null;
}

export interface RescheduleResponse {
    status: string;
    from_version_id?: string | null;
    to_version_id?: string | null;
    affected_tasks: number;
    moved_tasks: number;
    frozen_tasks: number;
    message: string;
    diff: Record<string, any>;
}

export interface MovedTaskInfo {
    task_id: string;
    batch_id?: string | null;
    old_start: string;
    old_end: string;
    new_start: string;
    new_end: string;
    delta_minutes: number;
}

export interface CompareResponse {
    v1_id: string;
    v2_id: string;
    v1_task_count: number;
    v2_task_count: number;
    only_in_v1: string[];
    only_in_v2: string[];
    moved: MovedTaskInfo[];
    unchanged_count: number;
    moved_count: number;
}

export interface PinTaskRequest {
    is_pinned: boolean;
}

export interface PinTaskResponse {
    task_id: string;
    is_pinned: boolean;
    message: string;
}

// ==========================================
// MOVE TASK (Итерация 9, C2: drag-and-drop)
// ==========================================

export interface MoveTaskRequest {
    new_start: string;   // ISO datetime (например "2026-09-07T08:00:00+03:00")
    new_end: string;     // ISO datetime
}

export interface MoveTaskResponse {
    task_id: string;
    planned_start: string;
    planned_end: string;
    is_pinned: boolean;
    message: string;
}

// ==========================================
// LABORATORY
// ==========================================

export type LabAction = 'REQUESTED' | 'APPROVED' | 'BLOCKED' | 'UNBLOCKED' | 'EXTENDED';
export type LabResult = 'PASSED' | 'FAILED' | 'PENDING';

export interface LabAnalysisLogEntry {
    id: string;
    organization_id: string;
    batch_id: string;
    scheduled_task_id?: string | null;
    action: LabAction;
    result?: LabResult | null;
    reason?: string | null;
    performed_by?: string | null;
    performed_by_name?: string | null;
    performed_at: string;
    comment?: string | null;
}

export interface BatchLabStatus {
    batch_id: string;
    product_id: string;
    product_code?: string | null;
    product_name?: string | null;
    volume_kg: number;
    is_lab_blocked: boolean;
    lab_status: LabStatus;
    lab_block_reason?: string | null;
    lab_blocked_at?: string | null;
    lab_blocked_by?: string | null;
    lab_blocked_by_name?: string | null;
    equipment_name?: string | null;
}

export interface LabPendingBatch {
    batch_id: string;
    order_id: string;
    product_id: string;
    product_code?: string | null;
    product_name?: string | null;
    volume_kg: number;
    equipment_id?: string | null;
    equipment_name?: string | null;
    is_lab_blocked: boolean;
    lab_status: LabStatus;
    lab_block_reason?: string | null;
    lab_blocked_at?: string | null;
    planned_end?: string | null;
    next_lab_task_id?: string | null;
    next_lab_task_start?: string | null;
    next_lab_task_end?: string | null;
}

export interface LabActionResponse {
    batch_id: string;
    action: string;
    is_lab_blocked: boolean;
    lab_status: LabStatus;
    message: string;
    log_id?: string | null;
}

export interface BlockBatchRequest {
    reason: string;
    scheduled_task_id?: string | null;
    comment?: string | null;
}

export interface UnblockBatchRequest {
    comment?: string | null;
}

export interface ApproveBatchRequest {
    result: 'PASSED' | 'FAILED';
    comment?: string | null;
}

export interface RequestAnalysisRequest {
    comment?: string | null;
}

// ==========================================
// PERSONNEL (Итерация 6 + Итерация 7)
// ==========================================

export type PersonnelPoolType =
    | 'REACTOR_OPERATOR'
    | 'LINE_OPERATOR'
    | 'MANUAL_OPERATOR'
    | 'LAB'
    | 'COOLING_ZONE'
    | 'BOILER';

export interface PersonnelPool {
    id: string;
    organization_id: string;
    name: string;
    type: PersonnelPoolType;
    capacity: number;
    comment?: string | null;
    updated_at?: string | null;
    scheduled_count: number;
    peak_concurrent: number;
    load_percent: number;
}

export interface PersonnelPoolList {
    pools: PersonnelPool[];
    total_capacity: number;
    total_scheduled: number;
    version_id?: string | null;
    version_name?: string | null;
}

export interface PersonnelPoolUpdate {
    name?: string;
    capacity?: number;
    comment?: string;
}

export interface PersonnelLoadItem {
    type: PersonnelPoolType;
    capacity: number;
    peak: number;
    load_percent: number;
}

// ==========================================
// ЧЕСТНЫЙ ЗНАК (Итерация 8)
// ==========================================

export type CzStatus = 'NOT_APPLICABLE' | 'PENDING' | 'IN_PROGRESS' | 'COMPLETED';

export interface CzScanRequest {
    cz_code: string;
    gtin?: string | null;
    batch_id?: string | null;
    task_id?: string | null;
    line_code?: string | null;
    camera_id?: string | null;
    scanned_at?: string | null;
    qty?: number;
    comment?: string | null;
}

export interface CzScanResponse {
    id: string;
    cz_code: string;
    batch_id?: string | null;
    scheduled_task_id?: string | null;
    qty: number;
    duplicate: boolean;
    resolved: boolean;
    message: string;
}

export interface CzAttachRequest {
    batch_id?: string | null;
    task_id?: string | null;
    comment?: string | null;
}

export interface CzProgress {
    batch_id: string;
    product_id: string;
    product_code?: string | null;
    product_name?: string | null;
    planned_qty?: number | null;
    marked_qty: number;
    progress_percent: number;
    cz_status: CzStatus;
    threshold: number;
    last_scan_at?: string | null;
    scans_count: number;
}

export interface CzScanLogEntry {
    id: string;
    organization_id: string;
    batch_id?: string | null;
    scheduled_task_id?: string | null;
    cz_code: string;
    gtin?: string | null;
    qty: number;
    line_code?: string | null;
    camera_id?: string | null;
    scanned_at: string;
    created_at: string;
    comment?: string | null;
    batch_name?: string | null;
    product_code?: string | null;
    product_name?: string | null;
}

export interface CzPendingBatch {
    batch_id: string;
    order_id: string;
    product_id: string;
    product_code?: string | null;
    product_name?: string | null;
    equipment_name?: string | null;
    volume_kg: number;
    cz_status: CzStatus;
    marked_qty: number;
    planned_qty?: number | null;
    progress_percent: number;
    last_scan_at?: string | null;
}

export interface CzStats {
    total_batches: number;
    not_applicable: number;
    pending: number;
    in_progress: number;
    completed: number;
    total_scans: number;
    unresolved_scans: number;
    threshold: number;
}

export interface CzActionResponse {
    id: string;
    message: string;
    resolved: boolean;
}