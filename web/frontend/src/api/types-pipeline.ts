// Tipos del dominio pipeline (compartidos entre store, vistas y forms).

export type StepType = 'image_op' | 'barcode' | 'ocr' | 'script'

export interface BasePipelineStep {
  id: string
  type: StepType
  enabled: boolean
}

export interface BarcodeStep extends BasePipelineStep {
  type: 'barcode'
  engine: 'motor1' | 'motor2'
  symbologies: string[]
  regex: string
  regex_include_symbology: boolean
  orientations: string[]
  quality_threshold: number
  window: [number, number, number, number] | null
}

export interface ImageOpStep extends BasePipelineStep {
  type: 'image_op'
  op: string
  params: Record<string, unknown>
  window: [number, number, number, number] | null
}

export interface OcrStep extends BasePipelineStep {
  type: 'ocr'
  engine: 'rapidocr' | 'easyocr' | 'tesseract'
  languages: string[]
  full_page: boolean
  window: [number, number, number, number] | null
}

// Union para el resto de tipos: en v1 solo se leen, no se editan.
export interface GenericStep extends BasePipelineStep {
  [key: string]: unknown
}

export type PipelineStep = BarcodeStep | ImageOpStep | OcrStep | GenericStep

export interface PipelineResponse {
  steps: PipelineStep[]
}

// Opciones de simbología soportadas por pyzbar/zxing-cpp (referencia).
export const SYMBOLOGIES = [
  'CODE128',
  'CODE39',
  'EAN13',
  'EAN8',
  'QRCODE',
  'DATAMATRIX',
  'PDF417',
  'AZTEC',
  'ITF',
  'UPCA',
  'UPCE',
] as const
