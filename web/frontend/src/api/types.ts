// Tipos TypeScript que reflejan los schemas de la API REST.

export interface Paginated<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface UserResponse {
  id: number;
  email: string;
  display_name: string;
  role: string;
  tenant_id: number;
  tenant_name: string;
}

// --- Applications ---

export interface ApplicationListItem {
  id: number;
  name: string;
  description: string;
  active: boolean;
  output_format: string;
  created_at: string;
}

export interface ApplicationResponse extends ApplicationListItem {
  tenant_id: number | null;
  pipeline_json: string;
  events_json: string;
  transfer_json: string;
  batch_fields_json: string;
  index_fields_json: string;
  auto_transfer: boolean;
  close_after_transfer: boolean;
  background_color: string;
  default_tab: string;
  scanner_backend: string;
  image_config_json: string;
  ai_config_json: string;
  updated_at: string;
}

export interface ApplicationCreate {
  name: string;
  description?: string;
  pipeline_json?: string;
  events_json?: string;
  transfer_json?: string;
  batch_fields_json?: string;
  index_fields_json?: string;
  auto_transfer?: boolean;
  output_format?: string;
}

export interface ApplicationUpdate {
  name?: string;
  description?: string;
  active?: boolean;
  pipeline_json?: string;
  events_json?: string;
  transfer_json?: string;
  batch_fields_json?: string;
  index_fields_json?: string;
  auto_transfer?: boolean;
  close_after_transfer?: boolean;
  background_color?: string;
  default_tab?: string;
  scanner_backend?: string;
  output_format?: string;
  image_config_json?: string;
  ai_config_json?: string;
}

// --- Batches ---

export interface BatchListItem {
  id: number;
  application_id: number;
  state: string;
  page_count: number;
  created_at: string;
  updated_at: string;
}

export interface BatchResponse extends BatchListItem {
  tenant_id: number | null;
  folder_path: string;
  hostname: string;
  username: string;
  fields_json: string;
  stats_json: string;
}

export interface BatchCreate {
  application_id: number;
  folder_path?: string;
  fields_json?: string;
}

// --- Pages ---

export interface PageListItem {
  id: number;
  batch_id: number;
  page_index: number;
  needs_review: boolean;
  review_reason: string;
  is_blank: boolean;
  is_excluded: boolean;
  pipeline_processed: boolean;
  barcodes_count: number;
  created_at: string;
}

export interface BarcodeResponse {
  id: number;
  value: string;
  symbology: string;
  engine: string;
  step_id: string;
  quality: number;
  pos_x: number;
  pos_y: number;
  pos_w: number;
  pos_h: number;
  role: string;
}

export interface PageResponse extends PageListItem {
  image_path: string;
  ocr_text: string;
  index_fields_json: string;
  review_reason: string;
  is_excluded: boolean;
  processing_errors_json: string;
  script_errors_json: string;
  barcodes: BarcodeResponse[];
  updated_at: string;
}

export interface PageUploadResponse {
  created: PageResponse[];
  batch_page_count: number;
}

// --- Team ---

export interface TeamUser {
  id: number;
  email: string;
  display_name: string;
  role: string;
  active: boolean;
  created_at: string;
}

export interface Invitation {
  id: number;
  email: string;
  role: string;
  token: string;
  expires_at: string;
  accepted_at: string | null;
  created_at: string;
}

// --- Admin (superadmin cross-tenant) ---

export interface TenantStats {
  n_users: number;
  n_applications: number;
  n_batches: number;
}

export interface TenantListItem {
  id: number;
  name: string;
  slug: string;
  plan: string;
  active: boolean;
  created_at: string;
  stats: TenantStats;
}

export interface TenantUserItem {
  id: number;
  email: string;
  display_name: string;
  role: string;
  active: boolean;
  created_at: string;
}

export interface TenantDetail extends TenantListItem {
  users: TenantUserItem[];
}

export interface TenantCreateRequest {
  tenant_name: string;
  plan: string;
  admin_email: string;
  admin_password: string;
  admin_display_name: string;
}

export interface TenantUpdateRequest {
  name?: string;
  plan?: string;
  active?: boolean;
}

export interface AdminUserListItem {
  id: number;
  email: string;
  display_name: string;
  role: string;
  active: boolean;
  created_at: string;
  tenant_id: number;
  tenant_name: string;
}

export interface AdminUserCreateRequest {
  tenant_id: number;
  email: string;
  password: string;
  display_name: string;
  role: string;
}

export interface AdminUserUpdateRequest {
  role?: string;
  active?: boolean;
  display_name?: string;
}

// --- Events ---

export interface EventFireIn {
  page_id?: number | null;
  key?: string | null;
  extra?: Record<string, unknown>;
}

export interface EventResult {
  executed: boolean;
  result: unknown;
  cancel: boolean;
  target_page_id: number | null;
  fields_updated: Record<string, unknown>;
  batch_fields_updated: Record<string, unknown>;
  logs: { level: string; message: string }[];
  error: string | null;
}
