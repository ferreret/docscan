# DocScan Studio — Informe de Proyecto
**Fecha**: 10 de marzo de 2026
**Versión del documento**: 1.0
**Estado del proyecto**: En desarrollo — Fase avanzada (91% completado)

---

## 1. Resumen Ejecutivo

DocScan Studio es una aplicación de escritorio para la **captura masiva, procesamiento automático e indexación inteligente de documentos**. Está diseñada para sustituir y modernizar el sistema actual basado en Flexibar.NET, incorporando capacidades de **inteligencia artificial generativa** (Claude de Anthropic, GPT-4o de OpenAI), **reconocimiento óptico de caracteres (OCR)** y **lectura avanzada de códigos de barras**.

El sistema permite digitalizar documentos desde escáneres físicos o importar archivos existentes (imágenes, PDFs), procesarlos automáticamente mediante un pipeline configurable, extraer información relevante y transferir los resultados a sistemas externos (carpetas de red, APIs, bases de datos, gestores documentales).

**Estado actual**: 20 de 22 fases de implementación completadas, con 67 módulos de código fuente (9.086 líneas), 409 tests automatizados pasando exitosamente, y la aplicación operativa para escenarios de captura, procesamiento y gestión de lotes.

---

## 2. Objetivos del Proyecto

### 2.1 Objetivo Principal
Desarrollar una plataforma de digitalización documental moderna, flexible y extensible que permita a las organizaciones automatizar sus flujos de captura e indexación de documentos.

### 2.2 Objetivos Específicos

| # | Objetivo | Beneficio |
|---|----------|-----------|
| 1 | **Multi-aplicación**: múltiples perfiles de proceso independientes | Un mismo software sirve para diferentes tipos de documento y flujos de trabajo |
| 2 | **Pipeline configurable**: procesamiento definible sin programación | Los administradores configuran el flujo de procesamiento visualmente |
| 3 | **IA generativa integrada**: extracción automática de campos | Reduce la intervención manual en la indexación de documentos |
| 4 | **Doble motor de barcode**: pyzbar + zxing-cpp | Mayor tasa de lectura y compatibilidad con todos los tipos de código |
| 5 | **OCR múltiple**: RapidOCR, EasyOCR, Tesseract | Flexibilidad según necesidades de precisión y velocidad |
| 6 | **Scripting Python**: automatización avanzada | Los procesos complejos se resuelven con scripts sin modificar el software |
| 7 | **Procesamiento desatendido**: worker CLI autónomo | Los lotes se pueden procesar sin intervención humana |
| 8 | **Multiplataforma**: Linux y Windows | Despliegue en la infraestructura existente |

---

## 3. Descripción Funcional

### 3.1 Módulo 1 — Lanzador de Aplicaciones

El **Launcher** es la pantalla principal del sistema. Presenta una lista de todas las aplicaciones (perfiles de proceso) configuradas, permitiendo al usuario:

- **Iniciar una aplicación** con doble-click o botón, abriendo la ventana de trabajo (Workbench)
- **Acceder al configurador** para crear o modificar aplicaciones (solo administradores)
- **Abrir el gestor de lotes** para supervisar el estado de los trabajos procesados
- **Lanzamiento por línea de comandos**: iniciar directamente una aplicación sin pasar por el launcher
- **Modo directo**: escanear y transferir automáticamente sin mostrar interfaz gráfica

**Ejemplo de uso**: Una empresa tiene configuradas las aplicaciones "Facturas Proveedor", "Albaranes de Entrega" y "Contratos Clientes". El operador abre el launcher, selecciona "Facturas Proveedor" e inmediatamente accede al entorno de trabajo configurado para ese tipo de documento.

### 3.2 Módulo 2 — Configurador de Aplicaciones

El configurador permite a los administradores definir completamente cómo se procesa cada tipo de documento. Se organiza en pestañas:

#### Pestaña General
Nombre, descripción, estado activo/inactivo, color de fondo personalizado (para distinguir visualmente aplicaciones abiertas simultáneamente), opciones de auto-transferencia y formato de imagen de salida.

#### Pestaña Campos de Lote
Define los datos que el operador introduce al iniciar un lote de escaneo. Ejemplos: fecha del lote, nombre del proveedor, número de pedido. Cada campo tiene tipo (texto, fecha, número, lista desplegable), puede ser obligatorio y validarse con expresiones regulares.

#### Pestaña de Indexación
Define los campos que se extraen **por cada página o documento**. Pueden ser introducidos manualmente, calculados automáticamente a partir de los barcodes detectados, o extraídos por IA. Ejemplos: número de factura, fecha, importe total, NIF del proveedor.

#### Pestaña Pipeline de Procesado
El corazón del sistema. Define **qué operaciones se aplican a cada página**, en qué orden:

| Tipo de paso | Descripción | Ejemplo de uso |
|--------------|-------------|----------------|
| **Operación de imagen** | Transformaciones visuales | Enderezar, convertir a blanco/negro, recortar bordes, ajustar brillo/contraste |
| **Lectura de barcode** | Detectar y leer códigos de barras | Leer Code128, QR, DataMatrix con uno o dos motores |
| **OCR** | Reconocimiento de texto | Extraer texto completo de la página o de una zona |
| **IA** | Extracción inteligente de campos | Enviar la imagen a Claude/GPT-4o para extraer datos estructurados |
| **Script** | Código Python personalizado | Asignar roles a barcodes, validar datos, conectar con sistemas externos |
| **Condición** | Evaluación de una expresión | Si no hay barcode, saltar al paso de revisión manual |
| **Petición HTTP** | Llamada a API externa | Consultar un ERP para validar un código de cliente |

El pipeline se ejecuta **automáticamente** por cada página escaneada o importada, sin intervención del operador.

**Ejemplo de pipeline para facturas**:
1. Auto-enderezar imagen
2. Convertir a escala de grises
3. Leer barcodes (Motor 1: pyzbar)
4. Leer barcodes (Motor 2: zxing-cpp)
5. Script: asignar rol "separador" si el barcode empieza con "SEP-"
6. OCR de zona superior (para número de factura)
7. IA: extraer fecha, importe y NIF con Claude Vision
8. Script: validar NIF contra base de datos

#### Pestaña IA / OCR
Configuración de credenciales de proveedores de IA (Anthropic, OpenAI), selección del proveedor por defecto y gestión de plantillas de extracción.

#### Pestaña Eventos y Scripts
Código Python que se ejecuta en momentos clave del ciclo de vida:
- Al abrir/cerrar la aplicación
- Al completar el escaneo de todas las páginas
- Antes y durante la transferencia
- Al navegar entre páginas
- Al pulsar teclas personalizadas

#### Pestaña Transferencia
Define cómo se exportan los documentos procesados:
- **Transferencia simple**: copiar archivos a una carpeta de red con reglas de subdirectorio y nombre
- **Transferencia avanzada**: script Python con acceso completo para conectar a cualquier sistema (ERP, gestor documental, API REST, SFTP, base de datos)
- Formatos de salida: TIFF, JPEG, PNG, PDF, PDF/A (con metadatos XMP)

### 3.3 Módulo 3 — Ventana de Trabajo (Workbench)

La ventana principal de operación del sistema:

```
┌─────────────┬──────────────────────────────┬─────────────────┐
│  Miniaturas │     Visor de documento        │  Panel barcodes │
│  de páginas │     (zoom, arrastre,          │  con tabla y    │
│  (scroll    │      overlays de barcodes     │  contadores     │
│   vertical) │      y campos IA)             │                 │
│             │                               │  ─────────────  │
│             │  Borde coloreado por estado:  │  Pestañas:      │
│             │  🟢 Con barcodes detectados   │  - Lote         │
│             │  🟠 Separador de documentos   │  - Indexación   │
│             │  🔵 Campos IA extraídos       │  - Verificación │
│             │  🔴 Requiere revisión manual  │                 │
│             │  ⚪ Sin procesar              │                 │
├─────────────┼──────────────────────────────┤                 │
│  Botones    │  Importar / Escáner / Zoom   │                 │
└─────────────┴──────────────────────────────┴─────────────────┘
```

**Funcionalidades clave**:
- **Adquisición**: importar imágenes (individuales, múltiples o carpeta), importar PDF, escanear desde dispositivo físico
- **Procesamiento en tiempo real**: el pipeline se ejecuta automáticamente en segundo plano por cada página, sin bloquear la interfaz
- **Visor interactivo**: zoom con rueda del ratón, arrastre, ajustar a página, zoom al 100%
- **Overlays visuales**: rectángulos semitransparentes sobre cada barcode detectado, con color según su rol
- **Panel de barcodes**: tabla detallada de todos los barcodes de la página (valor, simbología, motor, rol)
- **Contadores del lote**: total de páginas, con barcode, separadores, pendientes de revisión
- **Navegación**: primera/anterior/siguiente/última página, navegación inteligente (ir a siguiente con barcode, ir a siguiente pendiente de revisión)
- **Manipulación**: rotar, eliminar, marcar/desmarcar páginas
- **Transferencia**: exportar el lote procesado al destino configurado

### 3.4 Módulo 4 — Gestor de Lotes

Interfaz centralizada para supervisar todos los lotes procesados:

- **Lista filtrable**: por estado, aplicación, estación de trabajo, rango de fechas
- **Estados de lote**: Creado → Leído → Verificado → Listo para exportar → Exportado (+ estados de error)
- **Panel de detalle**: información general, estadísticas de procesamiento, lista de páginas, historial de operaciones
- **Modo supervisor**: acceso protegido con contraseña para operaciones avanzadas (liberar bloqueos, cambiar estados, eliminar lotes)
- **Refresco automático**: actualización periódica cada 20 segundos
- **Historial inmutable**: registro de auditoría de todas las operaciones sobre cada lote

### 3.5 Módulo 5 — Proceso Desatendido (DocScanWorker)

*[Pendiente de implementación]*

Proceso de línea de comandos que funciona sin interfaz gráfica:
- **Consume lotes automáticamente**: procesa lotes en estado "Leído" o "Listo para exportar"
- **Vigilancia de carpeta**: detecta nuevos archivos (imágenes o PDFs) en una carpeta de entrada y crea lotes automáticamente
- **Mismos motores de procesamiento**: utiliza exactamente el mismo pipeline que la interfaz gráfica
- **Notificaciones**: envía webhooks y/o emails al completar un lote

---

## 4. Arquitectura Técnica (Resumen)

### 4.1 Stack Tecnológico

| Componente | Tecnología | Justificación |
|------------|------------|---------------|
| Interfaz gráfica | PySide6 (Qt) | Framework maduro, multiplataforma, rendimiento nativo |
| Base de datos | SQLAlchemy + SQLite (modo WAL) | Sin servidor, concurrencia UI + worker |
| Barcode Motor 1 | pyzbar + OpenCV | Rápido, buen soporte 1D |
| Barcode Motor 2 | zxing-cpp | Superior en códigos 2D y múltiples códigos |
| OCR principal | RapidOCR | Ligero (~10MB), sin dependencia GPU |
| OCR alternativo | EasyOCR | Mayor precisión en textos complejos |
| IA | Anthropic SDK + OpenAI SDK | Claude Vision y GPT-4o para extracción inteligente |
| PDF | PyMuPDF | Lectura, generación y soporte PDF/A |
| Scripting | Python embebido | Scripts compilados al cargar la aplicación |
| Cifrado | Fernet (cryptography) | API keys siempre cifradas |

### 4.2 Principios de Diseño

- **La interfaz nunca se bloquea**: todo procesamiento pesado en hilos secundarios
- **Pipeline composable**: los pasos se combinan libremente sin limitaciones
- **Seguridad**: claves API cifradas, nunca en texto plano
- **Tolerancia a errores**: un error en un script no detiene el pipeline ni crashea la aplicación
- **Concurrencia**: SQLite en modo WAL permite acceso simultáneo desde la UI y el worker
- **Auditoría**: historial inmutable de todas las operaciones sobre lotes

---

## 5. Plan de Implementación

El proyecto se ha estructurado en **22 fases** organizadas de abajo hacia arriba (infraestructura → servicios → interfaz → integración):

### Fases 1-5: Infraestructura y Modelo de Datos ✅

| Fase | Descripción | Estado |
|------|-------------|--------|
| 1 | Definición de pasos del pipeline (dataclasses) | ✅ Completado |
| 2 | Contexto del pipeline (control de flujo) | ✅ Completado |
| 3 | Serialización pipeline (JSON ↔ objetos) | ✅ Completado |
| 4 | Configuración y gestión de secretos | ✅ Completado |
| 5 | Base de datos SQLite con modo WAL y repositorios | ✅ Completado |

### Fases 6-11: Servicios de Negocio ✅

| Fase | Descripción | Estado |
|------|-------------|--------|
| 6 | Modelos ORM (Aplicación, Lote, Página, Barcode, Plantilla) | ✅ Completado |
| 7 | Motor de scripts Python (compilación, ejecución, caché) | ✅ Completado |
| 8 | Pipeline de imagen (25+ operaciones de transformación) | ✅ Completado |
| 9 | Servicio de lectura de barcodes (2 motores) | ✅ Completado |
| 10 | Proveedores de IA y servicios de OCR | ✅ Completado |
| 11 | Ejecutor del pipeline (orquestación de pasos) | ✅ Completado |

### Fases 12-15: Servicios de Soporte ✅

| Fase | Descripción | Estado |
|------|-------------|--------|
| 12 | Servicio de escáner (SANE en Linux, TWAIN/WIA en Windows) | ✅ Completado |
| 13 | Servicio de importación (imágenes + PDF) | ✅ Completado |
| 14 | Servicios de lote y transferencia | ✅ Completado |
| 15 | Servicio de notificaciones (webhooks + email) | ✅ Completado |

### Fases 16-20: Interfaz de Usuario ✅

| Fase | Descripción | Estado |
|------|-------------|--------|
| 16 | Launcher (pantalla principal) | ✅ Completado |
| 17 | Configurador de aplicaciones + editor de pipeline | ✅ Completado |
| 18 | Editor de eventos y scripts | ✅ Completado |
| 19 | Workbench (ventana de trabajo con visor y workers) | ✅ Completado |
| 20 | Gestor de lotes (lista, filtros, detalle, supervisor) | ✅ Completado |

### Fases 21-22: Integración Final 🔲

| Fase | Descripción | Estado |
|------|-------------|--------|
| 21 | **DocScanWorker** — proceso CLI desatendido + vigilancia de carpeta | 🔲 Pendiente |
| 22 | **Tests adicionales** — cobertura extendida e integración | 🔲 Pendiente |

---

## 6. Estado Actual del Proyecto

### 6.1 Métricas

| Métrica | Valor |
|---------|-------|
| Fases completadas | **20 de 22** (91%) |
| Módulos de código fuente | **67 archivos Python** |
| Líneas de código (producción) | **9.086** |
| Líneas de código (tests) | **5.289** |
| Tests automatizados | **409 pasando** (0 fallando) |
| Commits | **10** |

### 6.2 Funcionalidades Operativas

Las siguientes funcionalidades están **implementadas y verificadas**:

| Funcionalidad | Detalles |
|---------------|----------|
| ✅ Launcher | Lista de aplicaciones, acceso a configurador y gestor de lotes |
| ✅ Configurador completo | 6 pestañas: general, pipeline, IA/OCR, eventos, transferencia simple y avanzada |
| ✅ Editor de pipeline | Añadir, editar, reordenar, activar/desactivar pasos de 7 tipos |
| ✅ Diálogos de paso | Formularios específicos para image_op, barcode, OCR, IA, script |
| ✅ Workbench funcional | Visor con zoom, miniaturas, panel de barcodes, panel de metadatos |
| ✅ Importación múltiple | Archivos individuales, múltiples, carpeta completa, PDF |
| ✅ Pipeline en tiempo real | Procesamiento automático en segundo plano por cada página importada |
| ✅ Detección de barcodes | Motor 1 (pyzbar) + Motor 2 (zxing-cpp), overlays visuales |
| ✅ Overlays en visor | Rectángulos semitransparentes coloreados por rol sobre cada barcode |
| ✅ Gestor de lotes | Lista con filtros, panel de detalle con 4 pestañas, modo supervisor |
| ✅ Historial de auditoría | Registro inmutable de todas las operaciones sobre lotes |
| ✅ Motor de scripts | Compilación, ejecución con contexto completo, caché por ID |
| ✅ 25+ operaciones de imagen | Deskew, crop, rotate, brightness, contrast, despeckle, etc. |
| ✅ Servicios de transferencia | Simple (carpeta) y avanzada (script Python) |
| ✅ Cifrado de credenciales | API keys protegidas con Fernet |
| ✅ Base de datos WAL | Concurrencia entre UI y worker sin conflictos |

### 6.3 Funcionalidades Pendientes

| Funcionalidad | Fase | Descripción |
|---------------|------|-------------|
| 🔲 DocScanWorker | 21 | Proceso CLI para procesamiento desatendido de lotes |
| 🔲 Folder-watch | 21 | Vigilancia automática de carpeta de entrada con watchdog |
| 🔲 Notificaciones automatizadas | 21 | Webhooks y emails al completar lotes en modo desatendido |
| 🔲 Tests de integración | 22 | Cobertura extendida de flujos end-to-end |

### 6.4 Funcionalidades Configuradas pero Pendientes de Validación en Producción

Estas funcionalidades están implementadas a nivel de código pero requieren validación con entornos y equipos reales:

- Conexión con escáneres físicos (SANE en Linux, TWAIN/WIA en Windows)
- Extracción con IA generativa (requiere claves API de Anthropic/OpenAI)
- OCR con EasyOCR (requiere descarga de modelos PyTorch)
- Generación de PDF/A con metadatos XMP
- Transferencia avanzada a sistemas externos

---

## 7. Hitos y Cronograma

### Hitos Completados

| Hito | Fecha | Descripción |
|------|-------|-------------|
| H1 | Completado | Infraestructura base: pipeline, base de datos, modelos |
| H2 | Completado | Servicios de negocio: barcode, OCR, IA, scripts, imagen |
| H3 | Completado | Interfaz de usuario: launcher, configurador, workbench, gestor |
| H4 | Completado | Integración: pipeline ejecutándose en tiempo real desde la UI |

### Hitos Pendientes

| Hito | Descripción | Esfuerzo estimado |
|------|-------------|-------------------|
| H5 | DocScanWorker + folder-watch | 1 fase |
| H6 | Tests de integración y cobertura extendida | 1 fase |
| H7 | Validación con escáneres y entornos reales | Variable |

---

## 8. Casos de Uso Principales

### Caso 1: Digitalización de facturas con separación automática
1. El operador abre la aplicación "Facturas Proveedor"
2. Coloca un lote de facturas en el escáner (con hojas separadoras entre facturas)
3. Pulsa "Escanear" → las páginas se capturan y procesan automáticamente
4. El pipeline detecta los barcodes separadores y agrupa las páginas por documento
5. La IA extrae automáticamente número de factura, fecha, importe y NIF
6. El operador verifica los datos en la pestaña de indexación
7. Pulsa "Transferir" → los documentos se exportan al gestor documental

### Caso 2: Procesamiento desatendido de documentos
1. Un sistema externo deposita PDFs en una carpeta de red
2. DocScanWorker detecta los nuevos archivos automáticamente
3. Crea un lote, extrae las páginas del PDF y ejecuta el pipeline configurado
4. Al finalizar, envía un webhook al sistema origen con los resultados
5. Los documentos procesados se transfieren al destino configurado
6. El administrador puede supervisar todo desde el gestor de lotes

### Caso 3: Clasificación de documentos con IA
1. El operador importa un conjunto de documentos variados
2. El pipeline incluye un paso de IA que clasifica cada página (factura, albarán, contrato...)
3. Un script posterior asigna la categoría como campo de indexación
4. Los documentos se transfieren a subcarpetas según su clasificación

---

## 9. Ventajas Competitivas

| Aspecto | DocScan Studio | Soluciones tradicionales |
|---------|---------------|--------------------------|
| **IA Generativa** | Claude Vision, GPT-4o integrados | No disponible o requiere integración externa |
| **Pipeline configurable** | Sin límites en orden y combinación de pasos | Flujo fijo pre-barcode → post-barcode |
| **Scripting** | Python completo con acceso al contexto | Limitado o inexistente |
| **Doble motor barcode** | pyzbar + zxing-cpp | Típicamente un solo motor |
| **Multiplataforma** | Linux + Windows | Generalmente solo Windows |
| **Open source** | Sin costes de licencia | Licencias comerciales |
| **Proceso desatendido** | DocScanWorker + folder-watch | Requiere licencias adicionales |

---

## 10. Riesgos y Mitigaciones

| Riesgo | Impacto | Mitigación |
|--------|---------|------------|
| Compatibilidad con escáneres específicos | Medio | Doble protocolo (SANE + TWAIN/WIA), fallback a importación de archivos |
| Costes de API de IA | Medio | OCR local como alternativa sin coste, IA solo para extracción avanzada |
| Rendimiento con lotes grandes | Bajo | Procesamiento multihilo, SQLite WAL, paginación |
| Precisión de lectura de barcodes | Bajo | Doble motor con configuración por simbología y calidad mínima |

---

## 11. Conclusión

DocScan Studio se encuentra en una **fase avanzada de desarrollo** con el 91% de las fases completadas. La arquitectura base, todos los servicios de negocio y la interfaz de usuario principal están operativos y verificados con 409 tests automatizados.

Las dos fases restantes (proceso desatendido y tests de integración extendidos) representan funcionalidades complementarias que no afectan al núcleo del sistema. La aplicación es **funcional hoy** para escenarios de captura interactiva, procesamiento con pipeline y gestión de lotes.

El diseño modular y extensible permite incorporar nuevos tipos de paso, proveedores de IA y destinos de transferencia sin modificar el código existente, garantizando la evolución futura del producto.

---

*Documento generado el 10 de marzo de 2026*
*DocScan Studio — Tecnomedia*
