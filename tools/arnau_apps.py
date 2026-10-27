"""Apps del Hospital Arnau de Vilanova portadas de FlexibarNET10 a DocScan.

Fuente: ``tools/SeedAppsArnau`` de ``Tecnomedia/FlexibarNET10`` (v1.30),
que a su vez porta 1:1 los XML del Flexibar.NET original. Aquí están las seis
Apps de **archivo simple** (familia A). Las dos de **control eCAP** (04 y 08),
que registran en la base de datos PSM_SCANECAP por ODBC, quedan para después.

Cómo funciona una App de la familia A:

- Cada página es una petición con un código de barras (Code128 o
  Interleaved 2 of 5). Ese código es su **separador**: el paso Barcode lo
  detecta con la regex legacy sobre «NN + valor» (``^(02|10)`` = Code128 o
  ITF), así que cada página abre su propio documento.
- Se archiva un TIFF Group4 por código en
  ``<raíz>[/subcarpeta]/aaaammdd/<código>.tif``. Si el mismo código vuelve a
  salir (en el lote o en otro), la página se añade al final del TIFF.
- El nombre lo calcula un script: las Apps de 10 dígitos se quedan con los
  9 últimos y las de Micro anteponen mes y día (``Mdd``). La fecha sale del
  campo de lote «Data» (vacío = hoy).
- Antes de transferir, ``on_transfer_validate`` exige que todas las páginas
  tengan código.

Este módulo solo describe las Apps. ``tools/seed_apps_arnau.py`` las crea en
una base de datos y genera las páginas de prueba.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app.pipeline.serializer import serialize
from app.pipeline.steps import BarcodeStep

# Raíz real en el hospital (unidad de red de las estaciones Windows).
RAIZ_PRODUCCION = "W:\\"

# Grupo del launcher de las Apps del hospital (Flexibar App.Group)
GRUPO = "Hospital Arnau de Vilanova"

# Regex del separador sobre "NN"+valor (NN = número legacy de simbología)
CODE128_O_I2OF5 = "^(02|10)"
SOLO_I2OF5 = "^10"

# Regex del valor tecleado a mano (sin el prefijo NN). En los XML legacy
# estaban desactivadas para la lectura automática; Flexibar las activó solo
# para el alta manual y aquí se hace lo mismo.
SEP_OCHO_O_NUEVE_DIGITOS = r"^\d{8,9}$"
SEP_NUEVE_DIEZ_O_DOCE = r"^\d{9}$|^\d{10}$|^\d{12}$"


@dataclass(frozen=True)
class ArnauApp:
    """Una App de archivo simple del Arnau.

    Attributes:
        legacy: Fichero XML del Flexibar.NET original (trazabilidad).
        nombre: Nombre literal del legacy, con su prefijo numérico.
        descripcion: Texto que ve el operador en el launcher (en catalán).
        subcarpeta: Subcarpeta bajo la raíz ("" = la raíz a secas).
        simbologias: Simbologías que lee el paso Barcode.
        separador_regex: Regex del separador sobre "NN"+valor.
        max_digitos: 0 = código entero; si no, los últimos N.
        prefijo_mdd: Antepone mes (sin cero) y día (dos dígitos) al código.
        regex_manual: Valida el código tecleado a mano por el operador.
    """

    legacy: str
    nombre: str
    descripcion: str
    subcarpeta: str
    simbologias: tuple[str, ...]
    separador_regex: str
    max_digitos: int
    prefijo_mdd: bool
    regex_manual: str


APPS: tuple[ArnauApp, ...] = (
    ArnauApp(
        "00000017",
        "01 Arxiu de Peticions",
        "Arxiu de peticions per codi separador. Un TIFF per document a la carpeta del dia.",
        "",
        ("Code128", "ITF"),
        CODE128_O_I2OF5,
        0,
        False,
        SEP_OCHO_O_NUEVE_DIGITOS,
    ),
    ArnauApp(
        "00000001",
        "02 Documents de Qualitat",
        "Arxiu de documents de qualitat per codi separador.",
        "Qualitat",
        ("Code128", "ITF"),
        CODE128_O_I2OF5,
        0,
        False,
        SEP_OCHO_O_NUEVE_DIGITOS,
    ),
    ArnauApp(
        "00000002",
        "03 Resultats de Micro",
        "Arxiu de resultats de microbiologia. El nom porta el prefix mes+dia.",
        "MR-MICRO",
        ("Code128", "ITF"),
        CODE128_O_I2OF5,
        0,
        True,
        SEP_OCHO_O_NUEVE_DIGITOS,
    ),
    ArnauApp(
        "00000005",
        "05 Arxiu de Peticions 10 DIGITS",
        "Arxiu de peticions amb numeració de 10 dígits (s'arxiva pels 9 últims).",
        "",
        ("ITF",),
        SOLO_I2OF5,
        9,
        False,
        SEP_NUEVE_DIEZ_O_DOCE,
    ),
    ArnauApp(
        "00000006",
        "06 Documents de Qualitat 10 DIGITS",
        "Arxiu de documents de qualitat amb numeració de 10 dígits.",
        "Qualitat",
        ("ITF",),
        SOLO_I2OF5,
        9,
        False,
        SEP_NUEVE_DIEZ_O_DOCE,
    ),
    ArnauApp(
        "00000007",
        "07 Resultats de Micro 10 DIGITS",
        "Arxiu de resultats de microbiologia amb numeració de 10 dígits i prefix mes+dia.",
        "MR-MICRO",
        ("ITF",),
        SOLO_I2OF5,
        9,
        True,
        SEP_NUEVE_DIEZ_O_DOCE,
    ),
)


# ------------------------------------------------------------------
# Scripts (puerto de ArnauScripts.cs)
# ------------------------------------------------------------------

# Fecha que decide la subcarpeta y el prefijo Mdd: el BatchValues.BatchDate
# del legacy. El campo se llama «Data» porque es la etiqueta que ve el
# operador (en catalán): si se renombra, hay que cambiarlo también aquí o
# todo se archivará con la fecha de hoy.
_FECHA_DE_LOTE = """def _fecha_de_lote(batch):
    \"\"\"Fecha del campo de lote «Data» (dd/mm/aaaa); vacía o ilegible = hoy.\"\"\"
    raw = str((batch.fields or {}).get("Data") or "").strip()
    if not raw:
        return date.today()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            pass
    return date.today()
"""


def nombre_fichero(max_digitos: int, prefijo_mdd: bool) -> str:
    """Script de nombre: subruta ``aaaammdd/código`` sin extensión.

    Sale con el formato de ``ruff format``: es lo que el integrador verá y
    editará en el Configurador.
    """
    return f"""from datetime import date, datetime

# Configuración de esta App (en Flexibar, MaxDigitos y PrefijoMdd)
MAX_DIGITOS = {max_digitos}  # 0 = el código entero; si no, los últimos N
PREFIJO_MDD = {prefijo_mdd}  # antepone mes (sin cero) y día al código


{_FECHA_DE_LOTE}

def file_name(page, document, batch, app):
    \"\"\"Subruta aaaammdd/código, sin extensión.\"\"\"
    codigo = document.separator_value if document else ""
    if not codigo:
        raise ValueError(
            f"La página {{page.page_index + 1}} no tiene valor de separador: "
            "no se puede componer el nombre del fichero."
        )
    # Una "/" leída del papel crearía subcarpetas dentro del día
    codigo = codigo.replace("/", "_").replace("\\\\", "_")
    if MAX_DIGITOS > 0 and len(codigo) > MAX_DIGITOS:
        codigo = codigo[-MAX_DIGITOS:]
    fecha = _fecha_de_lote(batch)
    if PREFIJO_MDD:
        # Format(fecha, "Mdd") del VB: mes sin cero y día con dos dígitos
        codigo = f"{{fecha.month}}{{fecha:%d}}" + codigo
    return f"{{fecha:%Y%m%d}}/{{codigo}}"
"""


# Puerto de TransferPrevalidation: toda página debe llevar código separador.
# Lanza en lugar de devolver False para que el operador vea qué página falla.
VALIDAR = """def on_transfer_validate(app, batch, pages):
    sin_codigo = [p.page_index + 1 for p in pages if not p.is_separator]
    if sin_codigo:
        raise ValueError(
            f"Hi ha pàgines sense codis de barra. La primera és la {sin_codigo[0]} "
            f"({len(sin_codigo)} pàgina(es) en total)."
        )
    return True
"""


# ------------------------------------------------------------------
# Configuración de cada App
# ------------------------------------------------------------------


def paso_barcode(app: ArnauApp) -> BarcodeStep:
    """Paso Barcode con la condición de separador del legacy."""
    return BarcodeStep(
        id="barcode",
        engine="motor2",
        symbologies=list(app.simbologias),
        separator_enabled=True,
        separator_by="regex",
        separator_regex=app.separador_regex,
        separator_regex_include_symbology=True,
        separator_manual_regex=app.regex_manual,
    )


def destino(app: ArnauApp, raiz: str) -> str:
    """Carpeta de destino de la App bajo ``raiz``."""
    if not app.subcarpeta:
        return raiz
    sep = "\\" if raiz.endswith("\\") or "\\" in raiz else "/"
    return raiz.rstrip("\\/") + sep + app.subcarpeta


def transferencia(app: ArnauApp, raiz: str) -> dict[str, Any]:
    """Un TIFF Group4 por código, anexando si el código se repite."""
    return {
        "standard_enabled": True,
        "mode": "tiff",
        "destination": destino(app, raiz),
        "grouping": "document",
        "separator_page": "include",
        "collision_policy": "merge",
        "name_mode": "script",
        "file_name_script": nombre_fichero(app.max_digitos, app.prefijo_mdd),
        "filename_pattern": "{separator}",
        "create_subdirs": False,
        "output_tiff_compression": "group4",
    }


# Campo único de lote: la fecha que decide la subcarpeta. No es obligatorio a
# propósito: el Workbench lo rellena con la fecha de hoy y el script cae a hoy
# si está vacío.
CAMPOS_DE_LOTE = [
    {
        "label": "Data",
        "description": "Data del lot (dd/MM/yyyy). Buida = avui.",
        "type": "fecha",
        "config": {"format": "dd/MM/yyyy"},
        "required": False,
    }
]


def columnas(app: ArnauApp, raiz: str, escaner: str = "twain") -> dict[str, Any]:
    """Valores de las columnas de ``Application`` para una App del Arnau.

    Todas las opciones de la App de Flexibar que tienen equivalente en
    DocScan (``Program.Sembrar`` de SeedAppsArnau). Sin equivalente queda el
    grupo del launcher («Hospital Arnau de Vilanova»).
    """
    return {
        "name": app.nombre,
        "description": app.descripcion,
        "group": GRUPO,  # Flexibar App.Group de las Apps del hospital
        "active": True,
        "pipeline_json": serialize([paso_barcode(app)]),
        "events_json": json.dumps({"on_transfer_validate": VALIDAR}),
        "transfer_json": json.dumps(transferencia(app, raiz), ensure_ascii=False),
        "batch_fields_json": json.dumps(CAMPOS_DE_LOTE, ensure_ascii=False),
        # legacy enCompressionBN = Group4. Como en Flexibar, la captura
        # conserva la profundidad del escáner: B/N va en Group4 y una página
        # en gris o color, en LZW (ImageLib), sin binarizarla.
        "image_config_json": json.dumps(
            {"format": "tiff", "tiff_compression": "group4"}
        ),
        "auto_transfer": False,  # legacy ActivateAutotransfer = false
        "close_after_transfer": True,  # legacy CloseAfterExport = true
        "output_format": "tiff",
        "scanner_backend": escaner,  # Flexibar: Twain (estaciones Windows)
        "show_scanner_ui": True,  # legacy ShowScanConfigInterface = true
        "icon_accent": "blue",  # Flexibar IconAccent de la familia A
    }
