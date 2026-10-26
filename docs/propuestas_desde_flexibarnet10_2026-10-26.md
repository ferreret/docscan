# Propuestas para DocScan Studio a partir de FlexibarNET 10 — segunda pasada

**Fecha:** 2026-10-26
**Fuente analizada:** `Tecnomedia/FlexibarNET10` @ `f3ed0383` (v1.30.0, 2026-10-06)
**Estado DocScan de referencia:** v0.1.6 + `82eeeb4` (fix de migraciones), 937 tests verdes
**Informe anterior:** `docs/propuestas_desde_flexibarnet10_2026-07-27.md` (contra v1.11.0)

---

## 1. Método

Desde el primer análisis, Flexibar ha publicado **19 versiones** (v1.11.1 → v1.30.0) y **6
auditorías** (31-07, 04-08, 11-08, 14-08, 07-09, 16-09), además de todo un bloque de RGPD
y de ciberresiliencia (CRA). Casi todo lo nuevo sale de su **primera implantación
hospitalaria real**: el Hospital Arnau de Vilanova, con escáneres Kodak.

He leído el changelog completo de ese tramo, las auditorías y los documentos de RGPD y
seguridad. Cada lección la he contrastado con el código de DocScan. **Todo lo que este
informe marca como «DocScan tiene el problema» está comprobado con fichero:línea**, y las
dos más graves están además reproducidas.

Quedan fuera, como en julio, Vintasoft (JBIG2, MRC), OMR, el licenciamiento Keygen,
AdminWeb, la Tienda y lo que solo existe en WPF.

---

## 2. Resumen ejecutivo

La lección central de esta etapa de Flexibar es una sola: **los fallos silenciosos**. Sus
versiones v1.20, v1.26 y v1.27 se dedican casi enteras a ellos: un error que se trataba
como un éxito, o que solo quedaba en el registro. **DocScan tiene la misma familia de
fallos**, y en algunos casos peor:

1. **Un script de transferencia que lanza una excepción da la transferencia por buena.**
   `run_event` devuelve `None` ante cualquier excepción. `TransferWorker` lo traduce a
   `success = result is not False`, es decir, `True`. Si el que falla es
   `on_transfer_validate`, la validación **deja pasar todo**. En el worker desatendido,
   además, `on_transfer_advanced` se ejecuta *después* de marcar el lote como `exported`.
2. **Un código de barras puede sacar la transferencia de la carpeta de destino.**
   Reproducido: con el barcode `/tmp/evil` y el patrón `{first_barcode}`, el fichero se
   escribe en `/tmp/evil.tif`. `_build_filename` solo elimina los segmentos `..`. Tampoco
   filtra `CON`/`NUL`, `:*?"<>|` ni la longitud de cada segmento. El valor llega del
   papel, así que es una **entrada no confiable**.
3. **Un atasco del escáner a mitad de tanda.** Es el incidente que más le costó a
   Flexibar: perdió 90 páginas en el Arnau. En DocScan `acquire()` devuelve la lista
   completa al final:
   - Si salta el `timeout=120` de `scanimage`, o el driver TWAIN lanza una excepción, se
     pierden **todas** las páginas ya escaneadas.
   - Si SANE devuelve error tras N páginas, se trata como «ADF agotado» y **no se avisa**
     al operador.
   - Todo el lote vive en RAM hasta el final, y no se puede cancelar a mitad.

Lo demás es más barato y casi todo de bajo riesgo: el consentimiento al importar Apps
(pendiente desde julio), el historial de operaciones (existe pero **nadie lo escribe**),
el borrado seguro en la base de datos y las comprobaciones al guardar en el Configurador.

---

## 3. Hallazgos verificados en DocScan

### Bloque D — Fallos silenciosos (Flexibar v1.20 / v1.26 / v1.27)

| # | Lección de Flexibar | Estado en DocScan | Esf. |
|---|---|---|---|
| D1 | Si falla `on_transfer_advanced`, la transferencia falla y el lote no se marca (v1.26) | ⚠️ Se da por éxito: `script_engine.py:284-291` → `transfer_worker.py:71-80` → `workbench_window.py:1675-1680`. En el worker se ejecuta después de `exported`: `worker_main.py:~487-500` | S |
| D2 | La validación previa falla cerrada | ⚠️ Una excepción en `on_transfer_validate` devuelve `None` y deja pasar: `workbench_window.py:1567`, `worker_main.py:445-452` | XS |
| D3 | Si una transferencia falla a medias, se retira lo ya escrito (v1.27) | ⚠️ `_transfer_folder` deja los ficheros. Al reintentar, la colisión crea `_1` duplicados | M |
| D4 | El Configurador no guarda si algún script no compila (v1.20, v1.26) | ⚠️ `app_configurator.py:93-115` guarda sin compilar. Al cargar solo hay un `log.warning` (`workbench_window.py:163-170`). `run_step` recompila en cada página sin dejar nada en `script_errors` | S |
| D5 | Que el motor no esté disponible no equivale a «página sin código» (v1.26) | ⚠️ `barcode_service.py:59-61,137-139` devuelve `[]`. `ocr_service.py:171-210` devuelve `OcrResult()` vacío, sin `processing_errors` | S |
| D6 | Duplicar una App conserva toda su configuración (v1.26) | ⚠️ El clon pierde `notifications_json` (`launcher_window.py:409-426`). El import ignora `active` | XS |
| D7 | Red global de excepciones y trazas completas (auditorías 08-11, 08-14) | ⚠️ No hay `sys.excepthook` ni `threading.excepthook`. Hay 69 `log.error` y solo 2 con traza | S |
| D8 | El log registra la versión en cada arranque (v1.24) | ⚠️ No la registra | XS |

### Bloque E — Escáner en campo (Flexibar v1.24 / v1.26 / v1.27, Arnau)

| # | Lección de Flexibar | Estado en DocScan | Esf. |
|---|---|---|---|
| E1 | Cada página se entrega y se guarda en cuanto llega | ⚠️ `SaneScanner.acquire` y `TwainScanner.acquire` devuelven la lista al final (`scanner_service.py:225-346, 585-684`). `ScanWorker` solo emite después | M |
| E2 | Un atasco conserva las páginas recibidas y avisa: «continúe desde la hoja siguiente» | ⚠️ SANE lo confunde con fin de ADF sin avisar. Con TWAIN o con timeout se pierde todo | S (sobre E1) |
| E3 | «Cancelar escaneo» conserva lo recibido (v1.27) | ⚠️ La interrupción solo se comprueba cuando el escáner ya ha entregado todo | S (sobre E1) |
| E4 | Escáner que deja de responder: timeout por inactividad entre páginas, no total (v1.24) | ⚠️ `timeout=120` por página en SANE y ninguno en TWAIN | S |
| E5 | Avisar si el escáner rechaza opciones del perfil (v1.26) | ⚠️ `scanner_service.py:358-408` y `508-510`: `pass` o `log.debug`. Si no consigue el ADF, escanea en plano sin decir nada | S |
| E6 | Cerrar con una transferencia en curso espera o avisa | ⚠️ `closeEvent` espera 500 ms y suelta la referencia al `QThread` (`workbench_window.py:2436-2463`) | S |

### Bloque F — Confianza, RGPD y seguridad (Flexibar v1.14 / v1.16 / v1.19 / v1.22 / v1.26)

| # | Lección de Flexibar | Estado en DocScan | Esf. |
|---|---|---|---|
| F1 | Consentimiento informado al importar una App con código (A10 de julio) | ⚠️ `launcher_window.py:475-519` importa scripts sin mostrar nada. `on_app_start` se ejecuta al abrir la App | S |
| F2 | «Envía datos a» declarado por la App, junto a las URL que aparecen en sus scripts (v1.26) | Falta | S |
| F3 | `secrets.get("nombre")` en todos los scripts; los secretos no viajan en el pack (v1.16) | ⚠️ No está en el namespace (`script_engine.py:393-410`). Las cabeceras del webhook, con tokens, se guardan en claro en `notifications_json` y salen en el export | M |
| F4 | Historial de operaciones que se escribe de verdad y sobrevive al lote (v1.22) | ⚠️ El modelo existe, **pero nada inserta filas**, y `ondelete="CASCADE"` lo borra con el lote (`operation_history.py:23`) | M |
| F5 | Borrado no recuperable: `PRAGMA secure_delete` + `VACUUM` tras borrar (v1.19) | Falta (`database.py:33-39`) | XS |
| F6 | Huella en lugar de PII en los logs: barcodes, campos, nombres de fichero (v1.19, v1.26) | Parcial. Hoy solo se escribe en stderr, pero `transfer_service.py:541-548` registra el barcode y los campos | S |
| F7 | Retención automática de lotes (A4 de julio) | Falta | S |
| F8 | Actualizador que falla cerrado sin checksum | ⚠️ `update_service.py:224-226` devuelve `True` | XS |
| F9 | Directorio de datos solo legible por el usuario | ⚠️ Umask por defecto (0755). Los secretos sí están en 0600 | XS |
| F10 | Aviso de disco de datos sin cifrar (BitLocker; LUKS en Linux) | Falta | S/M |
| F11 | `SECURITY.md`, SBOM en cada release, pip-audit/dependabot, actions fijadas por SHA (v1.18, CRA) | Falta | XS-S |

### Bloque G — UX y rendimiento

| # | Lección de Flexibar | Estado en DocScan | Esf. |
|---|---|---|---|
| G1 | Los eventos tienen timeout y no congelan la UI | ⚠️ `run_event` llama a la función sin timeout, desde el hilo de UI | M |
| G2 | Las miniaturas no se leen a resolución completa en el hilo de UI (lotes grandes) | ⚠️ `cv2.imread` completo por página: `workbench_window.py:746-754, 1931-1939` | M |
| G3 | Al cerrar el Workbench, el Launcher se refresca y mantiene la selección (v1.25.1) | A verificar | XS |
| G4 | Traducciones al día | ⚠️ Unas 129 de 396 cadenas `tr()` no están en `docscan_en.ts`, que es del 24/03 | S |
| G5 | Aviso al renombrar un campo de lote que usan los scripts (v1.16) | Falta | S |

### Lo que DocScan ya hace bien (no tocar)

Comprobado en el código:

- Campos de lote tipados con selector de fecha y spinbox, guardados en
  `editingFinished`, sin la carrera por tecla que tenía Flexibar.
- Las lecturas no toman el bloqueo de escritura.
- `PipelineAbortError` termina en `needs_review`.
- `replace_image` persiste la imagen.
- Las páginas a revisión no hacen fallar el lote.
- Los secretos se guardan en 0600.
- No hay telemetría.
- La versión de SQLite del venv (3.53.1) no tiene el CVE-2025-6965.
- Los tests son herméticos.

### Pendiente del informe de julio (sigue vigente)

- **A1 + A2**: el separador como propiedad de la página y el documento lógico, con
  transferencia por documento.
- **B2 + B3**: launcher tipo hub.
- **A3**: transferencia en cola. En Flexibar generó tres correcciones más: idempotencia,
  eventos cargados en el worker y rollback.
- **A8**: confirmado que `required` es **decorativo**. Solo pinta un asterisco
  (`metadata_panel.py:117`) y nadie lo comprueba antes de transferir.

---

## 4. Plan propuesto por lotes

Cada lote va en su propia rama y PR, con tests y la suite completa en verde. Ninguno
depende del siguiente.

### Lote 3 — «Nada falla en silencio» (bajo riesgo, sin cambios de modelo)

D1, D2, D4, D5, D6, D7, D8, F8, F9 y **la seguridad de rutas de transferencia**: segmentos
saneados, nombres reservados, longitud y la comprobación final de que el resultado queda
*dentro* del destino. Añado **A8** (campos obligatorios que bloquean la transferencia),
porque es la misma familia: una validación que no valida.

Esfuerzo estimado: **1-2 sesiones**. Cambia el comportamiento en un punto: Apps cuyos
scripts de transferencia venían fallando sin que nadie lo viera pasarán a bloquear la
transferencia. No hay instalaciones en producción, así que es el momento de hacerlo.

### Lote 4 — «El escáner no pierde páginas» (requiere probar con el DR-M160)

E1-E6 y D3 (retirar la salida parcial de una transferencia fallida). E1 cambia el
contrato de `BaseScanner.acquire` a un generador, o a un callback por página. Los tests
se pueden cubrir con mocks, pero **la validación final necesita el escáner físico**, y
solo tú puedes hacerla.

### Lote 5 — «Confianza y RGPD»

F1 + F2 (diálogo de consentimiento con el código y los destinos de datos), F3 (secretos
en scripts y cabeceras del webhook fuera del JSON), F4 (historial real: requiere una
migración para quitar el CASCADE), F5, F6 y F7.

### Lote 6 — Funcional (de julio)

A1 + A2 (separador y documento lógico) y B2 + B3 (launcher). Toca el modelo de datos, así
que conviene planificarlo antes de empezar. **El diseño detallado de separadores y documento
lógico está en `docs/diseno_separadores_documento_2026-10-26.md`.**

Hay un hallazgo que adelanto al lote 3: la receta oficial de separación (README y
docs-web) no funciona. Usa `.data` en lugar de `.value` y espera que `pipeline.get_metadata`
pase de una página a otra, pero el contexto es nuevo en cada página.

### Fuera de lote (proceso, sin código de la app)

F10, F11, G4, la guía de despliegue sanitario adaptada de su
`08-despliegue-sanitario.md` y, si hace falta, los borradores RGPD de Flexibar como
plantilla (contrato de encargado del art. 28, registro del art. 30).

---

## 5. Decisiones que necesito de ti

1. **Que un ScriptStep falle marca la página «a revisión».** Hoy el error solo queda en
   `script_errors`. Es compatible con la regla «no detener el pipeline», porque el
   pipeline sigue, pero cambia qué páginas salen marcadas. Flexibar lo hace desde la v1.20.
2. **La transferencia por script falla cerrada (D1/D2).** Es el cambio de comportamiento
   del lote 3.
3. **Orden de lotes.** Recomiendo 3 → 4 → 5 → 6: primero lo que hoy puede entregar datos
   erróneos sin avisar, después el escáner y, al final, lo nuevo.

---

*Análisis generado el 2026-10-26 contra FlexibarNET10 @ `f3ed0383` (v1.30.0).*
