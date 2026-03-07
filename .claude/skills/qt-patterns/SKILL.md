---
name: qt-patterns
description: Patrones obligatorios de PySide6 para DocScan Studio. Usar al implementar cualquier componente de UI, workers, señales o interacción con el event loop de Qt.
---

## Regla fundamental
NUNCA bloquear el hilo principal de UI. Todo I/O, procesado de imágenes,
pipeline y transferencia van en QThread.

## Worker pattern obligatorio
```python
class PipelineWorker(QThread):
    progress = Signal(int, str)
    finished = Signal(object)
    error = Signal(str)

    def run(self):
        try:
            result = self._execute()
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))
```

## Prohibido
- time.sleep() en el hilo de UI
- Llamadas bloqueantes (httpx sync, sqlite sin WAL) desde UI
- Acceder a widgets desde un QThread (solo via Signal)

## Convenciones de nombrado
- Signals: snake_case, verbo en pasado (scan_completed, page_processed)
- Slots: on_ + nombre_signal (on_scan_completed)
- Workers: nombre descriptivo + Worker (PipelineWorker, TransferWorker)