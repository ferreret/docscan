# :gear: Configurador

El configurador permite ajustar cada aspecto de una aplicación a través de **7 pestañas**: General, Imagen, Campos de lote, Pipeline, Eventos,
Transferencia y Notificaciones.

![Configurador — Pestaña Pipeline](../assets/screenshots/configurator_pipeline.png)

## Pestaña General

Configuración básica de la aplicación.

| Opción | Descripción |
|--------|-------------|
| Nombre | Nombre visible en el Launcher |
| Descripción | Texto descriptivo del propósito |
| Activa | Las inactivas se ven con el indicador gris en el Launcher |
| Backend escáner | SANE (Linux) o TWAIN/WIA (Windows), según el sistema. Un backend de otra plataforma (una App preparada para Windows abierta en Linux) se conserva al guardar |
| Mostrar el diálogo del escáner al capturar | Valor por defecto de la casilla de ⚙ en los equipos donde el operador no la ha cambiado |
| Color del icono | Color de la tarjeta en el Launcher. «Automático» lo saca del nombre, como FlexibarNET 10 |
| Transferir automáticamente | Transferir al completar el pipeline |
| Cerrar tras transferir | Cierra el Workbench después de transferir |
| Barcode manual | Expresión regex o valor fijo para los códigos añadidos a mano, y la casilla que oculta «+ Añadir» |
| Detección de páginas en blanco | Excluir páginas en blanco automáticamente |
| Pestañas del Workbench | Qué paneles y pestañas ve el operador y en qué orden |

## Pestaña Imagen

Define el formato de captura: formato de fichero, modo de color y compresión.

![Pestaña Imagen del configurador](../assets/screenshots/configurator_image.png)

## Pestaña Campos de lote

Campos dinámicos que el operador rellena en el Workbench.

| Tipo | Widget | Configuración |
|------|--------|---------------|
| Texto | Campo libre | — |
| Fecha | Calendario | Formato de fecha |
| Lista | Desplegable | Valores separados por coma |
| Numérico | Spinner | Mínimo, máximo, paso |

## Pestaña Pipeline

Cada fila de la lista es un paso, como en FlexibarNET 10:

- una **casilla** que lo activa o desactiva (un paso desactivado se ve atenuado y
  no se ejecuta);
- el **icono de su tipo**, cada uno con su color: imagen, barcode, OCR y script;
- su nombre y lo esencial de su configuración.

Doble clic para editar un paso. Para cambiar el orden, arrástralo o usa los botones
de subir y bajar.

El diálogo del paso **Barcode** tiene la sección **Separador de documento**
(casilla para activarla): condición (expresión regular, simbología o valor
fijo), *Evaluar sobre NN + valor* (el tooltip lista los números de
simbología) y, para la marca manual del Workbench, la regex del valor y el
valor por defecto. Ver [Separador de documento](pipeline.md#separador-de-documento).

Ver [Pipeline](pipeline.md) para la documentación completa.

## Pestaña Eventos

Ver [Scripting](scripting.md) para los eventos del ciclo de vida. El desplegable
marca con ● los eventos que tienen código y la pestaña se abre en el primero
de ellos.

## Editor de scripts

Todos los scripts (eventos, pasos Script, script de nombre de fichero y las
vistas previas de los asistentes) se editan con el mismo editor: fuente
monoespaciada, colores de Python según el tema, números de línea y resaltado
de la línea actual. **Tab** inserta cuatro espacios (o sangra la selección),
**Mayús+Tab** quita un nivel e **Intro** mantiene la sangría y añade un nivel
después de `:`.

## Pestaña Transferencia

Ver [Transferencia](transfer.md) para las opciones de exportación. Además del
destino y el patrón:

- **Modo**: `folder`, `pdf`, `pdfa`, `tiff` (multipágina) o `csv`.
- **Nombre por**: *Patrón* o *Script*. Con *Script* aparece un editor con la
  plantilla de `file_name(page, document, batch, app)`; la aplicación **no se
  guarda** si el script no compila.
- Grupo **Documentos**: agrupación (un fichero por lote o por documento, en
  los modos multipágina) y si la página separadora se incluye o se descarta.

## Pestaña Notificaciones

Un webhook (URL, método, timeout y cabeceras) al que el worker desatendido avisa
cuando termina una transferencia o cuando falla.
