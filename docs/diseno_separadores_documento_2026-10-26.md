# Hojas separadoras y documento lógico — análisis de FlexibarNET 10 y diseño para DocScan

**Fecha:** 2026-10-26
**Fuente:** `Tecnomedia/FlexibarNET10` @ `f3ed0383` (v1.30.0)
**Material leído:**
- **Código:** `Domain/Models/{Page,Document,PipelineStep}.cs`, `Application/Documents/*`,
  `PipelineExecutor.RunBarcode`, `TransferService` (agrupación y tokens),
  `WorkbenchViewModel.Documents.cs` e `IWorkbenchApi`.
- **Specs de diseño:** `2026-05-27-concepto-documento` (abandonado),
  `2026-06-01-documento-redux`, `2026-06-04-separador-entidad-disociada` y
  `2026-06-05-app-peticion-tipodocumento`.
- **Manual:** conceptos, Workbench, pestaña Pipeline y pestaña Transferencia.
- **Caso real:** las Apps del Arnau (`tools/SeedAppsArnau`).

**Complementa:** el bloque A1/A2/A6 de `propuestas_desde_flexibarnet10_2026-07-27.md` y el
lote 6 de `propuestas_desde_flexibarnet10_2026-10-26.md`.

---

## 1. Resumen

Flexibar acertó con el modelo **en el segundo intento**. El primero (v0.5.0) era rico: entidad
`Document`, reglas combinables, bandeja de «sin asignar», asignación manual con prioridad
sobre la automática y un `DocumentStep` aparte. **Se abandonó tras el smoke real.** El que
está en producción es deliberadamente mínimo:

> Un **separador** es una propiedad de la página (`IsSeparator` + `SeparatorValue`). Un
> **documento** es el tramo que va de un separador al siguiente, **calculado al vuelo** por
> una función pura y nunca almacenado. Los **campos del documento** son los campos de su
> página separadora.

Ese modelo encaja en DocScan casi tal cual, y conviene copiarlo **sin repetir el rodeo de
v0.5.0**.

> **Requisito (Nicolás, 2026-10-26): paridad funcional con FlexibarNET 10 v1.30.** DocScan
> tiene que comportarse igual que Flexibar con separadores y documentos: detección,
> precedencia del valor manual, reproceso, Workbench, agrupación y tokens. La referencia es
> el **comportamiento documentado en su manual**. Las únicas diferencias admitidas están
> listadas en §3: la opción de descartar la hoja, que tú has pedido, y tres puntos en los
> que el código de Flexibar contradice su propio manual.

En DocScan la separación hoy **solo existe como color**:
- Un script pone `role="separator"` a un barcode y la miniatura cambia de color.
- La transferencia no sabe nada de documentos.
- La receta oficial para separar está **rota** (§4).

---

## 2. Cómo funciona en FlexibarNET 10

### 2.1 Modelo

| Pieza | Qué es | Dónde |
|---|---|---|
| `Page.IsSeparator` | La verdad: «esta página abre un documento» | Columna en BD |
| `Page.SeparatorValue` | **Instantánea** del valor que identifica el documento. Es independiente de `page.Barcodes`: borrar un barcode no lo toca y desmarcar el separador no borra barcodes | Columna en BD, máximo 500 caracteres |
| `DocumentGroup(Index, SeparatorPage?, Pages, IsImplicitLeading)` | Vista lógica | `DocumentGrouper.Group(pages)`, función pura O(n) |
| Campos del documento | Los `VirtualFields` de la página separadora | Sin entidad nueva |

Reglas del agrupado:

- Las páginas anteriores al primer separador forman un **documento implícito**. Un lote sin
  separadores es un único documento, y por eso «por documento» equivale a «por lote» cuando
  no hay ninguno.
- **Reordenar** recalcula los tramos, porque el flag viaja con la página. **Desmarcar** un
  separador funde su tramo con el anterior, y **borrar** la página separadora también.
- El operador solo hace dos cosas: **marcar o desmarcar** y **reordenar**. No existe «mover
  la página al documento N». Esto fue una decisión explícita, tomada tras el fracaso de
  v0.5.0.

### 2.2 Detección automática: dentro del paso Barcode

El paso que lee los códigos es el mismo que decide el separador. Flexibar lo hizo así a
propósito: en v0.5.0, un `DocumentStep` separado dependía en silencio de un `BarcodeStep`
anterior, y ese fue uno de los motivos del abandono.

Campos del `BarcodeStep` (serializados en snake_case y omitidos si tienen el valor por
defecto):

| Campo | Para qué |
|---|---|
| `separator_enabled` | Activa la detección |
| `separator_by` | `symbology` / `regex` / `fixed_value` |
| `separator_symbology`, `separator_regex`, `separator_fixed_value` | Condición según el modo |
| `separator_regex_include_symbology` | Evalúa `NN`+valor (paridad con el Flexibar legacy: el Arnau lo usa) |
| `separator_manual_regex` | Valida lo que **teclea** el operador al marcar a mano. Es independiente de la regex automática y del «Añadir barcode» |
| `separator_default_value` | Valor con el que se pre-rellena el diálogo manual |

**Distinguir «detectar» de «identificar».** En `fixed_value` el código (por ejemplo `SEP`)
sirve para detectar el separador, pero no identifica el documento: es el mismo en todas las
hojas.

**Reproceso autoritativo.** Si `separator_enabled` está activo, reprocesar recalcula el
flag y el valor (true **o** false) y pisa la marca manual. Quien quiera mandar a mano
desactiva la detección. Flexibar evitó a conciencia un tri-estado «manual / auto»: en
v0.5.0 ese conflicto fue la otra causa del abandono.

### 2.3 Workbench

- **Marca visual:** marco naranja en la miniatura y en el visor, y banderita con ★. Las
  miniaturas reales se mantienen: en v0.5.0 se cambiaron por cajitas de texto y fue otra
  lección.
- **Botón de banderita** en la barra del visor:
  - **Marcar** pre-rellena el valor en este orden: código que cumple la condición → primer
    código de la página → valor por defecto → vacío. Después lo valida en vivo contra
    `separator_manual_regex`. Cancelar no marca nada. Se admite un valor vacío.
  - **Desmarcar** solo quita el flag y el valor.
- **Zona «Separador de documento»** en el panel derecho: tarjeta con borde naranja, el valor
  en monoespaciada y el botón «Editar valor».
- **Reordenar** arrastrando miniaturas o con **Alt+↑/↓**. El separador viaja con su página.

### 2.4 Transferencia

- Modo multipágina con `Agrupación = Por documento` genera un fichero por tramo.
- Tokens: `{separator}`, `{document_index}`, `{pagefield:NOMBRE}` (campo de la separadora
  del documento) y `{first_barcode}`.
- Flujo típico de la documentación: patrón `{separator}_{batch_id}` →
  `FAC-001_1234.pdf`, `FAC-002_1234.pdf`, etc.
- **Agrupación por clave, no por posición** (spec 06-05): con «un fichero por página» y la
  colisión `AppendToEnd`, las páginas **no consecutivas** que tienen el mismo número se
  anexan al mismo PDF. Es el caso real «Petición/TipoDocumento», que no se resuelve con
  separadores.

### 2.5 Scripts

- Los paneles de verificación tienen `Api.GetPageSeparator(i)` y `Api.SetSeparatorAsync(i,
  valor)`. Esta última valida como el botón y refresca la interfaz. Se añadió para el panel
  «Petició / Codi ICS» del Arnau: lo que teclea el operador **es** el separador que se
  archiva.
- La importación por script añade cada fichero como un documento y **marca su primera
  página como separador**.
- `Api.WriteExtraction(doc, json)` escribe los campos extraídos (por ejemplo, por IA) en la
  página separadora.

---

## 3. Lo que Flexibar hace mal o no hace (no copiar)

Lo he comprobado en el código de la v1.30.0:

1. **`{document_id}` siempre sale vacío.** La entidad `Document` y `Page.DocumentId` son
   restos del diseño abandonado: **nadie asigna `DocumentId`** (no hay ningún `DocumentId =`
   fuera de las migraciones). Aun así, el token aparece en el manual y en la guía de autoría.
   → **En DocScan, ni tabla ni columna de documento.**
2. **`{separator}` se resuelve sobre la página que se transfiere, no sobre la separadora de
   su documento** (`TransferService.cs:709`, `.Replace("{separator}",
   page.SeparatorValue)`). En el modo por documento funciona porque la primera página es la
   separadora. Pero en «un fichero por página», los adjuntos reciben `""`, en contra de lo
   que dice el manual. `{pagefield:}` en cambio sí usa el mapa de separadoras. Son dos
   reglas distintas para el mismo concepto.
   → **En DocScan, todos los tokens de documento se resuelven sobre la separadora del
   documento, para cualquier página y en cualquier modo.**
3. **No hay forma de descartar la hoja separadora física.** En Flexibar el separador es
   siempre la **portada** del documento (la petición médica), y por eso viaja en el PDF. Con
   **hojas separadoras** de verdad (patch sheets, folios con un barcode que no son
   documento) eso ensucia la salida.
   → **En DocScan, opción por App: la página separadora `se incluye` (portada) o `se
   descarta` (hoja separadora).**
4. **Varios pasos Barcode con detección activa se pisan.** Cada `RunBarcode` asigna
   `IsSeparator` a partir de **sus** resultados, de modo que un segundo paso que no casa
   desmarca lo que marcó el primero. Además, el Workbench toma la configuración manual del
   *primer* paso con detección.
   → **En DocScan, la decisión se toma una sola vez por página**: es separador si
   *cualquier* paso con detección casa.

Además, el diseño escrito y el código no coinciden en el reproceso. La spec del 01-06 dice
que se conserva el valor tecleado a mano; la del 04-06 y el código lo pisan.
**Decidido: como Flexibar hoy.** Con la detección activa, reprocesar recalcula flag y valor
y pisa la marca manual, sin diálogo adicional.

### Resolución con el requisito de paridad

| Punto | Comportamiento en DocScan |
|---|---|
| 1. `{document_id}` | Existe como **alias de `{document_index}`**. El manual lo describe como un id numérico del documento; así resuelve a un valor real y no a vacío, sin crear tabla |
| 2. `{separator}` en «un fichero por página» | **Lo que dice el manual**: el valor del separador del documento al que pertenece la página, también en los adjuntos |
| 3. Descartar la hoja separadora | Diferencia **pedida por Nicolás**: `separator_page`, por defecto `include` (= Flexibar) |
| 4. Varios pasos Barcode con detección | Es un caso que el manual no contempla. Separador si casa **cualquiera**; con un solo paso es idéntico a Flexibar |

---

## 4. Estado actual en DocScan

| Aspecto | Hoy | Evidencia |
|---|---|---|
| Concepto de separador | Solo `Barcode.role == "separator"`, puesto por script | `app/models/barcode.py:14,36` |
| Efecto | Color de la miniatura y contador «Separadores» | `page_state.py:58`, `workbench_window.py:2240` |
| Transferencia | Ignora el separador. PDF = **un fichero por lote** | `transfer_service.py:253-330` |
| Agrupar por clave | **Ya existe**: colisión «fusionar» por página | `transfer_service.py:455` (`_merge_into_existing`) |
| Excluir páginas | **Ya existe** `page.is_excluded` (los blancos se excluyen solos) | `workbench_window.py:1181,1609` |
| Reordenar páginas | **No existe** en el Workbench | Solo hay `InternalMove` en el editor de pipeline |
| Marca manual | «Barcode manual» con `barcode_fixed_value` («útil para separadores», según el asistente), pero no asigna rol | `workbench_window.py:1955-1990`, `ai_mode_assistant.py:344` |
| Contexto entre páginas | `PipelineContext` **se crea nuevo en cada página** | `executor.py:74` |

### ⚠️ La receta oficial de separación está rota

Aparece en `README.md` («Ejemplo: separación de documentos por barcode») y en
`docs-web/user-guide/scripting.md` («Separar documentos por barcode»):

```python
seps = [b for b in page.barcodes if b.symbology == "CODE128"]
if seps:
    page.fields["id_documento"] = seps[0].data            # (1)
    pipeline.set_metadata("ultimo_id", seps[0].data)
else:
    page.fields["id_documento"] = pipeline.get_metadata("ultimo_id") or "SIN_ID"   # (2)
```

1. `BarcodeResult` no tiene `.data`, se llama `.value` (`page_context.py:26-38`). La línea
   lanza `AttributeError` y el error queda en `script_errors`.
2. Aunque se corrija, `pipeline.get_metadata` **no sobrevive de una página a otra**: el
   contexto es nuevo en cada página. Por eso todos los adjuntos salen como `SIN_ID`.

Así que **en DocScan no hay hoy ninguna forma documentada que funcione** para propagar la
identidad de un documento a sus adjuntos. Es el argumento más fuerte para hacer de esto una
función del producto y no una receta de script. El arreglo de la documentación entra ya en
el lote 3.

---

## 5. Diseño propuesto para DocScan

### 5.1 Modelo de datos

- `Page.is_separator: bool` (por defecto `False`) y `Page.separator_value: str` (por defecto
  `""`). Es una migración Alembic **aditiva** con `server_default`.
  - Lección de nuestro bug del 05-08: probarla sobre una **copia** de una BD real y comparar
    `COUNT(*)` antes y después. El `PRAGMA foreign_keys=OFF` durante las migraciones ya está.
- **Sin tabla ni columna de documento.**
- `app/models/document.py` (dominio puro, sin ORM):

  ```python
  @dataclass(frozen=True)
  class LogicalDocument:
      index: int                      # 1-based
      separator_page: Page | None     # None = documento implícito inicial
      pages: list[Page]               # ordenadas por page_index
      @property
      def is_implicit(self) -> bool: ...
      @property
      def separator_value(self) -> str: ...

  def split_documents(pages: Sequence[Page]) -> list[LogicalDocument]: ...
  ```

- **Compatibilidad con `role="separator"`.** El rol se mantiene en `Barcode`, pero deja de
  ser lo que manda. La migración puede marcar `is_separator=True` en las páginas que hoy
  tienen un barcode con ese rol, para que los lotes existentes no cambien de aspecto.

### 5.2 Detección automática: en `BarcodeStep` y en scripts

- Se añaden a `BarcodeStep` (`app/pipeline/steps.py`) **los mismos campos planos y con las
  mismas claves snake_case que Flexibar**: `separator_enabled`, `separator_by`
  (`symbology` / `regex` / `fixed_value`), `separator_symbology`, `separator_regex`,
  `separator_fixed_value`, `separator_regex_include_symbology`, `separator_manual_regex` y
  `separator_default_value`. Con la misma semántica, una definición de paso se puede pasar
  de una aplicación a la otra.
  - Las regex van con `app/utils/safe_regex` (lote 2).
  - Test **obligatorio** de ida y vuelta con el serializador real, comprobando además la
    forma exacta del JSON. Es la lección nº 1 de v0.5.0.
- **Una decisión por página:** el executor junta lo que casan todos los pasos con detección
  activa y decide al terminar el pipeline: es separador si casa cualquiera. El valor es el
  del primer código que casa. Así se evita el bug 4 de §3.
- **Scripts:** `page.is_separator` y `page.separator_value` se pueden leer y escribir en
  `ScriptStep`. Un script posterior al paso Barcode tiene la última palabra. Es la vía
  «script-first» de DocScan, y la del FixedValue o las condiciones compuestas.
- ⚠️ **Choca con una regla del CLAUDE.md**: «BarcodeStep is role-agnostic… Roles are
  assigned by a subsequent ScriptStep». La propuesta no asigna *roles* a barcodes (el
  separador es de la página y el barcode no se toca), pero sí da al paso Barcode una
  condición declarativa. **Hay que reformular la regla** (§6).

### 5.3 Workbench

1. **Reordenar páginas** (arrastre en miniaturas + Alt+↑/↓). Es requisito previo: sin
   reordenar, el operador no puede corregir un documento.
2. Marco naranja en la miniatura y en el visor, y cabecera de tramo «Doc 3 · FAC-002 · 4
   págs».
3. Botón «Marcar separador» con atajo y diálogo validado. Usa la misma precedencia de
   pre-relleno que Flexibar y valida con `manual_regex`.
4. Zona «Separador de documento» en el panel derecho, con el valor y «Editar valor».
5. Contador «Documentos: N» junto a los que ya existen. Aviso ⚠ si hay un documento
   implícito inicial; no bloquea.

### 5.4 Transferencia

- La configuración de transferencia gana `grouping: "batch" | "document"` (aplica a PDF,
  PDF/A y TIFF multipágina) y `separator_page: "include" | "exclude"`.
- Tokens con **los mismos nombres que Flexibar**, siempre resueltos sobre el documento de la
  página, sea cual sea el modo (§3):
  - `{separator}`;
  - `{document_index}`;
  - `{document_id}` (alias de `{document_index}`);
  - `{pagefield:NOMBRE}`: campo de la página separadora.
- El valor del separador **viene del papel**, así que la seguridad de rutas del lote 3 (rutas
  que no salen del destino, nombres reservados, longitud) es **requisito previo**.
- La agrupación por clave ya existe con «fusionar». Basta con documentarla como la
  alternativa para páginas no consecutivas y comprobar que funciona también en PDF.
- **Validaciones antes de transferir:**
  - Documento sin valor de separador cuando el patrón usa `{separator}`, porque dos
    documentos acabarían con el mismo nombre.
  - Documento que queda vacío al descartar la hoja separadora.
  - Documento implícito inicial con `separator_page=exclude`.
- El worker desatendido usa el mismo camino: la función pura y la misma configuración.

### 5.5 Scripts y eventos

- `batch.documents` (calculado, solo lectura) en `on_transfer_validate`,
  `on_transfer_advanced` y `on_scan_complete`, con `.index`, `.separator_value`, `.pages`
  y `.fields`.
- En el panel de verificación, el equivalente de `SetSeparatorAsync`: un método que marca,
  valida y refresca igual que el botón.
- Importación de varios ficheros: opción «cada fichero importado es un documento», que marca
  la primera página de cada fichero. Es barata y es lo que Flexibar hace desde su
  importación por script.
- **Actualizar** el README, `docs-web` y el conocimiento de los asistentes
  (`_assistant_constants.py`, `ai_mode_assistant.py`). Flexibar tuvo Apps generadas por el
  asistente que no podían usar funciones nuevas porque su conocimiento no se había
  actualizado (v1.14).

---

## 6. Decisiones que necesito de ti

1. ✅ **Decidido (2026-10-26): se soportan las dos con `separator_page`.** El valor por
   defecto es `include`: la página separadora es la **portada** y va dentro del documento,
   como en Flexibar. Con `exclude` se trata como **hoja separadora** y no sale en el
   fichero.
2. ✅ **Reproceso: igual que Flexibar.** Con la detección activa, recalcula y pisa la
   marca manual. Quien quiera mandar a mano desactiva la detección.
3. **Reformular la regla del CLAUDE.md** sobre `BarcodeStep` role-agnostic. La paridad lo
   exige, porque en Flexibar la condición vive en el paso Barcode. Texto propuesto:
   «BarcodeStep no asigna roles a los barcodes; puede declarar una condición de separador
   que marca la **página**. Los scripts pueden sobrescribir `page.is_separator`». *El
   CLAUDE.md lo edito solo con tu OK explícito.*
4. **Migrar el `role="separator"` existente a `is_separator`**: Flexibar no tiene este
   legado. Recomiendo migrar para que los lotes antiguos se sigan viendo igual.

---

## 7. Plan por slices (con smoke real al cerrar cada uno)

Esta es la lección de proceso que más le costó a Flexibar: el smoke **en cada slice**, no
al final.

| Slice | Contenido | Smoke |
|---|---|---|
| **S1 — Núcleo de extremo a extremo** | Columnas y migración, `split_documents`, reordenar páginas, marca manual con diálogo, marco naranja, `grouping=document` en PDF y `separator_page`, tokens `{separator}` y `{document_index}` | Importar un PDF de 10 páginas, marcar 3 separadores a mano, reordenar y transferir: 3 PDF con el nombre correcto |
| **S2 — Detección automática** | Bloque `separator` en `BarcodeStep`, serializador (test de ida y vuelta), decisión única por página, editor del paso en el Configurador | Lote con hojas Code39 reales escaneadas con el DR-M160 |
| **S3 — Campos y scripts** | `{pagefield:}`, `page.is_separator` en scripts, `batch.documents` en eventos, API del panel de verificación, «cada fichero es un documento» al importar | App con extracción y nombrado por campo de documento |
| **S4 — Pulido** | Validaciones antes de transferir, cabeceras de tramo, worker desatendido, i18n, README, docs-web y conocimiento de los asistentes, CHANGELOG | Revisión visual de las ventanas reales en modo offscreen |

**Depende de:** el lote 3 (seguridad de rutas y transferencia que falla cerrada), porque el
nombre del fichero sale del papel.
**Esfuerzo:** de M a L en total; S1 es lo más grande.

---

## 8. Estado (2026-10-27, rama `feat/lote6-separadores`)

**Hecho: S1 y S2, más el script de nombre.** El caso de aceptación son las seis Apps de
archivo del Arnau (`tools/arnau_apps.py`), que pasan de extremo a extremo por el worker
real con lectura real de códigos (`tests/test_arnau_e2e.py`).

| Pieza | Estado |
|---|---|
| Columnas, migración `d3f8a1c6e2b7` y `role="separator"` → marca de página | Hecho |
| `split_documents` / `LogicalDocument` (`app/models/document.py`) | Hecho |
| Condición en `BarcodeStep`, decisión única por página, autoritativa | Hecho (`app/pipeline/separator.py`) |
| Leyenda legacy «NN» de simbologías | Hecho; corrige además el filtro general, que anteponía dos letras |
| Marca manual (Ctrl+D) con diálogo validado, zona del panel derecho, marco naranja | Hecho |
| Reordenar con Alt+↑/↓ | Hecho. **Falta arrastrar miniaturas** |
| `grouping` y `separator_page` en PDF, PDF/A y TIFF multipágina (modo nuevo) | Hecho |
| `{separator}`, `{document_index}`, `{document_id}` | Hecho |
| Script de nombre (`name_mode` / `file_name_script`) | Hecho. No estaba en este diseño: lo exige el Arnau |
| Validaciones antes de transferir (§5.4) | Hecho |
| `pages` y `documents` en `on_transfer_validate` / `on_transfer_advanced` | Hecho (era S3) |
| `{pagefield:}`, API del panel de verificación, «cada fichero es un documento» al importar | **Pendiente (S3)** |
| Cabeceras de tramo en las miniaturas, «Documentos: N» | **Pendiente (S4)** |
| Familia eCAP del Arnau (04 y 08): secretos en scripts + ODBC | **Pendiente** |

**Desviación del script de nombre respecto a Flexibar:** si el script lanza, Flexibar cae
al patrón y lo deja en el log. DocScan no transfiere nada y da el motivo, por la regla
«un fallo de script nunca se da por bueno» (lote 3).

---

*Análisis generado el 2026-10-26 contra FlexibarNET10 @ `f3ed0383` (v1.30.0).*
