# :material-rename-box: Patrones de nombre

Los patrones de nombre se usan en la transferencia para generar nombres de fichero dinámicos.

## Variables disponibles

| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `{batch_id}` | ID numérico del lote | `42` |
| `{page_index}` | Índice de la página (base 0) | `0`, `1`, `2` |
| `{page_number}` | Número de página (base 1) | `1`, `2`, `3` |
| `{fecha}` | Fecha actual (dd-MM-yyyy) | `25-03-2026` |
| `{hostname}` | Nombre del ordenador | `PC-OFICINA` |
| `{app_name}` | Nombre de la aplicación | `Facturas` |
| `{campo_lote}` | Cualquier campo de lote por nombre | `FAC-001` |

## Ejemplos

```
# Resultado: facturas/FAC-001/pagina_001.tif
{app_name}/{numero_factura}/pagina_{page_number:03d}

# Resultado: 2026-03-25/lote_42_pag_01.pdf
{fecha}/{batch_id}_pag_{page_number:02d}
```

!!! tip
    Los campos de lote se referencian directamente por su nombre tal como están definidos en la pestaña Campos.
