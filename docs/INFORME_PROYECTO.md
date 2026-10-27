# DocScan Studio — Informe de Proyecto
**Fecha**: 27 de octubre de 2026
**Versión del documento**: 1.2
**Estado del proyecto**: En desarrollo — v0.1.8 publicada, con instaladores; sin instalaciones en producción todavía

---

## 1. Resumen Ejecutivo

DocScan Studio es una aplicación de escritorio para la **captura por lotes, el procesamiento y la indexación de documentos**. Es la **reimplementación multiplataforma** de FlexibarNET 10, el producto de captura de Tecnomedia en .NET (solo Windows) que está en producción en hospitales. Mantiene **paridad funcional** con él (la misma lógica, las mismas claves de configuración y los mismos tokens), funciona en Linux y Windows, y añade **IA generativa** (Claude de Anthropic u OpenAI) para crear y configurar aplicaciones conversando.

El sistema digitaliza documentos desde escáneres físicos o importando ficheros (imágenes y PDF), los procesa con un pipeline configurable (operaciones de imagen, códigos de barras, OCR y scripts Python), los divide en documentos por código de barras, permite revisarlos e indexarlos, y los transfiere al archivo de destino.

**Estado actual**: v0.1.8, publicada el 27 de octubre de 2026, con instaladores para Linux (AppImage) y Windows (.exe) y actualización automática. Hay **1240 tests automáticos** en verde, con una cobertura de líneas del **72 %**. La v0.1.8 incorpora el **separador de documento** de FlexibarNET 10 y, como prueba de aceptación, **seis aplicaciones reales** de FlexibarNET 10 portadas (las de archivo del Hospital Arnau de Vilanova). Falta la validación en campo con escáner físico y la primera instalación en producción.

---

## 2. Objetivos del Proyecto

### 2.1 Objetivo Principal
Ofrecer una plataforma de captura documental multiplataforma, flexible y extensible, con el mismo comportamiento que FlexibarNET 10 allí donde ambos resuelven el mismo problema.

### 2.2 Objetivos Específicos

| # | Objetivo | Beneficio |
|---|----------|-----------|
| 1 | **Paridad con FlexibarNET 10** | Las aplicaciones de clientes reales se pueden portar con la misma configuración |
| 2 | **Multi-aplicación**: perfiles de proceso independientes, agrupables | Un mismo programa sirve para distintos tipos de documento y clientes |
| 3 | **Pipeline configurable**: pasos combinables sin programar | El flujo de proceso se define desde el configurador |
| 4 | **Separación de documentos** por código de barras | Un lote de papel se archiva como documentos independientes |
| 5 | **Scripting Python** | Los casos especiales se resuelven con scripts, sin tocar el programa |
| 6 | **IA generativa para configurar** | Crear o modificar una aplicación describiéndola en lenguaje natural |
| 7 | **Procesamiento desatendido** | Lotes procesados sin operador, desde una carpeta vigilada |
| 8 | **Multiplataforma**: Linux y Windows | Despliegue sin depender de Windows ni de SDK con licencia |

---

## 3. Descripción Funcional

### 3.1 Launcher

La pantalla principal lista las aplicaciones (perfiles de proceso) configuradas, agrupadas por cliente o departamento bajo cabeceras plegables, como en FlexibarNET 10. Desde él se:

- **Abre una aplicación** en la ventana de trabajo (Workbench)
- **Crea, configura, duplica, exporta e importa** aplicaciones
- **Abre el gestor de lotes**
- **Conversa con el AI Mode** para crear o modificar aplicaciones

Una aplicación también se puede abrir directamente desde la línea de comandos, o ejecutar en **modo directo** (escanear y transferir sin interfaz).

### 3.2 Configurador de Aplicaciones

Siete pestañas, con la presentación de FlexibarNET 10:

| Pestaña | Contenido |
|---------|-----------|
| **General** | Nombre, descripción, grupo, color del icono, escáner y si se muestra su diálogo, autotransferencia, detección de páginas en blanco |
| **Imagen** | Formato de captura, modo de color y compresión |
| **Campos de Lote** | Campos en maestro-detalle: tipo (texto, fecha, número, booleano, lista), obligatorio, descripción y valores |
| **Pipeline** | Lista de pasos con su resumen; un diálogo por tipo de paso |
| **Eventos** | Los 14 eventos del ciclo de vida y el panel de verificación, en lista con su estado y la casilla «Activado» |
| **Transferencia** | Modo, destino, colisión, nombre de los ficheros (patrón o script) y agrupación por documento |
| **Notificaciones** | Webhook al terminar una transferencia o ante un error |

Los scripts se editan con un editor con colores y números de línea, o en VS Code con autocompletado.

#### El pipeline

Cada página atraviesa los pasos configurados, en el orden que se quiera:

| Tipo de paso | Descripción | Ejemplo de uso |
|--------------|-------------|----------------|
| **Operación de imagen** | 24 transformaciones | Enderezar, binarizar, recortar bordes, quitar agujeros de perforadora |
| **Código de barras** | Dos motores (pyzbar con 10 simbologías, zxing-cpp con 15), página completa o zona | Leer el Code128 de una petición y decidir si la página abre un documento |
| **OCR** | Tres motores (RapidOCR, EasyOCR, Tesseract) | Extraer el texto de la página o de una zona |
| **Script** | Python con acceso al contexto completo | Extraer un número de pedido del texto, validar datos |

Desde un script se puede controlar el flujo: saltar pasos, repetir uno (con límite), abortar la página para revisión o sustituir la imagen.

#### Separador de documento

Un **documento** es el tramo de páginas que va de una página separadora a la siguiente. El paso de código de barras declara la condición de separador (por simbología, por expresión regular o por valor fijo), con la misma lógica que FlexibarNET 10. El operador puede marcar o desmarcar separadores a mano y reordenar páginas.

#### Transferencia

- Modos: carpeta (un fichero por página), **PDF**, **PDF/A**, **TIFF multipágina** y CSV de índices.
- Un fichero por lote o **uno por documento**; la página separadora se incluye o se descarta.
- Nombre por **patrón** (con variables del lote, de la página y del documento) o por **script**.
- Ante un nombre existente: sufijo, sobrescribir o **fusionar** (añadir páginas al final).
- Todo se comprueba antes de escribir (nombres, rutas, imágenes) y los ficheros multipágina se escriben de forma atómica: una transferencia que no puede completarse no deja nada a medias.
- Transferencia avanzada por script para integrarse con cualquier sistema.

### 3.3 Workbench (ventana de trabajo)

- **Adquisición**: escáner (SANE en Linux, TWAIN/WIA en Windows) o importación de imágenes y PDF.
- **Proceso en segundo plano**: el pipeline se ejecuta por cada página sin bloquear la interfaz.
- **Visor**: zoom, ajuste, rotación y recuadros sobre los códigos leídos.
- **Miniaturas** con un color por estado: con código, separadora, pendiente de revisión.
- **Panel derecho**: separador del documento, códigos de la página (alta manual validada por regex), campos de lote, verificación, texto OCR y log.
- **Navegación**: siguiente con código, siguiente pendiente de revisión, o la que decida un script.
- **Atajos de teclado** de FlexibarNET 10 (F5 escanear, F9 procesar, Ctrl+D separador, Alt+↑/↓ mover página…).
- **Transferencia** al destino configurado, tras la validación de la aplicación.

### 3.4 Gestor de Lotes

- Lista de lotes con filtros por aplicación, estación y fechas.
- Estados: creado → leído → verificado → listo para exportar → exportado, más los de error de lectura y de exportación.
- Detalle con cuatro pestañas: general, estadísticas, páginas e historial.
- Historial de las operaciones de cada lote.
- Refresco automático cada 20 segundos; abrir o eliminar un lote.

### 3.5 Proceso Desatendido (DocScanWorker)

Proceso de línea de comandos sin interfaz:

- **Vigila una carpeta** de entrada y crea un lote por cada fichero nuevo (imágenes o PDF).
- **Procesa los lotes pendientes** y termina.
- Usa **el mismo pipeline y el mismo flujo de transferencia** que el Workbench (validación, separadores, script de nombre).
- Un lote cuya validación falla pasa a error y se **notifica por webhook**.

---

## 4. Arquitectura Técnica (Resumen)

### 4.1 Stack Tecnológico

| Componente | Tecnología | Justificación |
|------------|------------|---------------|
| Lenguaje | Python 3.14 | Desarrollo, CI e instaladores con la misma versión |
| Interfaz gráfica | PySide6 (Qt 6) | Multiplataforma, nativo, maduro |
| Base de datos | SQLAlchemy 2 + SQLite (modo WAL) + Alembic | Sin servidor; interfaz y worker a la vez; migraciones al arrancar |
| Barcode motor 1 | pyzbar + OpenCV | Rápido en códigos 1D |
| Barcode motor 2 | zxing-cpp | Mejor en 2D y con varios códigos por página |
| OCR | RapidOCR (principal), EasyOCR, Tesseract | Local, sin coste por página |
| IA | Anthropic SDK, OpenAI SDK | AI Mode (*tool calling*) |
| PDF | PyMuPDF | Lectura y generación, incluido PDF/A |
| Escáner | SANE (Linux), TWAIN y WIA (Windows) | Sin SDK con licencia |
| Cifrado | Fernet (cryptography) | Claves de API nunca en texto plano |
| Empaquetado | PyInstaller, AppImage, Inno Setup | Instaladores y actualización automática desde GitHub Releases |

### 4.2 Principios de Diseño

- **Paridad con FlexibarNET 10**: cuando ambos resuelven el mismo problema, se sigue su comportamiento documentado; las desviaciones se deciden explícitamente.
- **Nada falla en silencio**: un fallo de script o de motor aparece en la página, en el log o como transferencia fallida, nunca como un éxito.
- **La interfaz nunca se bloquea**: el trabajo pesado va en hilos secundarios.
- **La IA configura, no procesa**: el proceso de cada página es determinista.
- **Datos del papel no fiables**: un valor leído no puede escribir fuera del destino.
- **Seguridad**: claves cifradas, directorios de datos privados.

---

## 5. Evolución del Proyecto

Las 22 fases del plan inicial (infraestructura → servicios → interfaz → worker → tests) están terminadas desde abril de 2026. Desde entonces el trabajo se organiza en **lotes de mejoras** sacados del análisis de FlexibarNET 10: dos pasadas sobre su código, sus versiones (v1.11 en julio, v1.30 en octubre: 19 versiones y 6 auditorías revisadas en la segunda) y sus manuales.

| Lote | Contenido | Versión |
|------|-----------|---------|
| 1 y 2 | Correcciones de la primera pasada (caché de scripts, regex sin bloqueos…) | v0.1.6 |
| 3 | «Nada falla en silencio»: transferencia que falla cerrada, rutas blindadas, obligatorios | v0.1.7 |
| 6 (S1–S2) | Separador de documento, transferencia por documento, script de nombre | v0.1.8 |
| 4 | Deshacer una transferencia que falla a medias | Pendiente |
| 5 | Log a fichero con enmascarado de datos personales | Pendiente |

---

## 6. Estado Actual del Proyecto

### 6.1 Métricas

Medidas el 27 de octubre de 2026 sobre la v0.1.8 (detalle y método en `docs/portfolio/metricas.md`).

| Métrica | Valor |
|---------|-------|
| Versión actual | **v0.1.8** (27/10/2026) |
| Releases publicadas | **10** (v0.1.0 a v0.1.8, más dos candidatas) |
| Tests automáticos | **1240** en verde |
| Cobertura de líneas | **72 %** |
| Líneas de Python de la aplicación | **27.407** |
| Líneas de tests | **18.743** |
| Aplicaciones de FlexibarNET 10 portadas | **6** |

### 6.2 Funcionalidades Operativas

| Funcionalidad | Detalles |
|---------------|----------|
| ✅ Launcher | Aplicaciones agrupadas, configurador, gestor de lotes, AI Mode |
| ✅ Configurador | 7 pestañas al estilo FlexibarNET 10, editor de scripts con colores, VS Code |
| ✅ Pipeline | 4 tipos de paso, 24 operaciones de imagen, 2 motores de barcode, 3 de OCR |
| ✅ Separador de documento | Automático por barcode o manual, con validación del valor |
| ✅ Transferencia | Carpeta, PDF, PDF/A, TIFF multipágina, CSV; por lote o por documento; nombre por script |
| ✅ Workbench | Visor, miniaturas, panel de códigos, campos, verificación, atajos de FlexibarNET 10 |
| ✅ Gestor de lotes | Filtros, detalle en 4 pestañas, historial |
| ✅ Worker desatendido | Carpeta vigilada y lotes pendientes, con el mismo flujo que el Workbench |
| ✅ IA | AI Mode con Claude u OpenAI, con vista previa de cada cambio |
| ✅ Instaladores | AppImage y setup.exe, con actualización automática |
| ✅ Idiomas | Español, inglés y catalán |

### 6.3 Pendiente de Validación en Campo

- Escaneo con escáner físico en Linux (Canon DR-M160) y en Windows.
- Las aplicaciones del Hospital Arnau con escaneos reales (hoy se prueban con páginas sintéticas con códigos reales).
- OCR con EasyOCR (descarga modelos de PyTorch).
- Primera instalación en producción.

---

## 7. Hitos y Cronograma

### Hitos Completados

| Hito | Fecha | Descripción |
|------|-------|-------------|
| H1–H4 | Marzo 2026 | Pipeline, servicios, interfaz e integración |
| H5 | Marzo 2026 | Primera release, v0.1.0, con instaladores |
| H6 | Abril–julio 2026 | Worker desatendido, auditoría, Python 3.14, dependencias al día (v0.1.1–v0.1.5) |
| H7 | Julio 2026 | Primera pasada de paridad con FlexibarNET 10 (v0.1.6) |
| H8 | Octubre 2026 | Segunda pasada: «nada falla en silencio» y rediseño visual (v0.1.7) |
| H9 | Octubre 2026 | Separador de documento y aplicaciones del Hospital Arnau (v0.1.8) |

### Hitos Pendientes

| Hito | Descripción |
|------|-------------|
| H10 | Familia eCAP del Hospital Arnau: secretos accesibles desde scripts y registro por ODBC |
| H11 | Lotes 4 y 5 |
| H12 | Validación en campo con escáner y primera instalación en producción |

---

## 8. Casos de Uso Principales

### Caso 1: Archivo de peticiones por código de barras (Hospital Arnau)
1. El operador abre «01 Arxiu de Peticions» y escanea un taco de peticiones.
2. El paso de código de barras lee el Code128 o el Interleaved 2 of 5 de cada hoja y la marca como separadora.
3. Si una hoja no tiene código, la validación bloquea la transferencia e indica cuál es; el operador la marca a mano (Ctrl+D) con su valor.
4. Al transferir, cada código va a su TIFF en la carpeta del día; si el código ya existía, la página se añade al final del fichero.

### Caso 2: Facturas, un PDF por factura
1. Las facturas llevan un Code128 con su número en la primera página.
2. El paso de código de barras marca esas páginas como separadoras; las siguientes forman parte de la misma factura.
3. Un script de nombre guarda cada factura en la carpeta de su proveedor con el número como nombre.

### Caso 3: Proceso desatendido
1. Un sistema externo deja PDF en una carpeta.
2. DocScanWorker crea un lote por fichero, ejecuta el pipeline y transfiere.
3. Si algo falla, el lote queda en error y se avisa por webhook; el gestor de lotes lo muestra.

---

## 9. Comparación con FlexibarNET 10

| Aspecto | DocScan Studio | FlexibarNET 10 |
|---------|----------------|----------------|
| **Plataforma** | Linux y Windows | Solo Windows |
| **Lenguaje** | Python 3.14, PySide6 | .NET 10, WPF |
| **Imagen y códigos** | OpenCV, pyzbar, zxing-cpp (libres) | SDK comercial con licencia |
| **Comportamiento** | Paridad: misma lógica, claves y tokens | Referencia, en producción en hospitales |
| **IA generativa** | Crear y configurar aplicaciones conversando | — |
| **Madurez** | En desarrollo, sin instalaciones en producción | En producción |

---

## 10. Riesgos y Mitigaciones

| Riesgo | Impacto | Mitigación |
|--------|---------|------------|
| Compatibilidad con escáneres concretos | Medio | SANE, TWAIN y WIA; importación de ficheros como alternativa; falta validar en campo |
| Diferencias de comportamiento con FlexibarNET 10 | Medio | Paridad como requisito; aplicaciones reales portadas como prueba de aceptación |
| Pérdida de datos al migrar la base de datos | Alto | Migraciones probadas sobre una copia de una base real antes de cada release |
| Costes de API de IA | Bajo | La IA solo se usa para configurar, nunca por página |

---

## 11. Conclusión

DocScan Studio cubre ya el flujo completo de captura —escaneo o importación, pipeline, separación en documentos, revisión, indexación y transferencia— en Linux y Windows, con el comportamiento de FlexibarNET 10 y 1240 tests automáticos. La v0.1.8 demuestra la paridad con seis aplicaciones reales de un hospital en producción con FlexibarNET 10.

Lo que queda para la primera instalación en producción es la validación en campo con escáner y escaneos reales, la familia eCAP del Hospital Arnau y los lotes 4 y 5 (transferencias que fallan a medias y log con datos personales enmascarados).

---

*Documento generado el 10 de marzo de 2026; actualizado el 22 de julio de 2026 (v1.1) y el 27 de octubre de 2026 (v1.2).*
*DocScan Studio — Tecnomedia*
