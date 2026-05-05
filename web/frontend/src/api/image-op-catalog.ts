// Catálogo de operaciones de imagen (ImageOp). Fuente de verdad del frontend.
// Sincronizado manualmente con app/services/image_pipeline.py::IMAGE_OPS.

export type FieldType =
  | 'int' | 'float' | 'enum' | 'bool' | 'point' | 'color'

export type Category =
  | 'geometry' | 'color' | 'cleanup'
  | 'morphology' | 'channels' | 'effects'

export interface FieldSchema {
  key: string
  type: FieldType
  label: string
  default: unknown
  min?: number
  max?: number
  step?: number
  options?: { value: string | number; label: string }[]
  help?: string
}

export interface OpSchema {
  name: string
  label: string
  category: Category
  description: string
  fields: FieldSchema[]
}

export const CATEGORY_LABELS: Record<Category, string> = {
  geometry: 'Geometría',
  color: 'Color y tono',
  cleanup: 'Limpieza',
  morphology: 'Morfología',
  channels: 'Canales',
  effects: 'Efectos',
}

export const IMAGE_OP_CATALOG: OpSchema[] = [
  // --- Geometría ---
  {
    name: 'AutoDeskew',
    label: 'Corregir inclinación',
    category: 'geometry',
    description: 'Detecta y corrige la inclinación de la imagen automáticamente.',
    fields: [],
  },
  {
    name: 'Crop',
    label: 'Recortar región',
    category: 'geometry',
    description: 'Recorta una región rectangular definida por X, Y, ancho y alto.',
    fields: [
      { key: 'x', type: 'int', label: 'X', default: 0, min: 0 },
      { key: 'y', type: 'int', label: 'Y', default: 0, min: 0 },
      { key: 'w', type: 'int', label: 'Ancho', default: 100, min: 1 },
      { key: 'h', type: 'int', label: 'Alto', default: 100, min: 1 },
    ],
  },
  {
    name: 'Resize',
    label: 'Redimensionar',
    category: 'geometry',
    description: 'Cambia el tamaño por escala o a un tamaño absoluto.',
    fields: [
      { key: 'scale', type: 'float', label: 'Escala', default: 1.0, min: 0.01, max: 10, step: 0.1 },
      { key: 'width', type: 'int', label: 'Ancho (px)', default: 800, min: 1 },
      { key: 'height', type: 'int', label: 'Alto (px)', default: 600, min: 1 },
    ],
  },
  {
    name: 'Rotate',
    label: 'Rotar 90° / 180° / 270°',
    category: 'geometry',
    description: 'Rota la imagen en incrementos de 90 grados.',
    fields: [
      {
        key: 'degrees',
        type: 'enum',
        label: 'Grados',
        default: 90,
        options: [
          { value: 90, label: '90°' },
          { value: 180, label: '180°' },
          { value: 270, label: '270°' },
        ],
      },
    ],
  },
  {
    name: 'RotateAngle',
    label: 'Rotar ángulo libre',
    category: 'geometry',
    description: 'Rota un ángulo arbitrario en grados.',
    fields: [
      { key: 'angle', type: 'float', label: 'Ángulo (°)', default: 0, min: -360, max: 360, step: 0.1 },
    ],
  },

  // --- Color y tono ---
  {
    name: 'FxGrayscale',
    label: 'Convertir a escala de grises',
    category: 'color',
    description: 'Convierte la imagen a escala de grises.',
    fields: [],
  },
  {
    name: 'FxNegative',
    label: 'Invertir (negativo)',
    category: 'color',
    description: 'Invierte los colores de la imagen.',
    fields: [],
  },
  {
    name: 'FxEqualizeIntensity',
    label: 'Ecualizar intensidad',
    category: 'color',
    description: 'Ecualiza el histograma de intensidad.',
    fields: [],
  },
  {
    name: 'SetBrightness',
    label: 'Ajustar brillo',
    category: 'color',
    description: 'Suma un valor constante al brillo (-100 a 100).',
    fields: [
      { key: 'value', type: 'int', label: 'Valor', default: 0, min: -100, max: 100 },
    ],
  },
  {
    name: 'SetContrast',
    label: 'Ajustar contraste',
    category: 'color',
    description: 'Multiplica la intensidad por un factor.',
    fields: [
      { key: 'factor', type: 'float', label: 'Factor', default: 1.0, min: 0, max: 3, step: 0.1 },
    ],
  },

  // --- Limpieza ---
  {
    name: 'ConvertTo1Bpp',
    label: 'Convertir a 1 bit',
    category: 'cleanup',
    description: 'Binariza la imagen con un umbral configurable.',
    fields: [
      { key: 'threshold', type: 'int', label: 'Umbral', default: 128, min: 0, max: 255 },
    ],
  },
  {
    name: 'RemoveLines',
    label: 'Eliminar líneas',
    category: 'cleanup',
    description: 'Elimina líneas horizontales, verticales o ambas.',
    fields: [
      {
        key: 'direction',
        type: 'enum',
        label: 'Dirección',
        default: 'HV',
        options: [
          { value: 'H', label: 'Horizontales' },
          { value: 'V', label: 'Verticales' },
          { value: 'HV', label: 'Ambas' },
        ],
      },
    ],
  },
  {
    name: 'FxDespeckle',
    label: 'Despeckle (mediana)',
    category: 'cleanup',
    description: 'Elimina ruido con un filtro de mediana.',
    fields: [
      { key: 'kernel_size', type: 'int', label: 'Tamaño kernel (impar)', default: 3, min: 1, max: 21 },
    ],
  },
  {
    name: 'CropWhiteBorders',
    label: 'Recortar bordes blancos',
    category: 'cleanup',
    description: 'Elimina bordes blancos alrededor del contenido.',
    fields: [
      { key: 'margin', type: 'int', label: 'Margen (px)', default: 5, min: 0 },
    ],
  },
  {
    name: 'CropBlackBorders',
    label: 'Recortar bordes negros',
    category: 'cleanup',
    description: 'Elimina bordes negros alrededor del contenido.',
    fields: [
      { key: 'margin', type: 'int', label: 'Margen (px)', default: 5, min: 0 },
    ],
  },
  {
    name: 'RemoveHolePunch',
    label: 'Eliminar perforaciones',
    category: 'cleanup',
    description: 'Detecta y tapa marcas circulares de perforadora.',
    fields: [
      { key: 'min_radius', type: 'int', label: 'Radio mínimo (px)', default: 10, min: 1 },
      { key: 'max_radius', type: 'int', label: 'Radio máximo (px)', default: 30, min: 1 },
    ],
  },

  // --- Morfología ---
  {
    name: 'FxDilate',
    label: 'Dilatar',
    category: 'morphology',
    description: 'Dilatación morfológica (engrosa).',
    fields: [
      { key: 'kernel_size', type: 'int', label: 'Tamaño kernel', default: 3, min: 1, max: 15 },
      { key: 'iterations', type: 'int', label: 'Iteraciones', default: 1, min: 1, max: 10 },
    ],
  },
  {
    name: 'FxErode',
    label: 'Erosionar',
    category: 'morphology',
    description: 'Erosión morfológica (adelgaza).',
    fields: [
      { key: 'kernel_size', type: 'int', label: 'Tamaño kernel', default: 3, min: 1, max: 15 },
      { key: 'iterations', type: 'int', label: 'Iteraciones', default: 1, min: 1, max: 10 },
    ],
  },

  // --- Canales ---
  {
    name: 'KeepChannel',
    label: 'Mantener canal',
    category: 'channels',
    description: 'Extrae un canal individual (R, G o B).',
    fields: [
      {
        key: 'channel',
        type: 'enum',
        label: 'Canal',
        default: 'R',
        options: [
          { value: 'R', label: 'Rojo (R)' },
          { value: 'G', label: 'Verde (G)' },
          { value: 'B', label: 'Azul (B)' },
        ],
      },
    ],
  },
  {
    name: 'RemoveChannel',
    label: 'Eliminar canal',
    category: 'channels',
    description: 'Pone a cero un canal (R, G o B).',
    fields: [
      {
        key: 'channel',
        type: 'enum',
        label: 'Canal',
        default: 'R',
        options: [
          { value: 'R', label: 'Rojo (R)' },
          { value: 'G', label: 'Verde (G)' },
          { value: 'B', label: 'Azul (B)' },
        ],
      },
    ],
  },
  {
    name: 'ScaleChannel',
    label: 'Escalar canal',
    category: 'channels',
    description: 'Multiplica un canal por un factor.',
    fields: [
      {
        key: 'channel',
        type: 'enum',
        label: 'Canal',
        default: 'R',
        options: [
          { value: 'R', label: 'Rojo (R)' },
          { value: 'G', label: 'Verde (G)' },
          { value: 'B', label: 'Azul (B)' },
        ],
      },
      { key: 'factor', type: 'float', label: 'Factor', default: 1.0, min: 0, max: 2, step: 0.1 },
    ],
  },

  // --- Efectos ---
  {
    name: 'FloodFill',
    label: 'Rellenar desde punto',
    category: 'effects',
    description: 'Relleno por inundación desde un punto de origen.',
    fields: [
      { key: 'x', type: 'int', label: 'Origen X', default: 0, min: 0 },
      { key: 'y', type: 'int', label: 'Origen Y', default: 0, min: 0 },
      { key: 'color', type: 'color', label: 'Color', default: [255, 255, 255] },
    ],
  },
  {
    name: 'SwapColor',
    label: 'Intercambiar color',
    category: 'effects',
    description: 'Sustituye un color por otro con tolerancia.',
    fields: [
      { key: 'from', type: 'color', label: 'Color origen', default: [0, 0, 0] },
      { key: 'to', type: 'color', label: 'Color destino', default: [255, 255, 255] },
      { key: 'tolerance', type: 'int', label: 'Tolerancia', default: 10, min: 0, max: 50 },
    ],
  },
  {
    name: 'SetResolution',
    label: 'Fijar resolución (DPI)',
    category: 'effects',
    description: 'Marca la resolución para el guardado (no redimensiona).',
    fields: [],
  },
]
