# :material-book-alphabet: Glosario

| Término | Definición |
|---------|-----------|
| **Aplicación** | Perfil de procesamiento independiente con pipeline, campos y transferencia propios |
| **Lote (Batch)** | Conjunto de páginas escaneadas/importadas en una sesión |
| **Pipeline** | Secuencia ordenada de pasos que procesa cada página |
| **Paso (Step)** | Operación individual: imagen, barcode, OCR o script |
| **Workbench** | Ventana de explotación para captura y procesamiento |
| **Launcher** | Ventana principal con lista de aplicaciones |
| **Configurador** | Diálogo de 6 pestañas para configurar aplicaciones |
| **Overlay** | Marcador visual sobre el visor (barcodes, regiones OCR) |
| **Transferencia** | Exportación de documentos procesados al destino |
| **AI Mode** | Asistente conversacional con IA generativa |
| **Motor 1 (pyzbar)** | Motor de barcodes rápido, 12 simbologías |
| **Motor 2 (zxing-cpp)** | Motor de barcodes avanzado, 14 simbologías |
| **RapidOCR** | Motor OCR principal, offline, ONNX Runtime |
| **EasyOCR** | Motor OCR alternativo, PyTorch, alta precisión |
| **Tesseract** | Motor OCR fallback, ligero |
| **SANE** | Scanner Access Now Easy — interfaz de escáneres en Linux |
| **TWAIN/WIA** | Interfaces de escáneres en Windows |
| **Fernet** | Cifrado AES-128-CBC + HMAC-SHA256 para API keys |
| **WAL mode** | Write-Ahead Logging — modo de SQLite para concurrencia |
| **PDF/A** | Formato PDF para archivo a largo plazo |
| **ScriptStep** | Paso del pipeline con lógica Python personalizada |
| **PipelineContext** | Objeto de control de flujo disponible en scripts |
