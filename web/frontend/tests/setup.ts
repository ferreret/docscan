// Setup global para Vitest.
// Node 25 expone un `localStorage` experimental incompleto (sin getItem/setItem/clear)
// que gana la precedencia frente al Storage de jsdom. Instalamos un polyfill mínimo
// compatible con la API Web Storage para que los tests puedan usar localStorage.*
// sin tocar el entorno jsdom.

class MemStorage implements Storage {
  private _data: Record<string, string> = {}

  get length(): number {
    return Object.keys(this._data).length
  }

  clear(): void {
    this._data = {}
  }

  getItem(key: string): string | null {
    return Object.prototype.hasOwnProperty.call(this._data, key) ? this._data[key] : null
  }

  key(index: number): string | null {
    const keys = Object.keys(this._data)
    return index >= 0 && index < keys.length ? keys[index] : null
  }

  removeItem(key: string): void {
    delete this._data[key]
  }

  setItem(key: string, value: string): void {
    this._data[key] = String(value)
  }
}

function hasStorageApi(obj: unknown): obj is Storage {
  return typeof (obj as { clear?: unknown })?.clear === 'function'
}

if (!hasStorageApi(globalThis.localStorage)) {
  Object.defineProperty(globalThis, 'localStorage', {
    value: new MemStorage(),
    writable: true,
    configurable: true,
  })
}

if (typeof window !== 'undefined' && !hasStorageApi(window.localStorage)) {
  Object.defineProperty(window, 'localStorage', {
    value: globalThis.localStorage,
    writable: true,
    configurable: true,
  })
}

// jsdom no implementa ResizeObserver. Mock no-op para que los componentes
// que lo usan (DocumentViewer) no exploten en runtime de tests.
if (typeof globalThis.ResizeObserver === 'undefined') {
  class MockResizeObserver {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  }
  Object.defineProperty(globalThis, 'ResizeObserver', {
    value: MockResizeObserver,
    writable: true,
    configurable: true,
  })
}
