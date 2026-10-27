"""Siembra las Apps de archivo del Hospital Arnau de Vilanova en DocScan.

Puerto del sembrador ``tools/SeedAppsArnau`` de FlexibarNET10. Crea (o
actualiza, por nombre) las seis Apps de la familia A descritas en
``tools/arnau_apps.py``, y opcionalmente exporta sus packs y genera páginas
de prueba con códigos de barras reales.

Uso::

    # Sembrar en una BD concreta (nunca toca la del usuario por defecto)
    .venv/bin/python tools/seed_apps_arnau.py --db /ruta/docscan.db
    # Raíz de destino distinta de W:\\ y escáner SANE (pruebas en Linux)
    .venv/bin/python tools/seed_apps_arnau.py --db /tmp/a.db --export-base /tmp/salida --escaner sane
    # Exportar un .json por App con el exportador real del launcher
    .venv/bin/python tools/seed_apps_arnau.py --db /tmp/a.db --packs /tmp/packs
    # Generar las páginas de prueba (y comprobar que el lector las lee)
    .venv/bin/python tools/seed_apps_arnau.py --paginas /tmp/paginas

Las páginas son sintéticas: los escaneos reales del hospital no se ceden.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

import arnau_apps  # noqa: E402

log = logging.getLogger("seed_apps_arnau")

# ------------------------------------------------------------------
# Páginas sintéticas (puerto de PaginasSinteticas.cs, familia A)
# ------------------------------------------------------------------

# (fichero, simbología, valor). None = página sin código.
HOJAS: tuple[tuple[str, str | None, str | None], ...] = (
    # Separador de 8 dígitos (Apps antiguas)
    ("01-separador-8-digitos.tif", "Code128", "12345678"),
    # Mismo código repetido: debe anexarse al mismo TIFF
    ("02-separador-8-digitos-repetido.tif", "Code128", "12345678"),
    # Diez dígitos en ITF (Apps «10 DIGITS»): se archiva por los 9 últimos
    ("03-separador-10-digitos.tif", "ITF", "0812345678"),
    # Página en blanco: debe bloquear la transferencia
    ("04-sin-codigo.tif", None, None),
    # Simbología no configurada en la familia A: no marca separador
    ("05-solo-code39.tif", "Code39", "0412345678"),
)

DPI = 200
ANCHO, ALTO = 1654, 2339  # A4 a 200 dpi
ANCHO_CODIGO, ALTO_CODIGO = 800, 120
Y_CODIGO = 200


def _dibujar_codigo(simbologia: str, valor: str) -> np.ndarray:
    """Código de barras en gris (0/255) con escala entera, sin deformar barras."""
    import zxingcpp

    formato = getattr(zxingcpp.BarcodeFormat, simbologia)
    base = np.array(zxingcpp.create_barcode(valor, formato).to_image(scale=1))
    escala = max(1, ANCHO_CODIGO // base.shape[1])
    img = np.array(zxingcpp.create_barcode(valor, formato).to_image(scale=escala))
    # Código 1D: estirar en vertical no cambia el ancho de las barras.
    return cv2.resize(img, (img.shape[1], ALTO_CODIGO), interpolation=cv2.INTER_NEAREST)


def generar_paginas(carpeta: Path) -> list[Path]:
    """Genera las hojas de prueba y comprueba que el lector las lee.

    Una página que el lector no decodifica invalidaría el smoke, así que la
    relectura forma parte de la generación, como en Flexibar.

    Raises:
        RuntimeError: Si alguna hoja no se lee como se esperaba.
    """
    from app.services.barcode_service import BarcodeService
    from app.services.image_lib import ImageLib

    carpeta.mkdir(parents=True, exist_ok=True)
    lector = BarcodeService()
    ficheros: list[Path] = []
    for nombre, simbologia, valor in HOJAS:
        pagina = np.full((ALTO, ANCHO), 255, np.uint8)
        if simbologia and valor:
            codigo = _dibujar_codigo(simbologia, valor)
            x = (ANCHO - codigo.shape[1]) // 2
            pagina[Y_CODIGO : Y_CODIGO + codigo.shape[0], x : x + codigo.shape[1]] = (
                codigo
            )
        ruta = carpeta / nombre
        ImageLib.save(pagina, ruta, compression="group4", dpi=DPI)
        ficheros.append(ruta)

        leidos = [
            (r.symbology, r.value)
            for r in lector.read(image=ImageLib.load(ruta)[0], engine="motor2")
        ]
        esperado = [(simbologia, valor)] if valor else []
        if leidos != esperado:
            raise RuntimeError(f"{nombre}: se esperaba {esperado} y se leyó {leidos}")
        log.info("  %s → %s", nombre, leidos or "sin código")
    return ficheros


# ------------------------------------------------------------------
# Siembra
# ------------------------------------------------------------------


def sembrar(db_path: Path, raiz: str, escaner: str = "twain") -> list[int]:
    """Crea o actualiza las Apps en la BD. Idempotente (upsert por nombre).

    Returns:
        Ids de las Apps, en el orden de ``arnau_apps.APPS``.
    """
    from app.db.database import (
        create_db_engine,
        get_session_factory,
        run_migrations,
    )
    from app.models.application import Application
    from app.models.barcode import Barcode  # noqa: F401
    from app.models.batch import Batch  # noqa: F401
    from app.models.operation_history import OperationHistory  # noqa: F401
    from app.models.page import Page  # noqa: F401
    from app.models.template import Template  # noqa: F401
    from app.services.script_engine import find_script_errors

    engine = create_db_engine(db_path=db_path)
    run_migrations(engine)
    session_factory = get_session_factory(engine)

    ids: list[int] = []
    with session_factory() as session:
        for definicion in arnau_apps.APPS:
            columnas = arnau_apps.columnas(definicion, raiz, escaner)
            errores = find_script_errors(
                columnas["pipeline_json"],
                columnas["events_json"],
                columnas["transfer_json"],
            )
            if errores:
                raise RuntimeError(
                    f"'{definicion.nombre}': hay scripts que no compilan: {errores}"
                )
            app = (
                session.query(Application)
                .filter(Application.name == definicion.nombre)
                .one_or_none()
            ) or Application()
            for clave, valor in columnas.items():
                setattr(app, clave, valor)
            session.add(app)
            session.flush()
            ids.append(app.id)
            log.info("  [%s] '%s' → id=%d", definicion.legacy, app.name, app.id)
        session.commit()
    engine.dispose()
    return ids


def exportar_packs(db_path: Path, destino: Path) -> list[Path]:
    """Un ``.json`` por App con el exportador real del launcher."""
    from app.db.database import create_db_engine, get_session_factory
    from app.models.application import Application
    from app.services.app_export_service import export_to_file

    destino.mkdir(parents=True, exist_ok=True)
    engine = create_db_engine(db_path=db_path)
    ficheros: list[Path] = []
    with get_session_factory(engine)() as session:
        for definicion in arnau_apps.APPS:
            app = (
                session.query(Application)
                .filter(Application.name == definicion.nombre)
                .one()
            )
            ruta = destino / f"{definicion.nombre}.json"
            export_to_file(app, ruta)
            ficheros.append(ruta)
            log.info("  %s", ruta.name)
    engine.dispose()
    return ficheros


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", type=Path, help="Base de datos donde sembrar")
    parser.add_argument(
        "--export-base",
        default=arnau_apps.RAIZ_PRODUCCION,
        help="Raíz de destino de las transferencias (por defecto W:\\)",
    )
    parser.add_argument(
        "--escaner",
        default="twain",
        choices=["twain", "wia", "sane"],
        help="Backend de escáner de las Apps (por defecto twain, como en el hospital)",
    )
    parser.add_argument("--packs", type=Path, help="Carpeta para exportar las Apps")
    parser.add_argument(
        "--paginas", type=Path, help="Carpeta para generar las páginas de prueba"
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if not (args.db or args.paginas):
        parser.error("indica --db (sembrar) o --paginas (páginas de prueba)")
    if args.packs and not args.db:
        parser.error("--packs necesita --db")

    try:
        if args.paginas:
            log.info("Páginas de prueba en %s", args.paginas)
            generar_paginas(args.paginas)
        if args.db:
            log.info("BD:   %s\nRaíz: %s", args.db, args.export_base)
            sembrar(args.db, args.export_base, args.escaner)
            log.info("Listo: %d App(s)", len(arnau_apps.APPS))
        if args.packs:
            log.info("Exportando packs a %s", args.packs)
            exportar_packs(args.db, args.packs)
    except Exception as e:
        log.error("ERROR: %s", e)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
