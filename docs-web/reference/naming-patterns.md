# :material-rename-box: Patrones de nombre

Los patrones de nombre se usan en la transferencia para generar nombres de fichero dinámicos.
Siguen la sintaxis de `str.format` de Python, así que admiten formato (`{page_index:04d}`).

## Variables disponibles

| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `{batch_id}` | ID numérico del lote | `42` |
| `{page_index}` | Índice de la página (base 0) | `0`, `1`, `2` |
| `{first_barcode}` | Valor del primer barcode de la página | `FAC-001` |
| `{nombre_del_campo}` | Cualquier campo de lote por su nombre; los espacios pasan a `_` (`fecha lote` → `{fecha_lote}`) | `2026-03-25` |

!!! danger "Una variable desconocida no da error"
    Si el patrón usa una variable que no existe (por ejemplo `{page_number}`,
    `{fecha}`, `{hostname}` o `{app_name}`, que **no** están disponibles), el
    nombre entero se sustituye por `batch_<lote>_page_<índice>` y solo queda un
    aviso en el log. Comprueba el patrón con un lote de prueba.

## Ejemplos

```
# Resultado: FAC-001/pagina_0001.tif   (campo de lote «numero factura»)
{numero_factura}/pagina_{page_index:04d}

# Resultado: lote_42/B1_0002.pdf
lote_{batch_id}/{first_barcode}_{page_index:04d}
```

!!! tip
    Los campos de lote se referencian por su nombre tal como están definidos en la
    pestaña Campos, con los espacios convertidos en `_`.

!!! info "Valores que vienen del papel"
    `{first_barcode}` y los campos salen del documento escaneado, así que se sanean
    antes de usarlos:

    - Sus `/` y `\` se convierten en `_`: solo las barras escritas en el patrón crean
      subcarpetas.
    - Los caracteres no válidos (`<>:"|?*`) pasan a `_` y los nombres reservados de
      Windows (`CON`, `NUL`, `COM1`…) llevan un `_` delante.
    - Cada segmento se limita a 200 caracteres.
    - La ruta final se comprueba: si quedara fuera de la carpeta de destino, la
      transferencia falla en lugar de escribir.

    Si el valor queda vacío, se usa `batch_<lote>_page_<índice>`.

## Pendiente: paridad con FlexibarNET 10

Los tokens de FlexibarNET 10 (`{page_number}`, `{date}`, `{time}`, `{app_name}`,
`{hostname}`, `{username}`, `{separator}`, `{document_index}`,
`{field:NOMBRE:FORMATO}`, `{pagefield:NOMBRE}`) están previstos, pero **todavía no**
existen en DocScan. Ver `docs/propuestas_desde_flexibarnet10_2026-10-26.md` y
`docs/diseno_separadores_documento_2026-10-26.md`.
