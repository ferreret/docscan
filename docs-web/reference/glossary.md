# :material-book-alphabet: Glosario

| Término | Definición |
|---------|-----------|
| **Aplicación** | Perfil de procesamiento independiente con pipeline, campos y transferencia propios |
| **Grupo (launcher)** | Agrupación opcional de aplicaciones en el launcher, con cabecera plegable. Se fija en Configurador → General |
| **Lote (Batch)** | Conjunto de páginas capturadas o importadas que se procesan y transfieren juntas. Se guarda en la base de datos y puede reabrirse desde la Gestión de lotes |
| **Documento** | Tramo de páginas que va de una página separadora a la siguiente. No se guarda: se calcula al vuelo a partir de las marcas de página, así que reordenar o desmarcar páginas lo cambia solo |
| **Separador (página separadora)** | Página marcada como inicio de un documento (`is_separator`), con un valor opcional que lo identifica (`separator_value`). Lo marca el paso Barcode, un script o el operador (`Ctrl+D`). Es una propiedad de la página, no un rol del código de barras |
| **Documento implícito** | Las páginas anteriores al primer separador. Un lote sin separadores es un único documento implícito, sin valor |
| **Hoja separadora** | Página separadora que se descarta al transferir (*Página separadora: Se descarta*). Con *Se incluye*, la separadora es la portada del documento |
| **Página excluida** | Página marcada con `Ctrl+M`: sigue en el lote pero no se transfiere ni llega a los scripts de transferencia |
| **Pipeline** | Secuencia ordenada de pasos que procesa cada página |
| **Paso (Step)** | Operación individual: imagen, barcode, OCR o script |
| **Workbench** | Ventana de explotación para captura y procesamiento |
| **Launcher** | Ventana principal con lista de aplicaciones |
| **Configurador** | Diálogo de 7 pestañas para configurar aplicaciones: General, Imagen, Campos de Lote, Pipeline, Eventos, Transferencia y Notificaciones |
| **Evento pausado** | Evento con la casilla «Activado» desmarcada: conserva el código pero no se compila ni se ejecuta |
| **Panel de verificación** | Panel propio de una aplicación, escrito en Python (subclase de `VerificationPanel`), que se muestra en la pestaña Verificación del Workbench y puede bloquear la transferencia |
| **Barra del visor** | Franja bajo el visor con zoom, rotación, exclusión, separador, borrado y el contador de página. El visor resalta los barcodes con un recuadro |
| **Transferencia** | Exportación de documentos procesados al destino |
| **Agrupación** | En PDF, PDF/A y TIFF multipágina: un fichero por lote o un fichero por documento |
| **Script de nombre** | Función `file_name(page, document, batch, app)` que da la subruta de cada fichero cuando el nombre es *por script* en lugar de por patrón |
| **Worker desatendido** | Proceso sin interfaz (`python -m docscan_worker`) que vigila una carpeta o procesa lotes pendientes y los transfiere por el mismo camino que el Workbench |
| **Modo directo** | Arranque `main.py --direct-mode "Aplicación"`: escanea, procesa y transfiere sin abrir ventanas |
| **AI Mode** | Asistente conversacional con IA generativa |
| **Motor 1 (pyzbar)** | Motor de barcodes rápido, 10 simbologías (1D, EAN/UPC y QR) |
| **Motor 2 (zxing-cpp)** | Motor de barcodes avanzado, 15 simbologías (añade PDF417, DataMatrix, Aztec, MaxiCode y Micro QR) |
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
