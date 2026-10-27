"""Regenera las capturas de pantalla de la documentación (y la del portfolio).

Abre las ventanas reales de DocScan sin mostrarlas (Qt offscreen), con datos
de demostración **ficticios y neutros**: empresas de ejemplo, ningún hospital
ni persona real. Así, cada vez que cambia la interfaz las capturas se rehacen
con un solo comando y salen siempre iguales.

Todo se ejecuta aislado: base de datos, datos y preferencias van a un
directorio temporal, de modo que el script no lee ni toca la configuración
real del usuario (``~/.local/share/docscan``, ``~/.config`` o el registro de
Windows) y no hace ninguna conexión de red.

Uso::

    .venv/bin/python tools/ui_snapshots.py                 # todas, tema oscuro
    .venv/bin/python tools/ui_snapshots.py --theme light --out /tmp/capturas
    .venv/bin/python tools/ui_snapshots.py --only workbench_full launcher_dark
    .venv/bin/python tools/ui_snapshots.py --portfolio ../portfolio/public/docscan-studio.webp
    .venv/bin/python tools/ui_snapshots.py --list

Por defecto escribe en ``docs/screenshots/`` y ``docs-web/assets/screenshots/``
con los mismos nombres de fichero que ya usan el README y la guía.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import tempfile
import time
import types
from collections.abc import Callable
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUTS = (
    ROOT / "docs" / "screenshots",
    ROOT / "docs-web" / "assets" / "screenshots",
)
MAIN_SIZE = (1440, 900)


# ---------------------------------------------------------------------------
# Aislamiento: SIEMPRE antes de importar nada de la aplicación.
# ---------------------------------------------------------------------------


def _isolate(workdir: Path, visible: bool) -> None:
    """Redirige datos, preferencias y pantalla a un entorno desechable."""
    os.environ["XDG_DATA_HOME"] = str(workdir / "data")
    os.environ["XDG_CONFIG_HOME"] = str(workdir / "config")
    os.environ["XDG_CACHE_HOME"] = str(workdir / "cache")
    if not visible:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
    # Sin escáner real: create_scanner() no debe enumerar dispositivos USB.
    sys.modules.setdefault("sane", types.ModuleType("sane"))
    # Los lotes guardan el nombre del equipo como estación: que no salga el
    # del equipo real en las capturas públicas.
    platform.node = lambda: DEMO_STATION
    sys.path.insert(0, str(ROOT))

    # QSettings («DocScanStudio») usa el backend nativo: el registro en Windows.
    # Igual que en tests/conftest.py, se fuerza IniFormat en el temporal.
    from PySide6 import QtCore

    real = QtCore.QSettings
    ini, user = real.Format.IniFormat, real.Scope.UserScope
    real.setPath(ini, user, str(workdir / "qsettings"))

    class _IsolatedQSettings(real):
        def __init__(self, *args, **kwargs):
            if len(args) == 2 and all(isinstance(a, str) for a in args):
                super().__init__(ini, user, args[0], args[1], **kwargs)
            else:
                super().__init__(*args, **kwargs)

    QtCore.QSettings = _IsolatedQSettings


# ---------------------------------------------------------------------------
# Documentos de demostración (ficticios)
# ---------------------------------------------------------------------------

COMPANY = "Suministros Ejemplo S.L."
COMPANY_ADDR = "Calle Mayor 1 · 28000 Ciudad Ejemplo"
DEMO_STATION = "PUESTO-01"  # nombre de equipo neutro para los lotes


def _font(size: int, bold: bool = False):
    from PIL import ImageFont

    name = "Inter-Bold.otf" if bold else "Inter-Regular.otf"
    return ImageFont.truetype(str(ROOT / "resources" / "fonts" / "inter" / name), size)


def _barcode(value: str, scale: int = 4):
    import numpy as np
    import zxingcpp

    img = zxingcpp.write_barcode_to_image(
        zxingcpp.create_barcode(value, zxingcpp.BarcodeFormat.Code128), scale=scale
    )
    return np.array(img)


def demo_page(kind: str, number: str, page: int, total: int):
    """Página A4 (150 DPI) de un documento ficticio. Devuelve (BGR, caja barcode)."""
    import numpy as np
    from PIL import Image, ImageDraw

    w, h = 1240, 1754
    canvas = Image.new("RGB", (w, h), (252, 252, 250))
    d = ImageDraw.Draw(canvas)
    d.text((110, 110), COMPANY, font=_font(46, bold=True), fill=(30, 34, 45))
    d.text((110, 175), COMPANY_ADDR, font=_font(24), fill=(110, 115, 125))
    d.line((110, 240, w - 110, 240), fill=(40, 40, 40), width=3)
    title = {"factura": "FACTURA", "albaran": "ALBARÁN DE ENTREGA", "anexo": "ANEXO"}[
        kind
    ]
    d.text((110, 290), title, font=_font(40, bold=True), fill=(30, 34, 45))
    d.text((110, 350), f"Número: {number}", font=_font(28), fill=(45, 45, 45))
    d.text((700, 350), "Fecha: 14/07/2026", font=_font(28), fill=(45, 45, 45))
    d.text(
        (110, 400), "Cliente: Comercial Demo S.A.", font=_font(28), fill=(45, 45, 45)
    )

    y = 500
    d.rectangle((110, y, w - 110, y + 50), fill=(232, 236, 242))
    for x, text in ((125, "Referencia"), (380, "Descripción"), (880, "Cantidad")):
        d.text((x, y + 10), text, font=_font(24, bold=True), fill=(30, 34, 45))
    items = [
        ("REF-10412", "Caja de archivo definitivo", "24"),
        ("REF-08833", "Papel multifunción 80 g", "60"),
        ("REF-11207", "Carpeta colgante", "150"),
        ("REF-07540", "Etiquetas adhesivas", "12"),
        ("REF-11970", "Archivador de palanca", "48"),
    ]
    for i, (ref, desc, qty) in enumerate(items if kind != "anexo" else items[:2]):
        yy = y + 70 + i * 50
        d.text((125, yy), ref, font=_font(24), fill=(45, 45, 45))
        d.text((380, yy), desc, font=_font(24), fill=(45, 45, 45))
        d.text((900, yy), qty, font=_font(24), fill=(45, 45, 45))
        d.line((110, yy + 42, w - 110, yy + 42), fill=(220, 222, 228), width=1)
    d.text(
        (110, h - 120),
        f"Página {page} de {total}",
        font=_font(22),
        fill=(120, 120, 120),
    )

    arr = np.array(canvas)[:, :, ::-1].copy()  # RGB -> BGR
    box = (0, 0, 0, 0)
    if kind != "anexo":
        bc = _barcode(number)
        bh, bw = bc.shape
        x0, y0 = w - 110 - bw, 270
        arr[y0 : y0 + bh, x0 : x0 + bw] = bc[:, :, None]
        box = (x0, y0, bw, bh)
    return arr, box


# ---------------------------------------------------------------------------
# Datos de demostración en la base de datos aislada
# ---------------------------------------------------------------------------

PIPELINE = [
    {"type": "image_op", "id": "enderezar", "op": "AutoDeskew"},
    {"type": "barcode", "id": "codigos", "engine": "motor2"},
    {"type": "ocr", "id": "texto", "engine": "rapidocr", "languages": ["es"]},
    {
        "type": "script",
        "id": "separar",
        "label": "Separar documentos",
        "entry_point": "separar",
        "script": (
            "def separar(app, batch, page, pipeline):\n"
            '    """Marca como separadora la página con el código de la factura."""\n'
            "    for bc in page.barcodes:\n"
            "        if bc.value.startswith('FAC-'):\n"
            "            bc.role = 'separator'\n"
            "            page.fields['separator'] = bc.value\n"
            "            return\n"
        ),
    },
]

BATCH_FIELDS = [
    {
        "label": "Proveedor",
        "type": "texto",
        "required": True,
        "description": "NIF o nombre del proveedor tal como figura en la factura.",
    },
    {
        "label": "Fecha de recepción",
        "type": "fecha",
        "config": {"format": "dd/MM/yyyy"},
        "description": "Fecha de entrada en el registro. Vacía = hoy.",
    },
    {"label": "Cajas", "type": "numérico", "config": {"min": 0, "max": 999, "step": 1}},
]

EVENTS = {
    "on_transfer_validate": (
        "def on_transfer_validate(app, batch):\n"
        '    """Exige el proveedor antes de archivar."""\n'
        "    if not batch.fields.get('Proveedor'):\n"
        "        log.warning('Falta el proveedor')\n"
        "        return False\n"
        "    return True\n"
    ),
    # Evento pausado: conserva el código pero no se ejecuta
    "on_batch_loaded": {
        "script": (
            "def on_batch_loaded(app, batch):\n"
            "    log.info('Lote %s abierto', batch.id)\n"
        ),
        "enabled": False,
    },
}

_TRANSFER_PDF = {
    "mode": "pdf",
    "destination": "/archivo/facturas",
    "filename_pattern": "{first_barcode}_{batch_id}",
}

# Cada aplicación con su configuración, para que las tarjetas del launcher
# (icono, acento y etiquetas se derivan de ella) enseñen la variedad real.
APPS = [
    (
        "Facturas de proveedores",
        "Un PDF por factura, separado por su código Code128",
        {
            "pipeline": PIPELINE,
            "events": EVENTS,
            "transfer": _TRANSFER_PDF,
            "group": "Administración",
        },
    ),
    (
        "Albaranes de entrada",
        "Albaranes de mercancía recibida en almacén",
        {
            "pipeline": PIPELINE[:2],
            "transfer": {
                "mode": "folder",
                "destination": "/archivo/albaranes",
                "output_format": "tiff",
            },
            "group": "Administración",
        },
    ),
    (
        "Expedientes de personal",
        "Contratos y documentación de RR. HH.",
        {
            "pipeline": [PIPELINE[0], PIPELINE[2]],
            "transfer": {"mode": "pdfa", "destination": "/archivo/rrhh"},
        },
    ),
    (
        "Contratos de alquiler",
        "Contratos firmados y sus anexos",
        {
            "pipeline": PIPELINE[:1],
            "transfer": {"mode": "pdf", "destination": "/archivo/contratos"},
        },
    ),
    (
        "Correspondencia entrante",
        "Cartas y notificaciones recibidas",
        {"pipeline": PIPELINE[:1], "scanner": "Canon DR-M160", "active": False},
    ),
]


def seed(session_factory, images_dir: Path) -> dict:
    """Crea las aplicaciones y lotes de demostración. Devuelve sus ids."""
    from app.models.application import Application
    from app.models.barcode import Barcode
    from app.services.batch_service import BatchService

    ids: dict = {}
    with session_factory() as s:
        for name, desc, profile in APPS:
            s.add(
                Application(
                    name=name,
                    description=desc,
                    pipeline_json=json.dumps(profile["pipeline"]),
                    batch_fields_json=json.dumps(BATCH_FIELDS),
                    events_json=json.dumps(profile.get("events", {})),
                    transfer_json=json.dumps(profile.get("transfer", {})),
                    active=profile.get("active", True),
                    group=profile.get("group", ""),
                )
            )
        s.commit()
        apps = {a.name: a.id for a in s.query(Application).all()}
    ids["app"] = apps["Facturas de proveedores"]

    # Escáner recordado por el Workbench (QSettings aislado): de él sale el
    # icono de escáner de la tarjeta.
    from PySide6.QtCore import QSettings  # ya sustituida por la aislada

    settings = QSettings("DocScanStudio", "Workbench")
    for name, _desc, profile in APPS:
        if profile.get("scanner"):
            settings.setValue(f"source/{apps[name]}/scanner_name", profile["scanner"])

    # Lotes para el gestor de lotes: varios estados.
    plan = [
        ("Facturas de proveedores", "exported", 6),
        ("Albaranes de entrada", "ready_to_export", 3),
        ("Expedientes de personal", "error_export", 2),
        ("Facturas de proveedores", "read", 4),
    ]
    for app_name, state, n in plan:
        with session_factory() as s:
            svc = BatchService(s, images_dir)
            batch = svc.create_batch(apps[app_name])
            pages = [
                demo_page("factura", f"FAC-2026-{i:04d}", i + 1, n)[0] for i in range(n)
            ]
            created = svc.add_pages(batch.id, pages)
            for p in created:
                p.pipeline_processed = True
            svc.transition_state(batch.id, state)
            s.commit()

    # Lote del Workbench: factura de dos páginas + factura + página a revisión.
    with session_factory() as s:
        svc = BatchService(s, images_dir)
        batch = svc.create_batch(apps["Facturas de proveedores"])
        batch.fields_json = json.dumps(
            {
                "Proveedor": COMPANY,
                "Fecha de recepción": date(2026, 7, 14).strftime("%d/%m/%Y"),
                "Cajas": "3",
            },
            ensure_ascii=False,
        )
        docs = [
            ("factura", "FAC-2026-0142", 1, 2),
            ("anexo", "FAC-2026-0142", 2, 2),
            ("factura", "FAC-2026-0143", 1, 1),
            ("factura", "FAC-2026-0144", 1, 1),
        ]
        rendered = [demo_page(*d) for d in docs]
        pages = svc.add_pages(batch.id, [img for img, _ in rendered])
        for page, (kind, number, *_), (_img, box) in zip(pages, docs, rendered):
            page.pipeline_processed = True
            if kind != "anexo":
                s.add(
                    Barcode(
                        page_id=page.id,
                        value=number,
                        symbology="Code128",
                        engine="zxing",
                        step_id="codigos",
                        role="separator",
                        quality=1.0,
                        pos_x=box[0],
                        pos_y=box[1],
                        pos_w=box[2],
                        pos_h=box[3],
                    )
                )
        pages[0].ocr_text = (
            f"{COMPANY}\nFACTURA\nNúmero: FAC-2026-0142\nFecha: 14/07/2026\n"
            "Cliente: Comercial Demo S.A."
        )
        s.add(
            Barcode(
                page_id=pages[0].id,
                value="PEDIDO-7781",
                symbology="MANUAL",
                engine="manual",
                step_id="manual",
            )
        )
        pages[3].needs_review = True
        pages[3].review_reason = "Falta el número de pedido"
        svc.transition_state(batch.id, "read")
        s.commit()
        ids["batch"] = batch.id
    return ids


# ---------------------------------------------------------------------------
# Capturas
# ---------------------------------------------------------------------------


def _settle(qapp, seconds: float = 0.6) -> None:
    """Deja correr el bucle de eventos (cargas diferidas, miniaturas…)."""
    end = time.time() + seconds
    while time.time() < end:
        qapp.processEvents()
        time.sleep(0.02)


class Shooter:
    """Genera cada captura con nombre de fichero estable."""

    def __init__(self, qapp, session_factory, ids: dict, outputs: list[Path]) -> None:
        self.qapp = qapp
        self.sf = session_factory
        self.ids = ids
        self.outputs = outputs
        self.saved: dict[str, list[Path]] = {}

    def _save(self, name: str, widget) -> None:
        _settle(self.qapp)
        pixmap = widget.grab()
        for out in self.outputs:
            out.mkdir(parents=True, exist_ok=True)
            path = out / f"{name}.png"
            pixmap.save(str(path))
            self.saved.setdefault(name, []).append(path)

    def _app(self):
        from app.models.application import Application

        with self.sf() as s:
            app = s.get(Application, self.ids["app"])
            s.expunge(app)
        return app

    # -- launcher -----------------------------------------------------------

    def _launcher(self):
        from app.ui.launcher.launcher_window import LauncherWindow

        win = LauncherWindow(self.sf)
        win.resize(*MAIN_SIZE)
        win.show()
        return win

    def launcher_dark(self) -> None:
        win = self._launcher()
        self._save("launcher_dark", win)
        win.close()

    def ai_mode(self) -> None:
        win = self._launcher()
        panel = win._ai_mode_panel
        panel.setVisible(True)
        btn = win._sidebar.get_button("ai_mode")
        if btn is not None and btn.isCheckable():
            btn.setChecked(True)
        panel._add_message(
            "user",
            "Necesito una aplicación para facturas de proveedores: un PDF por factura, "
            "separado por el código Code128 de la primera página.",
        )
        panel._add_message(
            "assistant",
            "He creado «Facturas de proveedores» con este pipeline: enderezar → "
            "códigos de barras → OCR → script «Separar documentos». La transferencia "
            "genera un PDF por documento con el nombre {first_barcode}_{batch_id}. "
            "¿Ajusto algo más?",
        )
        self._save("ai_mode", win)
        win.close()

    def new_app_dialog(self) -> None:
        from app.ui.launcher.new_app_dialog import NewAppDialog

        dlg = NewAppDialog()
        dlg.show()
        self._save("new_app_dialog", dlg)
        dlg.close()

    def about_dialog(self) -> None:
        from app.ui.about_dialog import AboutDialog

        dlg = AboutDialog()
        dlg.show()
        self._save("about_dialog", dlg)
        dlg.close()

    # -- configurador -------------------------------------------------------

    _CONFIG_TABS = {
        "configurator_general": 0,
        "configurator_image": 1,
        "configurator_fields": 2,
        "configurator_pipeline": 3,
        "configurator_events": 4,
        "configurator_transfer": 5,
    }

    def configurator(self, name: str) -> None:
        from app.ui.configurator.app_configurator import AppConfigurator

        dlg = AppConfigurator(self._app(), self.sf)
        dlg.resize(1100, 780)
        dlg.show()
        dlg._tabs.setCurrentIndex(self._CONFIG_TABS[name])
        if name == "configurator_events":
            dlg._tab_events.select_event("on_transfer_validate")
        self._save(name, dlg)
        dlg.close()

    # -- diálogos de pasos --------------------------------------------------

    def dialog_barcode(self) -> None:
        from app.pipeline.steps import BarcodeStep
        from app.ui.configurator.step_dialogs.barcode_step_dialog import (
            BarcodeStepDialog,
        )

        dlg = BarcodeStepDialog(
            BarcodeStep(
                id="codigos",
                engine="motor2",
                symbologies=["Code128", "QR"],
                separator_enabled=True,
                separator_by="regex",
                separator_regex="^22SEP",
                separator_regex_include_symbology=True,
            )
        )
        dlg.resize(720, 1400)
        dlg.show()
        self._save("dialog_barcode", dlg)
        dlg.close()

    def dialog_ocr(self) -> None:
        from app.pipeline.steps import OcrStep
        from app.ui.configurator.step_dialogs.ocr_step_dialog import OcrStepDialog

        dlg = OcrStepDialog(OcrStep(id="texto", engine="rapidocr", languages=["es"]))
        dlg.show()
        self._save("dialog_ocr", dlg)
        dlg.close()

    def dialog_script(self) -> None:
        from app.pipeline.serializer import deserialize
        from app.ui.configurator.step_dialogs.script_step_dialog import ScriptStepDialog

        step = deserialize(json.dumps([PIPELINE[3]]))[0]
        dlg = ScriptStepDialog(step)
        dlg.resize(760, 560)
        dlg.show()
        self._save("dialog_script", dlg)
        dlg.close()

    def dialog_event_script(self) -> None:
        from app.ui.configurator.event_script_dialog import EventScriptDialog

        dlg = EventScriptDialog(
            "on_transfer_validate",
            "Antes de transferir",
            EVENTS["on_transfer_validate"],
        )
        dlg.show()
        self._save("dialog_event_script", dlg)
        dlg.close()

    # -- workbench y gestor de lotes ---------------------------------------

    def workbench_full(self) -> None:
        from unittest.mock import patch

        import app.services.scanner_service as scanner_service
        from app.ui.workbench.workbench_window import WorkbenchWindow

        with patch.object(
            scanner_service, "create_scanner", side_effect=RuntimeError("sin escáner")
        ):
            win = WorkbenchWindow(self.ids["app"], self.sf, batch_id=self.ids["batch"])
        win.resize(*MAIN_SIZE)
        win.show()
        win._navigate_to(0)
        win._update_lot_counters()
        deadline = time.time() + 6
        while time.time() < deadline and len(win._thumbnail_panel._thumbnails) < 4:
            _settle(self.qapp, 0.2)
        win._metadata_panel.select_tab("ocr")
        self._save("workbench_full", win)
        win.close()

    def batch_manager(self) -> None:
        from app.ui.batch_manager.batch_manager_window import BatchManagerWindow

        win = BatchManagerWindow(self.sf)
        win.resize(*MAIN_SIZE)
        win.show()
        self._save("batch_manager", win)
        win.close()

    def shots(self) -> dict[str, Callable[[], None]]:
        table: dict[str, Callable[[], None]] = {
            "launcher_dark": self.launcher_dark,
            "ai_mode": self.ai_mode,
            "new_app_dialog": self.new_app_dialog,
            "about_dialog": self.about_dialog,
            "dialog_barcode": self.dialog_barcode,
            "dialog_ocr": self.dialog_ocr,
            "dialog_script": self.dialog_script,
            "dialog_event_script": self.dialog_event_script,
            "workbench_full": self.workbench_full,
            "batch_manager": self.batch_manager,
        }
        for name in self._CONFIG_TABS:
            table[name] = lambda n=name: self.configurator(n)
        return table


SHOT_NAMES = (
    "launcher_dark",
    "ai_mode",
    "new_app_dialog",
    "about_dialog",
    "configurator_general",
    "configurator_image",
    "configurator_fields",
    "configurator_pipeline",
    "configurator_events",
    "configurator_transfer",
    "dialog_barcode",
    "dialog_ocr",
    "dialog_script",
    "dialog_event_script",
    "workbench_full",
    "batch_manager",
)


def _portfolio_image(src: Path, dest: Path, width: int = 1600) -> None:
    """Versión WebP de la captura del Workbench para el portfolio."""
    from PIL import Image

    img = Image.open(src)
    if img.width > width:
        img = img.resize((width, round(img.height * width / img.width)), Image.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest, "WEBP", quality=85, method=6)


# ---------------------------------------------------------------------------
# Programa
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--theme", choices=("dark", "light"), default="dark")
    parser.add_argument(
        "--out",
        type=Path,
        action="append",
        help="Carpeta de salida (repetible). Por defecto, las dos de la documentación.",
    )
    parser.add_argument(
        "--only", nargs="+", metavar="NOMBRE", help="Solo estas capturas"
    )
    parser.add_argument(
        "--portfolio",
        type=Path,
        help="Además, escribe la imagen WebP del portfolio aquí",
    )
    parser.add_argument("--visible", action="store_true", help="Mostrar las ventanas")
    parser.add_argument("--list", action="store_true", help="Lista las capturas y sale")
    args = parser.parse_args(argv)

    if args.list:
        print("\n".join(SHOT_NAMES))
        return 0
    unknown = set(args.only or []) - set(SHOT_NAMES)
    if unknown:
        parser.error(f"capturas desconocidas: {', '.join(sorted(unknown))}")

    workdir = Path(tempfile.mkdtemp(prefix="docscan-snapshots-"))
    _isolate(workdir, args.visible)

    import logging

    logging.basicConfig(level=logging.WARNING)
    from PySide6.QtWidgets import QApplication

    qapp = QApplication(["docscan-snapshots"])

    import app.models  # noqa: F401 — registra todos los modelos
    from app.db.database import create_db_engine, get_session_factory, run_migrations
    from app.ui.fonts import register_fonts
    from app.ui.theme_manager import Theme, ThemeManager
    from config.settings import APP_IMAGES_DIR, get_settings

    register_fonts()
    engine = create_db_engine(get_settings().database.path)
    run_migrations(engine)
    session_factory = get_session_factory(engine)
    ids = seed(session_factory, APP_IMAGES_DIR)
    ThemeManager().apply_theme(Theme.DARK if args.theme == "dark" else Theme.LIGHT)

    outputs = args.out or list(DEFAULT_OUTPUTS)
    shooter = Shooter(qapp, session_factory, ids, outputs)
    table = shooter.shots()
    wanted = args.only or list(SHOT_NAMES)
    if args.portfolio and "workbench_full" not in wanted:
        wanted.append("workbench_full")
    failed = []
    for name in wanted:
        try:
            table[name]()
            print(f"  ✓ {name}")
        except Exception as exc:  # noqa: BLE001 — se informa y se sigue
            failed.append(name)
            print(f"  ✗ {name}: {type(exc).__name__}: {exc}")

    if args.portfolio and "workbench_full" in shooter.saved:
        _portfolio_image(shooter.saved["workbench_full"][0], args.portfolio)
        print(f"  ✓ portfolio → {args.portfolio}")

    print(f"\n{len(wanted) - len(failed)} capturas en: {', '.join(map(str, outputs))}")
    engine.dispose()
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
