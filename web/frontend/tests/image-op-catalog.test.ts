import { describe, it, expect } from 'vitest'
import {
  IMAGE_OP_CATALOG,
  CATEGORY_LABELS,
  type Category,
} from '@/api/image-op-catalog'

// Lista esperada, sincronizada manualmente con app/services/image_pipeline.py::IMAGE_OPS.
// Si el backend añade/quita ops, actualizar esta lista y el catálogo a la vez.
const EXPECTED_OPS = [
  'AutoDeskew',
  'ConvertTo1Bpp',
  'Crop',
  'CropBlackBorders',
  'CropWhiteBorders',
  'FloodFill',
  'FxDespeckle',
  'FxDilate',
  'FxEqualizeIntensity',
  'FxErode',
  'FxGrayscale',
  'FxNegative',
  'KeepChannel',
  'RemoveChannel',
  'RemoveHolePunch',
  'RemoveLines',
  'Resize',
  'Rotate',
  'RotateAngle',
  'ScaleChannel',
  'SetBrightness',
  'SetContrast',
  'SetResolution',
  'SwapColor',
] as const

describe('IMAGE_OP_CATALOG', () => {
  it('contiene exactamente las 24 operaciones esperadas', () => {
    const names = IMAGE_OP_CATALOG.map((op) => op.name).sort()
    expect(names).toEqual([...EXPECTED_OPS].sort())
  })

  it('cada operación tiene label, description y category', () => {
    for (const op of IMAGE_OP_CATALOG) {
      expect(op.label).toBeTruthy()
      expect(op.description).toBeTruthy()
      expect(CATEGORY_LABELS[op.category]).toBeTruthy()
    }
  })

  it('cada field tiene default definido y los enums tienen opciones', () => {
    for (const op of IMAGE_OP_CATALOG) {
      for (const f of op.fields) {
        expect(f.default).toBeDefined()
        if (f.type === 'enum') {
          expect(f.options).toBeDefined()
          expect(f.options!.length).toBeGreaterThan(0)
        }
      }
    }
  })

  it('los fields numéricos con min y max cumplen min <= max', () => {
    for (const op of IMAGE_OP_CATALOG) {
      for (const f of op.fields) {
        if (
          (f.type === 'int' || f.type === 'float') &&
          f.min !== undefined &&
          f.max !== undefined
        ) {
          expect(f.min).toBeLessThanOrEqual(f.max)
        }
      }
    }
  })

  it('CATEGORY_LABELS cubre todas las categorías usadas', () => {
    const usedCategories = new Set(IMAGE_OP_CATALOG.map((op) => op.category))
    for (const cat of usedCategories) {
      expect(CATEGORY_LABELS[cat as Category]).toBeTruthy()
    }
  })
})
