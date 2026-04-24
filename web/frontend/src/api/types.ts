// Tipos TypeScript que reflejan los schemas de la API REST.

export interface Paginated<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}


export interface TokenResponse {
  access_token: string
  token_type: string
}

export interface LoginRequest {
  email: string
  password: string
}

export interface RegisterRequest {
  email: string
  password: string
  display_name: string
  tenant_name: string
}

export interface UserResponse {
  id: number
  email: string
  display_name: string
  role: string
  tenant_id: number
  tenant_name: string
}

// --- Applications ---

export interface ApplicationListItem {
  id: number
  name: string
  description: string
  active: boolean
  output_format: string
  created_at: string
}

export interface ApplicationResponse extends ApplicationListItem {
  tenant_id: number | null
  pipeline_json: string
  events_json: string
  transfer_json: string
  batch_fields_json: string
  index_fields_json: string
  auto_transfer: boolean
  close_after_transfer: boolean
  background_color: string
  default_tab: string
  scanner_backend: string
  image_config_json: string
  ai_config_json: string
  updated_at: string
}

export interface ApplicationCreate {
  name: string
  description?: string
  pipeline_json?: string
  events_json?: string
  transfer_json?: string
  batch_fields_json?: string
  index_fields_json?: string
  auto_transfer?: boolean
  output_format?: string
}

export interface ApplicationUpdate {
  name?: string
  description?: string
  active?: boolean
  pipeline_json?: string
  events_json?: string
  transfer_json?: string
  batch_fields_json?: string
  index_fields_json?: string
  auto_transfer?: boolean
  close_after_transfer?: boolean
  background_color?: string
  default_tab?: string
  scanner_backend?: string
  output_format?: string
  image_config_json?: string
  ai_config_json?: string
}

// --- Batches ---

export interface BatchListItem {
  id: number
  application_id: number
  state: string
  page_count: number
  created_at: string
  updated_at: string
}

export interface BatchResponse extends BatchListItem {
  tenant_id: number | null
  folder_path: string
  hostname: string
  username: string
  fields_json: string
  stats_json: string
}

export interface BatchCreate {
  application_id: number
  folder_path?: string
  fields_json?: string
}

// --- Pages ---

export interface PageListItem {
  id: number
  batch_id: number
  page_index: number
  needs_review: boolean
  review_reason: string
  is_blank: boolean
  is_excluded: boolean
  pipeline_processed: boolean
  created_at: string
}

export interface BarcodeResponse {
  id: number
  value: string
  symbology: string
  engine: string
  step_id: string
  quality: number
  pos_x: number
  pos_y: number
  pos_w: number
  pos_h: number
  role: string
}

export interface PageResponse extends PageListItem {
  image_path: string
  ocr_text: string
  index_fields_json: string
  review_reason: string
  is_excluded: boolean
  processing_errors_json: string
  script_errors_json: string
  barcodes: BarcodeResponse[]
  updated_at: string
}

export interface PageUploadResponse {
  created: PageResponse[]
  batch_page_count: number
}

// --- Team ---

export interface TeamUser {
  id: number
  email: string
  display_name: string
  role: string
  active: boolean
  created_at: string
}

export interface Invitation {
  id: number
  email: string
  role: string
  token: string
  expires_at: string
  accepted_at: string | null
  created_at: string
}
