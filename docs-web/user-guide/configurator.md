# :gear: Configurador

El configurador permite ajustar cada aspecto de una aplicación a través de **7 pestañas**: General, Imagen, Campos de lote, Pipeline, Eventos,
Transferencia y Notificaciones.

![Configurador — Pestaña Pipeline](../assets/screenshots/configurator_pipeline.png)

## Pestaña General

Configuración básica de la aplicación.

| Opción | Descripción |
|--------|-------------|
| Nombre | Nombre visible en el Launcher. De él sale también el color de su tarjeta |
| Descripción | Texto descriptivo del propósito |
| Activa | Las inactivas se ven con el indicador gris en el Launcher |
| Backend escáner | SANE (Linux) o TWAIN/WIA (Windows), según el sistema |
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

Ver [Pipeline](pipeline.md) para la documentación completa.

## Pestaña Eventos

Ver [Scripting](scripting.md) para los eventos del ciclo de vida.

## Pestaña Transferencia

Ver [Transferencia](transfer.md) para las opciones de exportación.

## Pestaña Notificaciones

Un webhook (URL, método, timeout y cabeceras) al que el worker desatendido avisa
cuando termina una transferencia o cuando falla.
